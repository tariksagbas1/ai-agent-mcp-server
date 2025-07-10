const chatWindow = document.getElementById('chat-window');
const chatForm = document.getElementById('chat-form');
const userInput = document.getElementById('user-input');

function appendMessage(sender, text, isHtml = false) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${sender}`;
    if (isHtml) {
        msgDiv.innerHTML = text;
    } else {
        msgDiv.textContent = text;
    }
    chatWindow.appendChild(msgDiv);
    chatWindow.scrollTop = chatWindow.scrollHeight;
}

document.addEventListener('DOMContentLoaded', () => {
    const uuid = crypto.randomUUID();
    console.log("UUID IS :", uuid);

    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const message = userInput.value.trim();
        if (!message) return;
        appendMessage('user', message);
        userInput.value = '';
        appendMessage('agent', '...'); // loading indicator
        try {
            const res = await fetch('http://0.0.0.0:8080/agent', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    question: message,
                    session_id: uuid,
                })
            });
            const data = await res.json();
            console.log("DATA IS :", data);
            // Remove the loading indicator
            const loading = chatWindow.querySelector('.message.agent:last-child');
            if (loading && loading.textContent === '...') loading.remove();
            if (data.response) {
                const html = marked.parse(data.response);
                appendMessage('agent', html, true);
            } else if (data.error) {
                appendMessage('agent', '[Error] ' + data.error);
            } else {
                appendMessage('agent', '[No response]');
            }
        } catch (err) {
            const loading = chatWindow.querySelector('.message.agent:last-child');
            if (loading && loading.textContent === '...') loading.remove();
            appendMessage('agent', '[Network error]');
        }
    });
});
