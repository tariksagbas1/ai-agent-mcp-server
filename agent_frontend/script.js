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

async function test_mcp() {
    const payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "get_date_time",
            "arguments": {
                "timezone": "Europe/Istanbul" // or any valid timezone
            }
        }
    };
    const res = await fetch("http://0.0.0.0:8080/all_resource_templates", {
        method: "POST",
        headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json, text/event-stream'
        },
        body: JSON.stringify(payload)
    });
    const data = await res.json();
    console.log(data);
}

document.addEventListener('DOMContentLoaded', () => {
    test_mcp();
});

let allTools = [];

async function loadToolsSidebar() {
    const res = await fetch('http://0.0.0.0:8080/all_tools', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
    });
    const data = await res.json();
    allTools = data.response || [];
    const toolList = document.getElementById('tool-list');
    toolList.innerHTML = '';
    allTools.forEach((tool, idx) => {
        const li = document.createElement('li');
        li.textContent = tool.name;
        li.onclick = () => showToolDetails(idx);
        toolList.appendChild(li);
    });
}

function showToolDetails(idx) {
    const tool = allTools[idx];
    document.querySelectorAll('#tool-list li').forEach((li, i) => {
        li.classList.toggle('active', i === idx);
    });
    const details = document.getElementById('tool-details');
    let html = `<div><strong>${tool.name}</strong></div>`;
    html += `<div style="margin-bottom:8px;">${tool.description.replace(/\n/g, '<br>')}</div>`;
    html += `<form id="tool-param-form">`;
    const props = tool.inputSchema?.properties || {};
    for (const [key, val] of Object.entries(props)) {
        html += `<label for="param-${key}">${val.title || key}${tool.inputSchema.required?.includes(key) ? ' *' : ''}</label>`;
        if (val.type === 'string') {
            html += `<input type="text" id="param-${key}" name="${key}" value="${val.default || ''}" />`;
        } else if (val.type === 'integer' || val.type === 'number') {
            html += `<input type="number" id="param-${key}" name="${key}" value="${val.default || ''}" />`;
        } else if (val.type === 'boolean') {
            html += `<select id="param-${key}" name="${key}">
                        <option value="true">True</option>
                        <option value="false">False</option>
                     </select>`;
        } else if (val.type === 'array') {
            html += `<input type="text" id="param-${key}" name="${key}" placeholder="Comma-separated values" />`;
        } else {
            html += `<input type="text" id="param-${key}" name="${key}" value="${val.default || ''}" />`;
        }
    }
    html += `<button type="submit" style="margin-top:10px;">Call Tool</button>`;
    html += `</form>`;
    details.innerHTML = html;

    // Add form submit handler
    const form = document.getElementById('tool-param-form');
    form.onsubmit = async (e) => {
        e.preventDefault();
        const formData = new FormData(form);
        let args = {};
        for (const [key, val] of formData.entries()) {
            const type = props[key]?.type;
            if (type === 'integer' || type === 'number') {
                args[key] = val === '' ? null : Number(val);
            } else if (type === 'boolean') {
                args[key] = val === 'true';
            } else if (type === 'array') {
                args[key] = val.split(',').map(v => v.trim()).filter(v => v.length > 0);
            } else {
                args[key] = val;
            }
        }
        // Show result in sidebar, not chat
        const toolResultDiv = document.getElementById('tool-result');
        toolResultDiv.textContent = '...'; // loading indicator
        try {
            const payload = {
                tool_name: tool.name,
                arguments: args
            };
            const res = await fetch('http://0.0.0.0:8080/call_tool', {
                method: 'POST',
                headers: {
                    'Accept': 'application/json',
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            // Show both content and structured_content if present
            let html = '';
            if (data.result) {
                if (data.result.content) {
                    html += `<div style="margin-bottom:12px;"><strong>Content:</strong><br><pre style='white-space:pre-wrap;'>${typeof data.result.content === 'string' ? data.result.content : JSON.stringify(data.result.content, null, 2)}</pre></div>`;
                }
                if (data.result.structured_content) {
                    html += `<div><strong>Structured Content:</strong><br><pre style='white-space:pre-wrap;'>${typeof data.result.structured_content === 'string' ? data.result.structured_content : JSON.stringify(data.result.structured_content, null, 2)}</pre></div>`;
                }
                if (!data.result.content && !data.result.structured_content) {
                    html = `<pre style='white-space:pre-wrap;'>${typeof data.result === 'string' ? data.result : JSON.stringify(data.result, null, 2)}</pre>`;
                }
                toolResultDiv.innerHTML = html;
            } else if (data.error) {
                toolResultDiv.textContent = '[Error] ' + data.error;
            } else {
                toolResultDiv.textContent = '[No response]';
            }
        } catch (err) {
            toolResultDiv.textContent = '[Network error]';
        }
    };
}

document.addEventListener('DOMContentLoaded', () => {
    loadToolsSidebar();
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
