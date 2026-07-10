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
    addMessage('', false); // empty AI bubble to animate into
    const el = chatHistory.querySelector('.ai-message .message-content');
    typeMessage(el, '👋 Hi! I\'m ready to help you explore your documents. Ask me anything, and I\'ll find the relevant information for you.');
    showNotification('Chat history cleared.', 'success');
});

// Initial scroll
scrollToBottom();

/**
 * Reusable typing animation — shows thinking dots, then types text
 * character-by-character at 35ms per character.
 * @param {HTMLElement} containerEl - the .message-content element to type into
 * @param {string} text - the full text to type out
 */
function typeMessage(containerEl, text) {
    containerEl.innerHTML = '';

    // Show typing indicator dots
    const indicator = document.createElement('div');
    indicator.className = 'typing-indicator';
    indicator.innerHTML = '<div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>';
    containerEl.appendChild(indicator);

    setTimeout(() => {
        indicator.remove();
        containerEl.classList.add('typing-cursor');

        let i = 0;
        const typeInterval = setInterval(() => {
            containerEl.textContent = text.substring(0, i + 1);
            i++;
            if (i >= text.length) {
                clearInterval(typeInterval);
                setTimeout(() => containerEl.classList.remove('typing-cursor'), 1500);
            }
            scrollToBottom();
        }, 35);
    }, 600);
}

// Welcome Message Typing Animation (runs once on page load)
document.addEventListener('DOMContentLoaded', () => {
    const welcomeEl = document.querySelector('.ai-message .message-content');
    if (welcomeEl && welcomeEl.textContent.trim()) {
        const fullText = welcomeEl.textContent.trim();
        typeMessage(welcomeEl, fullText);
    }
});
