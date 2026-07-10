import { showNotification } from '../utils.js';
import { API } from '../api.js';

// ── DOM References ──────────────────────────────────────────────────────────
const searchForm = document.getElementById('search-form');
const searchInput = document.getElementById('search-input');
const resultsContainer = document.getElementById('results-container');
const resultsCount = document.getElementById('results-count');
const pagination = document.querySelector('.pagination-controls');

const filterSemantic = document.getElementById('filter-semantic');
const filterKeyword = document.getElementById('filter-keyword');
const filterTopK = document.getElementById('filter-topk');

// ── Form Submission ─────────────────────────────────────────────────────────
searchForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const query = searchInput.value.trim();
    if (!query) return;

    // Validate Top-K
    let topK = parseInt(filterTopK.value, 10);
    if (isNaN(topK) || topK < 1) { topK = 1; filterTopK.value = '1'; }
    if (topK > 20) { topK = 20; filterTopK.value = '20'; }

    // Read filter states
    const isKeyword = filterKeyword.checked;

    const searchOptions = {
        top_k: topK,
        hybrid_search: isKeyword,
    };

    // Loading State
    resultsCount.textContent = 'Searching...';
    resultsContainer.innerHTML = '<div class="empty-state">Retrieving relevant documents...</div>';
    pagination.style.display = 'none';

    const startTime = performance.now();

    try {
        const response = await API.search(query, searchOptions);
        const citations = response.citations || [];
        const elapsed = ((performance.now() - startTime) / 1000).toFixed(2);

        renderResults(citations, elapsed, isKeyword);
        resultsCount.textContent = `${citations.length} Result${citations.length !== 1 ? 's' : ''} Found`;
    } catch (error) {
        resultsCount.textContent = 'Error';
        resultsContainer.innerHTML = `<div class="empty-state" style="color:var(--error)">Failed to search: ${escapeHtml(error.message)}</div>`;
    }
});

// ── Validation: Semantic cannot be disabled ──────────────────────────────────
filterSemantic.addEventListener('change', (e) => {
    if (!e.target.checked) {
        e.target.checked = true;
        showNotification('Semantic search is the core retrieval method and cannot be disabled.', 'warning');
    }
});

// ── Validation: Top-K bounds ─────────────────────────────────────────────────
filterTopK.addEventListener('change', () => {
    let val = parseInt(filterTopK.value, 10);
    if (isNaN(val) || val < 1) { filterTopK.value = '1'; showNotification('Top-K minimum is 1.', 'warning'); }
    if (val > 20) { filterTopK.value = '20'; showNotification('Top-K maximum is 20.', 'warning'); }
});

// ── Render Results ───────────────────────────────────────────────────────────
function renderResults(citations, elapsedSec, isHybrid) {
    if (citations.length === 0) {
        resultsContainer.innerHTML = '<div class="empty-state">No relevant documents found for your query.</div>';
        return;
    }

    const cardsHtml = citations.map((c) => {
        // Normalize score: clamp to [0, 1] then convert to percentage
        const rawScore = typeof c.score === 'number' ? c.score : 0;
        const clampedScore = Math.max(0, Math.min(1, rawScore));
        const pct = (clampedScore * 100).toFixed(1);

        // Build score badge color class
        const scoreClass = clampedScore >= 0.75 ? 'score-high'
            : clampedScore >= 0.5 ? 'score-mid'
            : 'score-low';

        // Safe text snippet
        const snippet = c.text && c.text.trim() ? escapeHtml(c.text) : '<em>Content preview not available.</em>';

        // Filename and title
        const filename = c.filename || 'Unknown File';
        const title = c.title || filename;

        // Page / Chunk display
        const pagePart = c.page != null ? `<span class="meta-tag">Page ${c.page}</span>` : '';
        const chunkPart = c.chunk_index != null ? `<span class="meta-tag">Chunk ${c.chunk_index}</span>` : '';

        // Retrieval method badge
        const method = c.retrieval_method || (isHybrid ? 'Hybrid' : 'Semantic');

        return `
        <div class="result-card">
            <div class="result-header">
                <div class="result-title-block">
                    <h3 class="result-title">${escapeHtml(title)}</h3>
                    <span class="result-filename">${escapeHtml(filename)}</span>
                </div>
                <span class="score-badge ${scoreClass}">${pct}% Match</span>
            </div>
            <div class="result-content">${snippet}</div>
            <div class="result-footer">
                ${pagePart}
                ${chunkPart}
                <span class="meta-tag method-tag">${escapeHtml(method)}</span>
                <span class="result-latency">${elapsedSec}s</span>
            </div>
        </div>`;
    }).join('');

    resultsContainer.innerHTML = cardsHtml;
}

// ── Utility: HTML escaping ───────────────────────────────────────────────────
function escapeHtml(str) {
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(String(str)));
    return div.innerHTML;
}
