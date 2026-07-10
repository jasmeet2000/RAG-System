import { showNotification } from '../utils.js';
import { API } from '../api.js';

const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('file-input');
const uploadList = document.getElementById('upload-list');

// Drag & Drop event listeners
['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
    dropzone.addEventListener(eventName, preventDefaults, false);
});

function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
}

['dragenter', 'dragover'].forEach(eventName => {
    dropzone.addEventListener(eventName, () => dropzone.classList.add('dragover'), false);
});

['dragleave', 'drop'].forEach(eventName => {
    dropzone.addEventListener(eventName, () => dropzone.classList.remove('dragover'), false);
});

// Handle drop and click
dropzone.addEventListener('drop', handleDrop, false);
dropzone.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', (e) => handleFiles(e.target.files));

function handleDrop(e) {
    const dt = e.dataTransfer;
    const files = dt.files;
    handleFiles(files);
}

function handleFiles(files) {
    [...files].forEach(uploadFile);
}

async function uploadFile(file) {
    // 1. Validate File type
    const validExtensions = ['.pdf', '.docx', '.txt', '.md'];
    const isValid = validExtensions.some(ext => file.name.toLowerCase().endsWith(ext));
    
    if (!isValid) {
        showNotification(`Invalid file format: ${file.name}`, 'error');
        return;
    }

    // 2. Create UI entry
    const li = document.createElement('li');
    li.className = 'upload-item';
    li.innerHTML = `
        <div class="upload-item-header">
            <span class="file-name">${file.name}</span>
            <span class="file-status uploading">Processing...</span>
        </div>
        <div class="progress-bar-container">
            <div class="progress-bar" style="width: 50%"></div>
        </div>
    `;
    uploadList.prepend(li);
    
    const progressBar = li.querySelector('.progress-bar');
    const statusText = li.querySelector('.file-status');
    
    try {
        const response = await API.ingest(file);
        
        progressBar.style.width = '100%';
        progressBar.classList.add('success');
        statusText.textContent = `Completed (${response.chunks_created} chunks)`;
        statusText.className = 'file-status success';
        showNotification(`${file.name} ingested successfully!`, 'success');
        
        // Refresh the recent documents list
        loadRecentDocuments();
    } catch (error) {
        progressBar.style.width = '100%';
        progressBar.classList.add('error');
        statusText.textContent = 'Failed';
        statusText.className = 'file-status error';
    }
}

let currentPage = 1;
const itemsPerPage = 5;
let allDocuments = [];

async function loadRecentDocuments() {
    const recentUploadsList = document.getElementById('recent-uploads-list');
    if (!recentUploadsList) return;

    try {
        const response = await API.getDocuments().catch(() => ({ documents: [] }));
        allDocuments = response.documents || [];
        renderList();
    } catch (error) {
        console.error("Failed to load recent documents", error);
    }
}

function renderList() {
    const recentUploadsList = document.getElementById('recent-uploads-list');
    const paginationContainer = document.getElementById('upload-pagination');
    const prevBtn = document.getElementById('upload-prev');
    const nextBtn = document.getElementById('upload-next');
    const pageInfo = document.getElementById('upload-page-info');

    recentUploadsList.innerHTML = '';
    
    if (allDocuments.length === 0) {
        recentUploadsList.innerHTML = '<li class="upload-item" style="justify-content: center; opacity: 0.6;">No documents uploaded yet.</li>';
        if (paginationContainer) paginationContainer.style.display = 'none';
        return;
    }

    const totalPages = Math.ceil(allDocuments.length / itemsPerPage);
    if (paginationContainer) paginationContainer.style.display = totalPages > 1 ? 'flex' : 'none';
    
    if (prevBtn) prevBtn.disabled = currentPage === 1;
    if (nextBtn) nextBtn.disabled = currentPage === totalPages;
    if (pageInfo) pageInfo.textContent = `Page ${currentPage} of ${totalPages}`;

    const startIdx = (currentPage - 1) * itemsPerPage;
    const currentDocs = allDocuments.slice(startIdx, startIdx + itemsPerPage);

    currentDocs.forEach(doc => {
        const li = document.createElement('li');
        li.className = 'upload-item';
        
        let timeStr = 'Unknown time';
        if (doc.uploaded_at) {
            const seconds = Math.floor((new Date() - new Date(doc.uploaded_at)) / 1000);
            if (seconds < 60) timeStr = 'just now';
            else if (seconds < 3600) timeStr = Math.floor(seconds / 60) + ' mins ago';
            else if (seconds < 86400) timeStr = Math.floor(seconds / 3600) + ' hours ago';
            else timeStr = Math.floor(seconds / 86400) + ' days ago';
        }

        li.innerHTML = `
            <div class="upload-item-header" style="width: 100%; display: flex; justify-content: space-between; align-items: center;">
                <div style="display: flex; flex-direction: column; gap: 4px;">
                    <span class="file-name">📄 ${doc.filename}</span>
                    <span class="file-status" style="opacity: 0.7;">${timeStr}</span>
                </div>
                <button class="btn delete-doc-btn" data-id="${doc.document_id}" style="padding: 4px 12px; font-size: 0.8rem; background: var(--error); border: none; color: white; cursor: pointer; border-radius: 4px; transition: opacity 0.2s;">Delete</button>
            </div>
        `;

        const deleteBtn = li.querySelector('.delete-doc-btn');
        deleteBtn.addEventListener('click', async () => {
            if (confirm(`Are you sure you want to delete "${doc.filename}"? This action cannot be undone.`)) {
                deleteBtn.textContent = 'Deleting...';
                deleteBtn.disabled = true;
                deleteBtn.style.opacity = '0.5';
                try {
                    await API.deleteDocument(doc.document_id);
                    showNotification(`Document ${doc.filename} deleted successfully`, 'success');
                    loadRecentDocuments();
                } catch (error) {
                    showNotification(`Failed to delete document: ${error.message}`, 'error');
                    deleteBtn.textContent = 'Delete';
                    deleteBtn.disabled = false;
                    deleteBtn.style.opacity = '1';
                }
            }
        });

        recentUploadsList.appendChild(li);
    });
}

// Event listeners for pagination
document.addEventListener('DOMContentLoaded', () => {
    loadRecentDocuments();
    
    const prevBtn = document.getElementById('upload-prev');
    const nextBtn = document.getElementById('upload-next');
    
    if (prevBtn) {
        prevBtn.addEventListener('click', () => {
            if (currentPage > 1) {
                currentPage--;
                renderList();
            }
        });
    }
    
    if (nextBtn) {
        nextBtn.addEventListener('click', () => {
            const totalPages = Math.ceil(allDocuments.length / itemsPerPage);
            if (currentPage < totalPages) {
                currentPage++;
                renderList();
            }
        });
    }
});

