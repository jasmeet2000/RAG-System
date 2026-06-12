import { showNotification } from '../utils.js';
import { API } from '../api.js';

const searchForm = document.getElementById('search-form');
const searchInput = document.getElementById('search-input');
const resultsContainer = document.getElementById('results-container');
const resultsCount = document.getElementById('results-count');
const pagination = document.querySelector('.pagination-controls');

searchForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const query = searchInput.value.trim();
    if (!query) return;

    // Loading State
    resultsCount.textContent = 'Searching...';
    resultsContainer.innerHTML = '<div class="empty-state">Retrieving relevant documents...</div>';
    pagination.style.display = 'none';

    try {
        const response = await API.search(query);
        const citations = response.citations || [];
        
        // Since search just hits the ask endpoint with stream=False, it returns citations and answer.
        // For search page, we map citations to results.
        const mockResults = citations.map((c, i) => ({
            id: String(i),
            content: c.text || 'No text snippet available',
            metadata: { source: c.document_id, chunk: c.chunk_id },
            score: c.score || 0
        }));

        renderResults(mockResults);
        resultsCount.textContent = `${mockResults.length} Results Found`;
        if (mockResults.length > 0) pagination.style.display = 'flex';
    } catch (error) {
        resultsCount.textContent = 'Error';
        resultsContainer.innerHTML = `<div class="empty-state" style="color:var(--error)">Failed to search: ${error.message}</div>`;
    }
});

function renderResults(results) {
    if (results.length === 0) {
        resultsContainer.innerHTML = '<div class="empty-state">No relevant documents found.</div>';
        return;
    }

    resultsContainer.innerHTML = results.map(res => `
        <div class="result-card">
            <div class="result-meta">
                <span>Source: <strong>${res.metadata.source}</strong> (Page/Chunk: ${res.metadata.page || res.metadata.chunk})</span>
                <span class="score-badge">${(res.score * 100).toFixed(0)}% Match</span>
            </div>
            <div class="result-content">
                ${res.content}
            </div>
        </div>
    `).join('');
}
