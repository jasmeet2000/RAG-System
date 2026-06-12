export const CONFIG = {
    // API Defaults
    DEFAULT_API_URL: 'http://localhost:8000',
    
    // Getters for LocalStorage items with fallbacks
    getApiUrl: () => localStorage.getItem('rag_api_url') || 'http://localhost:8000',
    getTheme: () => localStorage.getItem('rag_theme') || 'dark',
    getTopK: () => parseInt(localStorage.getItem('rag_top_k')) || 5,
    getRerankCount: () => parseInt(localStorage.getItem('rag_rerank_count')) || 3,
    getChunkSize: () => parseInt(localStorage.getItem('rag_chunk_size')) || 512,
    getChunkOverlap: () => parseInt(localStorage.getItem('rag_chunk_overlap')) || 50,

    // Setters
    setSetting: (key, value) => localStorage.setItem(`rag_${key}`, value),
    resetDefaults: () => {
        localStorage.removeItem('rag_api_url');
        localStorage.removeItem('rag_theme');
        localStorage.removeItem('rag_top_k');
        localStorage.removeItem('rag_rerank_count');
        localStorage.removeItem('rag_chunk_size');
        localStorage.removeItem('rag_chunk_overlap');
    }
};
