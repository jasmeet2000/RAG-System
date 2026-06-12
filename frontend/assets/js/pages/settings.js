import { CONFIG } from '../config.js';
import { showNotification } from '../utils.js';

const form = document.getElementById('settings-form');
const resetBtn = document.getElementById('reset-settings');

// Populate inputs with current config
document.getElementById('api-url').value = CONFIG.getApiUrl();
document.getElementById('theme-select').value = CONFIG.getTheme();
document.getElementById('top-k').value = CONFIG.getTopK();
document.getElementById('rerank-count').value = CONFIG.getRerankCount();
document.getElementById('chunk-size').value = CONFIG.getChunkSize();
document.getElementById('chunk-overlap').value = CONFIG.getChunkOverlap();

form.addEventListener('submit', (e) => {
    e.preventDefault();
    
    // Save to LocalStorage via CONFIG setter
    CONFIG.setSetting('api_url', document.getElementById('api-url').value);
    CONFIG.setSetting('top_k', document.getElementById('top-k').value);
    CONFIG.setSetting('rerank_count', document.getElementById('rerank-count').value);
    CONFIG.setSetting('chunk_size', document.getElementById('chunk-size').value);
    CONFIG.setSetting('chunk_overlap', document.getElementById('chunk-overlap').value);
    
    const newTheme = document.getElementById('theme-select').value;
    if (newTheme !== 'system') {
        CONFIG.setSetting('theme', newTheme);
        document.documentElement.setAttribute('data-theme', newTheme);
    }
    
    showNotification('Settings saved successfully!', 'success');
});

resetBtn.addEventListener('click', () => {
    if (confirm('Are you sure you want to reset all settings to their defaults?')) {
        CONFIG.resetDefaults();
        // Reload page to re-populate defaults from CONFIG getters
        window.location.reload();
    }
});
