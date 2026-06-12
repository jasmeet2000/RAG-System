import { API } from '../api.js';

document.addEventListener('DOMContentLoaded', async () => {
    const sysStatus = document.getElementById('system-status');
    const docsCount = document.getElementById('docs-count');
    const vdbStatus = document.getElementById('vdb-status');
    const llmStatus = document.getElementById('llm-status');
    const activityList = document.getElementById('activity-list');

    try {
        const health = await API.getHealth();
        // console.log(health);
        sysStatus.textContent = health.status === 'ok' ? 'Online' : 'Degraded';
        sysStatus.className = health.status === 'ok' ? 'status-online' : 'status-warning';

        const docsResponse = await API.getDocuments().catch(() => ({ documents: [] }));
        const allDocuments = docsResponse.documents || [];
        docsCount.textContent = allDocuments.length.toString();

        vdbStatus.textContent = health.vector_db === 'connected' ? 'Qdrant Connected' : 'Disconnected';
        vdbStatus.className = health.vector_db === 'connected' ? 'status-online' : 'status-error';

        llmStatus.textContent = health.llm === 'ready' ? 'Ollama Ready' : 'Unavailable';
        llmStatus.className = health.llm === 'ready' ? 'status-online' : 'status-error';

        let currentPage = 1;
        const itemsPerPage = 5;
        const paginationContainer = document.getElementById('dashboard-pagination');
        const prevBtn = document.getElementById('dashboard-prev');
        const nextBtn = document.getElementById('dashboard-next');
        const pageInfo = document.getElementById('dashboard-page-info');

        function renderList() {
            activityList.innerHTML = '';
            
            if (allDocuments.length === 0) {
                activityList.innerHTML = '<li>No documents uploaded yet.</li>';
                paginationContainer.style.display = 'none';
                return;
            }

            const totalPages = Math.ceil(allDocuments.length / itemsPerPage);
            paginationContainer.style.display = totalPages > 1 ? 'flex' : 'none';
            
            prevBtn.disabled = currentPage === 1;
            nextBtn.disabled = currentPage === totalPages;
            pageInfo.textContent = `Page ${currentPage} of ${totalPages}`;

            const startIdx = (currentPage - 1) * itemsPerPage;
            const currentDocs = allDocuments.slice(startIdx, startIdx + itemsPerPage);
            
            currentDocs.forEach(doc => {
                const li = document.createElement('li');
                let timeStr = 'Unknown time';
                if (doc.uploaded_at) {
                    const seconds = Math.floor((new Date() - new Date(doc.uploaded_at)) / 1000);
                    if (seconds < 60) timeStr = 'just now';
                    else if (seconds < 3600) timeStr = Math.floor(seconds / 60) + ' mins ago';
                    else if (seconds < 86400) timeStr = Math.floor(seconds / 3600) + ' hours ago';
                    else timeStr = Math.floor(seconds / 86400) + ' days ago';
                }
                li.innerHTML = `Ingested <strong>${doc.filename}</strong> - <span style="opacity:0.7;">${timeStr}</span>`;
                activityList.appendChild(li);
            });
        }

        prevBtn.addEventListener('click', () => {
            if (currentPage > 1) {
                currentPage--;
                renderList();
            }
        });

        nextBtn.addEventListener('click', () => {
            const totalPages = Math.ceil(allDocuments.length / itemsPerPage);
            if (currentPage < totalPages) {
                currentPage++;
                renderList();
            }
        });

        // Initial render
        renderList();
        
    } catch (error) {
        sysStatus.textContent = 'Offline';
        sysStatus.className = 'status-error';
        docsCount.textContent = '0';
        vdbStatus.textContent = 'Error';
        vdbStatus.className = 'status-error';
        llmStatus.textContent = 'Error';
        llmStatus.className = 'status-error';
    }
});
