const messageInput = document.getElementById("messageInput");
const sendButton = document.getElementById("sendButton");
const chatContainer = document.getElementById("chatContainer");
const clearButton = document.getElementById("clearButton");
const historyList = document.getElementById("historyList");

let currentConversationId =
    localStorage.getItem("currentConversationId");

function formatAssistantMessage(content) {
    if (!content) {
        return "";
    }

    let text = String(content);

    // Normalize line endings
    text = text.replace(/\r\n/g, "\n");
    text = text.replace(/\r/g, "\n");

    // Remove excessive blank lines first
    text = text.replace(/\n\s*\n+/g, "\n");

    // Section headings
    text = text.replace(
        /^\s*(For now:|Medicine:|See a doctor if:)\s*$/gim,
        "\n$1\n"
    );

    // Convert existing -, *, • bullets to a consistent bullet
    text = text.replace(
        /^\s*[-*•]\s*/gm,
        "• "
    );

    // If the backend sends plain lines after a section heading,
    // convert each line into a bullet.
    const sectionNames = [
        "For now:",
        "Medicine:",
        "See a doctor if:"
    ];

    sectionNames.forEach(function (section) {

        const sectionRegex = new RegExp(
            section.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"),
            "i"
        );

        const match = text.match(sectionRegex);

        if (!match) {
            return;
        }

        const start = match.index + match[0].length;

        let end = text.length;

        sectionNames.forEach(function (otherSection) {

            if (
                otherSection.toLowerCase() ===
                section.toLowerCase()
            ) {
                return;
            }

            const otherRegex = new RegExp(
                otherSection.replace(
                    /[.*+?^${}()|[\]\\]/g,
                    "\\$&"
                ),
                "i"
            );

            const remaining =
                text.slice(start);

            const otherMatch =
                remaining.match(otherRegex);

            if (
                otherMatch &&
                start + otherMatch.index < end
            ) {
                end =
                    start + otherMatch.index;
            }
        });

        const before =
            text.slice(0, start);

        const sectionContent =
            text.slice(start, end)
                .trim();

        if (!sectionContent) {
            return;
        }

        // Already has bullets
        if (sectionContent.includes("•")) {
            return;
        }

        // Split each sentence into a bullet
        const points =
            sectionContent
                .split(/(?<=[.!?])\s+/)
                .map(function (item) {
                    return item.trim();
                })
                .filter(Boolean);

        if (!points.length) {
            return;
        }

        const formatted =
            "\n" +
            points
                .map(function (item) {
                    return "• " + item;
                })
                .join("\n") +
            "\n";

        text =
            before +
            formatted +
            text.slice(end);
    });

    // Make sure existing bullets are on separate lines
    text = text.replace(
        /\s*•\s*/g,
        "\n• "
    );

    // Remove excessive blank lines
    text = text.replace(
        /\n{2,}/g,
        "\n"
    );

    // Remove spaces around each line
    text = text
        .split("\n")
        .map(function (line) {
            return line.trim();
        })
        .filter(function (line) {
            return line.length > 0;
        })
        .join("\n");

    return text.trim();
}


// ============================================================
// ADD MESSAGE
// ============================================================

function addMessage(
    content,
    type,
    createdAt = null,
    showSuggestionButtons = false
) {
    const welcome =
        document.getElementById("welcome");

    if (welcome) {
        welcome.remove();
    }

    const row =
        document.createElement("div");

    row.className =
        type === "user"
            ? "message-row user"
            : "message-row assistant";

    const avatar =
        document.createElement("div");

    avatar.className =
        "message-avatar";

    avatar.textContent =
        type === "user"
            ? "👤"
            : "🩺";

    const wrapper =
        document.createElement("div");

    wrapper.className =
        "message-content";

    const bubble =
        document.createElement("div");

    bubble.className =
        "message-bubble";

    bubble.textContent =
        content;

    wrapper.appendChild(
        bubble
    );

    // ========================================================
    // TIME
    // ========================================================

    if (createdAt) {

        const time =
            document.createElement("div");

        time.className =
            "message-time";

        time.textContent =
            formatTime(createdAt);

        wrapper.appendChild(
            time
        );
    }

    // ========================================================
    // HOME REMEDY + YOGA BUTTONS
    // ========================================================

    // ========================================================
    // HOME REMEDY + YOGA BUTTONS
    // ========================================================

    if (
        type === "assistant" &&
        showSuggestionButtons &&
        currentConversationId
    ) {

        const suggestionContainer =
            document.createElement("div");

        suggestionContainer.className =
            "suggestion-buttons";

        // ----------------------------------------------------
        // HOME REMEDIES
        // ----------------------------------------------------

        const homeRemedyButton =
            document.createElement("button");

        homeRemedyButton.type =
            "button";

        homeRemedyButton.className =
            "suggestion-button";

        homeRemedyButton.textContent =
            "🌿 Suggestion for Home Remedies";

        homeRemedyButton.addEventListener(
            "click",
            function () {

                getHomeRemedySuggestions(
                    homeRemedyButton,
                    suggestionContainer
                );

            }
        );

        suggestionContainer.appendChild(
            homeRemedyButton
        );


        // ----------------------------------------------------
        // YOGA
        // ----------------------------------------------------

        const yogaButton =
            document.createElement("button");

        yogaButton.type =
            "button";

        yogaButton.className =
            "suggestion-button";

        yogaButton.textContent =
            "🧘 Suggestion for Yoga";

        yogaButton.addEventListener(
            "click",
            function () {

                getYogaSuggestions(
                    yogaButton,
                    suggestionContainer
                );

            }
        );

        suggestionContainer.appendChild(
            yogaButton
        );


        wrapper.appendChild(
            suggestionContainer
        );
    }


    // ========================================================
    // MESSAGE POSITION
    // ========================================================

    if (type === "user") {

        row.appendChild(
            wrapper
        );

        row.appendChild(
            avatar
        );

    } else {

        row.appendChild(
            avatar
        );

        row.appendChild(
            wrapper
        );
    }

    chatContainer.appendChild(
        row
    );

    scrollToBottom();
}


// ============================================================
// FORMAT TIME
// ============================================================

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


// ============================================================
// TYPING
// ============================================================

function showTyping() {
    const welcome =
        document.getElementById("welcome");

    if (welcome) {
        welcome.remove();
    }

    const row =
        document.createElement("div");

    row.id = "typingMessage";

    row.className =
        "message-row assistant";

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

    chatContainer.appendChild(
        row
    );

    scrollToBottom();
}


function hideTyping() {
    const typing =
        document.getElementById(
            "typingMessage"
        );

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


// ============================================================
// CLEAR CHAT UI
// ============================================================

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


// ============================================================
// SEND MESSAGE
// ============================================================

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

    messageInput.style.height =
        "auto";

    sendButton.disabled =
        true;

    showTyping();

    try {

        const response =
            await fetch(
                "/chat",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({
                        message:
                            question,

                        conversation_id:
                            currentConversationId
                    })
                }
            );

        const data =
            await response.json();

        hideTyping();


        // ====================================================
        // HTTP ERROR
        // ====================================================

        if (!response.ok) {

            addMessage(
                data.error ||
                "Something went wrong.",
                "assistant"
            );

            return;
        }


        // ====================================================
        // BACKEND ERROR
        // ====================================================

        if (data.error) {

            addMessage(
                data.error,
                "assistant"
            );

            return;
        }


        // ====================================================
        // SAVE CONVERSATION ID
        // ====================================================

        currentConversationId =
            data.conversation_id;

        localStorage.setItem(
            "currentConversationId",
            currentConversationId
        );


        // ====================================================
        // FINAL MEDICAL ANSWER
        //
        // IMPORTANT:
        // show_suggestions comes from Flask backend.
        // ====================================================

        addMessage(
            data.answer,
            "assistant",
            null,
            data.show_suggestions === true
        );


        await loadHistory();

        highlightCurrentConversation();

    } catch (error) {

        hideTyping();

        addMessage(
            "Unable to connect to the server. Please make sure the Flask application is running.",
            "assistant"
        );

        console.error(
            error
        );

    } finally {

        sendButton.disabled =
            false;

        messageInput.focus();
    }
}


// ============================================================
// HOME REMEDY SUGGESTIONS
// ============================================================

async function getHomeRemedySuggestions(
    button,
    buttonContainer,
    isFollowUp = false
) {

    if (!currentConversationId) {
        return;
    }

    button.disabled = true;

    button.innerHTML =
        "🌿 Loading Home Remedies...";

    try {

        const response =
            await fetch(
                "/suggestions/home-remedies",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({
                        conversation_id:
                            currentConversationId
                    })
                }
            );

        const data =
            await response.json();

        if (!response.ok) {

            throw new Error(
                data.error ||
                "Unable to get home remedy suggestions."
            );
        }

        // Remove clicked button container
        buttonContainer.remove();


        // ====================================================
        // HOME REMEDIES CLICKED
        //
        // If this is the FIRST suggestion:
        // show Yoga.
        //
        // If this is the SECOND suggestion:
        // show nothing.
        // ====================================================

        if (!isFollowUp) {

            addSuggestionResult(
                data.suggestions,
                "yoga"
            );

        } else {

            addSuggestionResult(
                data.suggestions,
                null
            );
        }

    } catch (error) {

        console.error(
            "Home remedy error:",
            error
        );

        button.disabled = false;

        button.innerHTML =
            "🌿 Try Home Remedies Again";
    }
}


// ============================================================
// YOGA SUGGESTIONS
// ============================================================

async function getYogaSuggestions(
    button,
    buttonContainer,
    isFollowUp = false
) {

    if (!currentConversationId) {
        return;
    }

    button.disabled = true;

    button.innerHTML =
        "🧘 Finding Yoga...";

    try {

        const response =
            await fetch(
                "/suggestions/yoga",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({
                        conversation_id:
                            currentConversationId
                    })
                }
            );

        const data =
            await response.json();

        if (!response.ok) {

            throw new Error(
                data.error ||
                "Unable to get yoga suggestions."
            );
        }

        // Remove clicked button container
        buttonContainer.remove();


        // ====================================================
        // YOGA CLICKED
        //
        // If this is the FIRST suggestion:
        // show Home Remedies.
        //
        // If this is the SECOND suggestion:
        // show nothing.
        // ====================================================

        if (!isFollowUp) {

            addSuggestionResult(
                data.suggestions,
                "home_remedy"
            );

        } else {

            addSuggestionResult(
                data.suggestions,
                null
            );
        }

    } catch (error) {

        console.error(
            "Yoga error:",
            error
        );

        button.disabled = false;

        button.innerHTML =
            "🧘 Try Yoga Suggestions Again";
    }
}


// ============================================================
// LOAD HISTORY
// ============================================================

async function loadHistory() {

    try {

        const response =
            await fetch(
                "/history"
            );

        if (!response.ok) {
            return;
        }

        const conversations =
            await response.json();

        historyList.innerHTML =
            "";

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
                    document.createElement(
                        "div"
                    );

                item.className =
                    "history-item";

                if (
                    conversation.id ===
                    currentConversationId
                ) {
                    item.classList.add(
                        "active"
                    );
                }

                const openButton =
                    document.createElement(
                        "button"
                    );

                openButton.className =
                    "history-open";

                openButton.type =
                    "button";

                openButton.dataset.id =
                    conversation.id;


                const icon =
                    document.createElement(
                        "span"
                    );

                icon.className =
                    "history-icon";


                const title =
                    document.createElement(
                        "span"
                    );

                title.className =
                    "history-title";

                title.textContent =
                    conversation.title;

                openButton.appendChild(
                    icon
                );

                openButton.appendChild(
                    title
                );


                const deleteButton =
                    document.createElement(
                        "button"
                    );

                deleteButton.className =
                    "history-delete";

                deleteButton.type =
                    "button";

                deleteButton.title =
                    "Delete conversation";

                deleteButton.textContent =
                    "×";


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


                item.appendChild(
                    openButton
                );

                item.appendChild(
                    deleteButton
                );

                historyList.appendChild(
                    item
                );
            }
        );

    } catch (error) {

        console.error(
            "History error:",
            error
        );
    }
}


// ============================================================
// ADD SUGGESTION RESULT
// ============================================================

function addSuggestionResult(
    content,
    nextSuggestion = null
) {

    const row =
        document.createElement("div");

    row.className =
        "message-row assistant";


    // ========================================================
    // AVATAR
    // ========================================================

    const avatar =
        document.createElement("div");

    avatar.className =
        "message-avatar";

    avatar.textContent =
        "🩺";


    // ========================================================
    // WRAPPER
    // ========================================================

    const wrapper =
        document.createElement("div");

    wrapper.className =
        "message-content";


    // ========================================================
    // RESPONSE
    // ========================================================

    const bubble =
        document.createElement("div");

    bubble.className =
        "message-bubble";

    bubble.textContent =
        content;

    wrapper.appendChild(
        bubble
    );


    // ========================================================
    // NEXT SUGGESTION
    // ========================================================

    if (
        nextSuggestion === "yoga"
        ||
        nextSuggestion === "home_remedy"
    ) {

        const suggestionContainer =
            document.createElement("div");

        suggestionContainer.className =
            "suggestion-buttons";


        const nextButton =
            document.createElement("button");

        nextButton.type =
            "button";

        nextButton.className =
            "suggestion-button";


        // ====================================================
        // HOME → YOGA
        // ====================================================

        if (
            nextSuggestion === "yoga"
        ) {

            nextButton.textContent =
                "🧘 Suggestion for Yoga";

            nextButton.addEventListener(
                "click",
                function () {

                    // IMPORTANT:
                    // true = this is the SECOND suggestion
                    getYogaSuggestions(
                        nextButton,
                        suggestionContainer,
                        true
                    );

                }
            );
        }


        // ====================================================
        // YOGA → HOME
        // ====================================================

        else if (
            nextSuggestion === "home_remedy"
        ) {

            nextButton.textContent =
                "🌿 Suggestion for Home Remedies";

            nextButton.addEventListener(
                "click",
                function () {

                    // IMPORTANT:
                    // true = this is the SECOND suggestion
                    getHomeRemedySuggestions(
                        nextButton,
                        suggestionContainer,
                        true
                    );

                }
            );
        }


        suggestionContainer.appendChild(
            nextButton
        );

        wrapper.appendChild(
            suggestionContainer
        );
    }


    // ========================================================
    // MESSAGE POSITION
    // ========================================================

    row.appendChild(
        avatar
    );

    row.appendChild(
        wrapper
    );

    chatContainer.appendChild(
        row
    );

    scrollToBottom();
}

// ============================================================
// OPEN CONVERSATION
// ============================================================

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

        chatContainer.innerHTML =
            "";

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


// ============================================================
// DELETE CONVERSATION
// ============================================================

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


// ============================================================
// HIGHLIGHT CURRENT CONVERSATION
// ============================================================

function highlightCurrentConversation() {

    document
        .querySelectorAll(
            ".history-item"
        )
        .forEach(
            function (item) {

                item.classList.remove(
                    "active"
                );
            }
        );


    document
        .querySelectorAll(
            ".history-open"
        )
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
                    String(
                        currentConversationId
                    )
                ) {

                    item.classList.add(
                        "active"
                    );
                }
            }
        );
}


// ============================================================
// CLEAR BUTTON
// ============================================================

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
            .querySelectorAll(
                ".history-item"
            )
            .forEach(
                function (item) {

                    item.classList.remove(
                        "active"
                    );
                }
            );

        messageInput.focus();
    }
);


// ============================================================
// SEND BUTTON
// ============================================================

sendButton.addEventListener(
    "click",
    sendMessage
);


// ============================================================
// ENTER TO SEND
// ============================================================

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


// ============================================================
// AUTO RESIZE TEXTAREA
// ============================================================

messageInput.addEventListener(
    "input",
    function () {

        this.style.height =
            "auto";

        this.style.height =
            Math.min(
                this.scrollHeight,
                120
            ) + "px";
    }
);


// ============================================================
// INITIALIZE APP
// ============================================================

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



// ============================================================
// BLOOD REPORT PDF UPLOAD
// DIGITAL PDF ONLY
// ============================================================

const uploadButton =
    document.getElementById(
        "uploadButton"
    );

const uploadMenu =
    document.getElementById(
        "uploadMenu"
    );

const uploadPdfButton =
    document.getElementById(
        "uploadPdfButton"
    );

const bloodReportPdfInput =
    document.getElementById(
        "bloodReportPdfInput"
    );


// ============================================================
// OPEN / CLOSE MENU
// ============================================================

function toggleUploadMenu() {

    if (!uploadMenu) {
        return;
    }

    uploadMenu.classList.toggle(
        "show"
    );
}


function closeUploadMenu() {

    if (!uploadMenu) {
        return;
    }

    uploadMenu.classList.remove(
        "show"
    );
}


// ============================================================
// PLUS BUTTON
// ============================================================

if (uploadButton) {

    uploadButton.addEventListener(
        "click",
        function (event) {

            event.stopPropagation();

            toggleUploadMenu();

        }
    );
}


// ============================================================
// PDF BUTTON
// ============================================================

if (uploadPdfButton) {

    uploadPdfButton.addEventListener(
        "click",
        function () {

            closeUploadMenu();

            bloodReportPdfInput.click();

        }
    );
}


// ============================================================
// CLOSE MENU WHEN CLICKING OUTSIDE
// ============================================================

document.addEventListener(
    "click",
    function (event) {

        if (
            uploadMenu &&
            uploadButton &&
            !uploadMenu.contains(
                event.target
            ) &&
            !uploadButton.contains(
                event.target
            )
        ) {

            closeUploadMenu();

        }

    }
);


// ============================================================
// PDF SELECTED
// ============================================================

if (bloodReportPdfInput) {

    bloodReportPdfInput.addEventListener(
        "change",
        function () {

            if (
                bloodReportPdfInput.files &&
                bloodReportPdfInput.files.length > 0
            ) {

                uploadBloodReport(
                    bloodReportPdfInput.files[0]
                );

            }

            bloodReportPdfInput.value =
                "";

        }
    );
}


// ============================================================
// ADD BLOOD REPORT RESULT
// ============================================================

function addBloodReportResult(content) {

    if (!content) {

        addMessage(
            "The blood report was uploaded, but no analysis was returned.",
            "assistant"
        );

        return;
    }

    const row =
        document.createElement("div");

    row.className =
        "message-row assistant";


    // ========================================================
    // AVATAR
    // ========================================================

    const avatar =
        document.createElement("div");

    avatar.className =
        "message-avatar";

    avatar.textContent =
        "🩺";


    // ========================================================
    // WRAPPER
    // ========================================================

    const wrapper =
        document.createElement("div");

    wrapper.className =
        "message-content";


    // ========================================================
    // BLOOD REPORT RESULT
    // ========================================================

    const bubble =
        document.createElement("div");

    bubble.className =
        "message-bubble blood-report-result";

    bubble.textContent =
        content;


    wrapper.appendChild(
        bubble
    );


    // ========================================================
    // TIME
    // ========================================================

    const time =
        document.createElement("div");

    time.className =
        "message-time";

    time.textContent =
        formatTime(
            new Date().toISOString()
        );

    wrapper.appendChild(
        time
    );


    // ========================================================
    // MESSAGE POSITION
    // ========================================================

    row.appendChild(
        avatar
    );

    row.appendChild(
        wrapper
    );

    chatContainer.appendChild(
        row
    );


    // ========================================================
    // SCROLL
    // ========================================================

    scrollToBottom();
}

// ============================================================
// UPLOAD BLOOD REPORT
// ============================================================

async function uploadBloodReport(
    file
) {

    if (!file) {
        return;
    }


    // ========================================================
    // PDF ONLY
    // ========================================================

    const isPdf =
        file.type === "application/pdf"
        ||
        file.name
            .toLowerCase()
            .endsWith(".pdf");


    if (!isPdf) {

        addMessage(
            "Please upload a digital PDF blood report.",
            "assistant"
        );

        return;
    }


    // ========================================================
    // 15 MB LIMIT
    // ========================================================

    if (
        file.size >
        15 * 1024 * 1024
    ) {

        addMessage(
            "The blood report PDF must be smaller than 15 MB.",
            "assistant"
        );

        return;
    }


    // ========================================================
    // SHOW USER UPLOAD
    // ========================================================

    addMessage(
        "📎 Uploaded blood report: " +
        file.name,
        "user"
    );


    showTyping();


    if (uploadButton) {

        uploadButton.disabled =
            true;

    }

    if (sendButton) {

        sendButton.disabled =
            true;

    }


    // ========================================================
    // FORM DATA
    // ========================================================

    const formData =
        new FormData();

    formData.append(
        "report",
        file
    );

    if (currentConversationId) {

        formData.append(
            "conversation_id",
            currentConversationId
        );
    }


    try {

        const response =
            await fetch(
                "/analyze-report",
                {
                    method: "POST",
                    body: formData,
                    credentials: "same-origin"
                }
            );


        // ====================================================
        // READ RESPONSE SAFELY
        // ====================================================

        const contentType =
            response.headers.get(
                "content-type"
            ) || "";


        if (
            !contentType.includes(
                "application/json"
            )
        ) {

            hideTyping();

            addMessage(
                "The server returned an unexpected response. Please refresh the page and try again.",
                "assistant"
            );

            console.error(
                "Unexpected server response:",
                await response.text()
            );

            return;
        }


        const data =
            await response.json();


        hideTyping();


        // ====================================================
        // SERVER ERROR
        // ====================================================

        if (!response.ok) {

            addMessage(
                data.error ||
                "Unable to analyze the blood report.",
                "assistant"
            );

            return;
        }


        // ====================================================
        // APPLICATION ERROR
        // ====================================================

        if (data.error) {

            addMessage(
                data.error,
                "assistant"
            );

            return;
        }


        // ====================================================
        // REPORT RESULT
        // ====================================================

        if (data.conversation_id) {

            currentConversationId =
                data.conversation_id;

            localStorage.setItem(
                "currentConversationId",
                currentConversationId
            );
        }

        addBloodReportResult(
            data.analysis
        );

        await loadHistory();

        highlightCurrentConversation();

    } catch (error) {

        hideTyping();

        console.error(
            "Blood report upload error:",
            error
        );

        addMessage(
            "Unable to connect to the server. Please try again.",
            "assistant"
        );

    } finally {

        if (uploadButton) {

            uploadButton.disabled =
                false;

        }

        if (sendButton) {

            sendButton.disabled =
                false;

        }

    }
}


initializeApp();