import { CONFIG } from './config.js';
import { showNotification } from './utils.js';

/**
 * Centralized API Layer connected to FastAPI backend
 */
export const API = {
    async request(endpoint, options = {}) {
        const url = `${CONFIG.getApiUrl()}${endpoint}`;
        try {
            const response = await fetch(url, options);
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || errorData.message || `HTTP error! status: ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error(`API Error (${endpoint}):`, error);
            showNotification(error.message, 'error');
            throw error;
        }
    },
    
    async getHealth() { 
        return this.request('/health', { method: 'GET' });
    },
    
    async askStream(query, onChunk, onFinish, onError, onCitations) {
        const url = `${CONFIG.getApiUrl()}/api/v1/search`;
        const payload = {
            query: query,
            top_k: CONFIG.getTopK(),
            stream: true,
            hybrid_search: true
        };

        try {
            const response = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder('utf-8');
            let buffer = '';

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;
                
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n\n');
                buffer = lines.pop(); // Keep incomplete chunk in buffer

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const dataStr = line.substring(6).trim();
                        if (!dataStr) continue;
                        
                        try {
                            const event = JSON.parse(dataStr);
                            if (event.event === 'done') {
                                if (onFinish) onFinish();
                                return;
                            } else if (event.event === 'error') {
                                if (onError) onError(new Error(event.data));
                                return;
                            } else if (event.event === 'citations') {
                                if (onCitations) onCitations(event.data);
                            } else {
                                if (onChunk) onChunk(event.data);
                            }
                        } catch (e) {
                            console.error('Parse error:', e, dataStr);
                        }
                    }
                }
            }
            if (onFinish) onFinish();
        } catch (error) {
            if (onError) onError(error);
            showNotification(error.message, 'error');
        }
    },
    
    async search(query, options = {}) { 
        const top_k = options.top_k !== undefined ? options.top_k : CONFIG.getTopK();
        const hybrid_search = options.hybrid_search !== undefined ? options.hybrid_search : true;

        return this.request('/api/v1/search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                query: query,
                top_k: top_k,
                stream: false,
                hybrid_search: hybrid_search
            })
        });
    },
    
    async ingest(file) { 
        const formData = new FormData();
        formData.append('file', file);
        return this.request('/api/v1/documents/upload', {
            method: 'POST',
            body: formData
        });
    },
    
    async getDocuments() {
        return this.request('/api/v1/documents', { method: 'GET' });
    },
    
    async deleteDocument(documentId) {
        return this.request(`/api/v1/documents/${documentId}`, { method: 'DELETE' });
    }
};
