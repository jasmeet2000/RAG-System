import { showNotification } from '../utils.js';
import { API } from '../api.js';

const chatForm = document.getElementById('chat-form');
const chatInput = document.getElementById('chat-input');
const chatHistory = document.getElementById('chat-history');
const clearBtn = document.getElementById('clear-chat');

function scrollToBottom() {
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

function addMessage(content, isUser = false) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${isUser ? 'user-message' : 'ai-message'}`;
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    
    // Render Markdown for AI messages if 'marked' is loaded
    if (!isUser && typeof marked !== 'undefined') {
        contentDiv.innerHTML = marked.parse(content);
    } else {
        contentDiv.textContent = content;
    }
    
    msgDiv.appendChild(contentDiv);
    chatHistory.appendChild(msgDiv);
    scrollToBottom();
}

// Auto-resize textarea
chatInput.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 200) + 'px';
});

// Submit on Enter (without shift)
chatInput.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        chatForm.dispatchEvent(new Event('submit'));
    }
});

chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const query = chatInput.value.trim();
    if (!query) return;
    
    // 1. Add User Message
    addMessage(query, true);
    chatInput.value = '';
    chatInput.style.height = 'auto';
    chatInput.disabled = true; // prevent multiple submissions
    
    // 2. Setup Loading/Streaming UI
    const loadingId = 'loading-' + Date.now();
    addMessage('', false); // Empty message to hold streamed content
    const aiMessageEl = chatHistory.lastChild.querySelector('.message-content');
    chatHistory.lastChild.id = loadingId;
    
    let currentResponse = '';

    // 3. Stream from API
    await API.askStream(
        query,
        (chunkText) => {
            currentResponse += chunkText;
            if (typeof marked !== 'undefined') {
                aiMessageEl.innerHTML = marked.parse(currentResponse);
            } else {
                aiMessageEl.textContent = currentResponse;
            }
            scrollToBottom();
        },
        () => {
            // onFinish
            chatInput.disabled = false;
            chatInput.focus();
        },
        (err) => {
            // onError
            aiMessageEl.innerHTML = `<span style="color:var(--error)">Error: ${err.message}</span>`;
            chatInput.disabled = false;
        },
        (citations) => {
            // onCitations
            if (citations && citations.length > 0) {
                const uniqueCitations = [];
                const seen = new Set();
                citations.forEach(c => {
                    if (!seen.has(c.filename)) {
                        seen.add(c.filename);
                        uniqueCitations.push(c);
                    }
                });
                
                const citationHTML = uniqueCitations.map(c => 
                    `<span style="display:inline-block; background:rgba(255,255,255,0.1); padding:2px 8px; border-radius:12px; margin-right:5px; font-size:0.8rem;">📄 ${c.filename}</span>`
                ).join('');
                
                const citationDiv = document.createElement('div');
                citationDiv.style.marginTop = '10px';
                citationDiv.innerHTML = `<div style="font-size:0.8rem; opacity:0.7; margin-bottom:5px;">Analyzing Sources:</div>${citationHTML}`;
                
                // Prepend citations before the text streams in
                aiMessageEl.parentElement.insertBefore(citationDiv, aiMessageEl);
            }
        }
    );
});

clearBtn.addEventListener('click', () => {
    chatHistory.innerHTML = '';
    showNotification('Chat history cleared.', 'success');
});

// Initial scroll
scrollToBottom();
