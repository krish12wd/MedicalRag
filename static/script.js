const messageInput = document.getElementById("messageInput");
const sendButton = document.getElementById("sendButton");
const chatContainer = document.getElementById("chatContainer");
const clearButton = document.getElementById("clearButton");
const historyList = document.getElementById("historyList");

let currentConversationId =
    localStorage.getItem("currentConversationId");

function addMessage(content, type, createdAt = null) {
    const welcome = document.getElementById("welcome");

    if (welcome) {
        welcome.remove();
    }

    const row = document.createElement("div");

    row.className =
        type === "user"
            ? "message-row user"
            : "message-row assistant";

    const avatar = document.createElement("div");

    avatar.className = "message-avatar";

    avatar.textContent =
        type === "user"
            ? "👤"
            : "🩺";

    const wrapper = document.createElement("div");

    wrapper.className = "message-content";

    const bubble = document.createElement("div");

    bubble.className = "message-bubble";

    bubble.textContent = content;

    wrapper.appendChild(bubble);

    if (createdAt) {
        const time = document.createElement("div");

        time.className = "message-time";

        time.textContent = formatTime(createdAt);

        wrapper.appendChild(time);
    }

    if (type === "user") {
        row.appendChild(wrapper);
        row.appendChild(avatar);
    } else {
        row.appendChild(avatar);
        row.appendChild(wrapper);
    }

    chatContainer.appendChild(row);

    scrollToBottom();
}

function formatTime(timestamp) {
    if (!timestamp) {
        return "";
    }

    const date = new Date(timestamp);

    if (Number.isNaN(date.getTime())) {
        return "";
    }

    return date.toLocaleTimeString([], {
        hour: "numeric",
        minute: "2-digit"
    });
}

function showTyping() {
    const welcome = document.getElementById("welcome");

    if (welcome) {
        welcome.remove();
    }

    const row = document.createElement("div");

    row.id = "typingMessage";
    row.className = "message-row assistant";

    row.innerHTML = `
        <div class="message-avatar">
            🩺
        </div>

        <div class="message-content">

            <div class="message-bubble">

                <div class="typing">

                    <span></span>
                    <span></span>
                    <span></span>

                </div>

            </div>

        </div>
    `;

    chatContainer.appendChild(row);

    scrollToBottom();
}

function hideTyping() {
    const typing =
        document.getElementById("typingMessage");

    if (typing) {
        typing.remove();
    }
}

function scrollToBottom() {
    chatContainer.scrollTo({
        top: chatContainer.scrollHeight,
        behavior: "smooth"
    });
}

function clearChatUI() {
    chatContainer.innerHTML = `
        <div
            id="welcome"
            class="welcome"
        >

            <div class="welcome-logo">
                🩺
            </div>

            <h2>
                Welcome to
                <span>
                    MediGuide AI
                </span>
            </h2>

            <p>
                Ask questions about the
                Standard Treatment Guidelines
                and get document-grounded answers.
            </p>

            <div class="feature-grid">

                <div class="feature-card">

                    <div class="feature-icon blue">
                        🔎
                    </div>

                    <div>

                        <strong>
                            RAG Search
                        </strong>

                        <span>
                            Searches the guideline
                            knowledge base
                        </span>

                    </div>

                </div>

                <div class="feature-card">

                    <div class="feature-icon purple">
                        ⚡
                    </div>

                    <div>

                        <strong>
                            Smart Reranking
                        </strong>

                        <span>
                            FlashRank selects the
                            most relevant content
                        </span>

                    </div>

                </div>

                <div class="feature-card">

                    <div class="feature-icon green">
                        🧠
                    </div>

                    <div>

                        <strong>
                            Agentic AI
                        </strong>

                        <span>
                            LangGraph manages
                            reasoning and tools
                        </span>

                    </div>

                </div>

            </div>

        </div>
    `;

    scrollToBottom();
}

async function sendMessage() {
    const question =
        messageInput.value.trim();

    if (!question) {
        return;
    }

    addMessage(
        question,
        "user"
    );

    messageInput.value = "";

    messageInput.style.height = "auto";

    sendButton.disabled = true;

    showTyping();

    try {
        const response = await fetch(
            "/chat",
            {
                method: "POST",

                headers: {
                    "Content-Type":
                        "application/json"
                },

                body: JSON.stringify({
                    message: question,
                    conversation_id:
                        currentConversationId
                })
            }
        );

        const data =
            await response.json();

        hideTyping();

        if (!response.ok) {
            addMessage(
                data.error ||
                "Something went wrong.",
                "assistant"
            );

            return;
        }

        if (data.error) {
            addMessage(
                data.error,
                "assistant"
            );

            return;
        }

        currentConversationId =
            data.conversation_id;

        localStorage.setItem(
            "currentConversationId",
            currentConversationId
        );

        addMessage(
            data.answer,
            "assistant"
        );

        await loadHistory();

        highlightCurrentConversation();

    } catch (error) {
        hideTyping();

        addMessage(
            "Unable to connect to the server. Please make sure the Flask application is running.",
            "assistant"
        );

        console.error(error);

    } finally {
        sendButton.disabled = false;

        messageInput.focus();
    }
}

async function loadHistory() {
    try {
        const response =
            await fetch("/history");

        if (!response.ok) {
            return;
        }

        const conversations =
            await response.json();

        historyList.innerHTML = "";

        if (!conversations.length) {
            historyList.innerHTML = `
                <div class="history-empty">
                    No conversations yet
                </div>
            `;

            return;
        }

        conversations.forEach(
            function (conversation) {

                const item =
                    document.createElement("div");

                item.className =
                    "history-item";

                if (
                    conversation.id ===
                    currentConversationId
                ) {
                    item.classList.add("active");
                }

                const openButton =
                    document.createElement("button");

                openButton.className =
                    "history-open";

                openButton.type = "button";



                const icon =
                    document.createElement("span");

                icon.className =
                    "history-icon";



                const title =
                    document.createElement("span");

                title.className =
                    "history-title";

                title.textContent =
                    conversation.title;

                openButton.appendChild(icon);

                openButton.appendChild(title);

                const deleteButton =
                    document.createElement("button");

                deleteButton.className =
                    "history-delete";

                deleteButton.type = "button";

                deleteButton.title =
                    "Delete conversation";

                deleteButton.textContent = "×";

                openButton.addEventListener(
                    "click",
                    function () {
                        openConversation(
                            conversation.id
                        );
                    }
                );

                deleteButton.addEventListener(
                    "click",
                    function (event) {

                        event.stopPropagation();

                        deleteConversation(
                            conversation.id
                        );
                    }
                );

                item.appendChild(openButton);

                item.appendChild(deleteButton);

                historyList.appendChild(item);
            }
        );

    } catch (error) {
        console.error(
            "History error:",
            error
        );
    }
}

async function openConversation(
    conversationId
) {
    try {
        const response =
            await fetch(
                `/conversation/${conversationId}`
            );

        const data =
            await response.json();

        if (!response.ok) {
            alert(
                data.error ||
                "Unable to open conversation."
            );

            return;
        }

        currentConversationId =
            data.id;

        localStorage.setItem(
            "currentConversationId",
            currentConversationId
        );

        chatContainer.innerHTML = "";

        data.messages.forEach(
            function (message) {

                addMessage(
                    message.content,

                    message.role === "user"
                        ? "user"
                        : "assistant",

                    message.created_at ||
                    message.timestamp ||
                    null
                );
            }
        );

        await loadHistory();

        scrollToBottom();

    } catch (error) {
        console.error(
            "Conversation error:",
            error
        );
    }
}

async function deleteConversation(
    conversationId
) {
    const confirmed =
        window.confirm(
            "Delete this conversation?"
        );

    if (!confirmed) {
        return;
    }

    try {
        const response =
            await fetch(
                `/conversation/${conversationId}`,
                {
                    method: "DELETE"
                }
            );

        const data =
            await response.json();

        if (!response.ok) {
            alert(
                data.error ||
                "Unable to delete conversation."
            );

            return;
        }

        if (
            currentConversationId ===
            conversationId
        ) {
            currentConversationId =
                null;

            clearChatUI();
        }

        await loadHistory();

    } catch (error) {
        console.error(
            "Delete error:",
            error
        );
    }
}

function highlightCurrentConversation() {
    document
        .querySelectorAll(".history-item")
        .forEach(
            function (item) {
                item.classList.remove("active");
            }
        );

    document
        .querySelectorAll(".history-open")
        .forEach(
            function (button) {

                const item =
                    button.closest(
                        ".history-item"
                    );

                if (!item) {
                    return;
                }

                if (
                    button.dataset.id ===
                    String(currentConversationId)
                ) {
                    item.classList.add("active");
                }
            }
        );
}

clearButton.addEventListener(
    "click",
    function () {

        currentConversationId =
            null;

        localStorage.removeItem(
            "currentConversationId"
        );

        clearChatUI();

        document
            .querySelectorAll(".history-item")
            .forEach(
                function (item) {
                    item.classList.remove("active");
                }
            );

        messageInput.focus();
    }
);

sendButton.addEventListener(
    "click",
    sendMessage
);

messageInput.addEventListener(
    "keydown",
    function (event) {

        if (
            event.key === "Enter" &&
            !event.shiftKey
        ) {

            event.preventDefault();

            sendMessage();
        }
    }
);

messageInput.addEventListener(
    "input",
    function () {

        this.style.height = "auto";

        this.style.height =
            Math.min(
                this.scrollHeight,
                120
            ) + "px";
    }
);

async function initializeApp() {

    await loadHistory();

    const savedConversationId =
        localStorage.getItem(
            "currentConversationId"
        );

    if (savedConversationId) {

        await openConversation(
            savedConversationId
        );
    }
}

initializeApp();