const messageInput = document.getElementById("messageInput");
const sendButton = document.getElementById("sendButton");
const chatContainer = document.getElementById("chatContainer");
const clearButton = document.getElementById("clearButton");
const historyList = document.getElementById("historyList");

// ============================================================
// SPEECH TO TEXT
// ============================================================

const SpeechRecognition =
    window.SpeechRecognition ||
    window.webkitSpeechRecognition;

let speechRecognition = null;
let isListening = false;
let manualStop = false;
let silenceTimer = null;

// ------------------------------------------------------------
// CREATE MIC BUTTON
// ------------------------------------------------------------

const micButton = document.createElement("button");

micButton.type = "button";
micButton.id = "micButton";
micButton.className = "mic-button";
micButton.title = "Use voice input";
micButton.setAttribute("aria-label", "Use voice input");
micButton.innerHTML = '<i class="fa fa-microphone" aria-hidden="true"></i>';

// Insert mic before send button
sendButton.parentNode.insertBefore(
    micButton,
    sendButton
);


// ============================================================
// BROWSER SUPPORT CHECK
// ============================================================

if (!SpeechRecognition) {

    console.warn(
        "Speech recognition is not supported in this browser."
    );

    micButton.disabled = true;
    micButton.title =
        "Voice input is not supported in this browser";

    micButton.style.opacity = "0.45";
    micButton.style.cursor = "not-allowed";

} else {

    // --------------------------------------------------------
    // CREATE SPEECH RECOGNITION
    // --------------------------------------------------------

    speechRecognition =
        new SpeechRecognition();

    speechRecognition.continuous = true;
    speechRecognition.interimResults = false;
    speechRecognition.lang = "en-IN";


    // ========================================================
    // VOICE BAR
    // ========================================================

    function createVoiceBar() {

        const bar =
            document.createElement("div");

        bar.className =
            "voice-listening-bar";

        bar.id =
            "voiceListeningBar";

        bar.innerHTML = `
            <button
                type="button"
                class="voice-cancel-button"
                id="voiceCancelButton"
                title="Cancel">
                ×
            </button>

            <div class="voice-wave">
                <span></span>
                <span></span>
                <span></span>
                <span></span>
                <span></span>
                <span></span>
                <span></span>
                <span></span>
                <span></span>
                <span></span>
            </div>

            <button
                type="button"
                class="voice-stop-button"
                id="voiceStopButton"
                title="Stop listening">
                ■
            </button>
        `;

        return bar;
    }


    function showVoiceBar() {

        const container =
            sendButton.parentNode;

        const existingBar =
            document.getElementById(
                "voiceListeningBar"
            );

        // Prevent duplicate bars
        if (existingBar) {
            return;
        }

        const bar =
            createVoiceBar();

        messageInput.style.display =
            "none";

        micButton.style.display =
            "none";

        sendButton.style.display =
            "none";

        container.insertBefore(
            bar,
            sendButton
        );


        // ----------------------------------------------------
        // STOP
        // ----------------------------------------------------

        document
            .getElementById("voiceStopButton")
            .addEventListener(
                "click",
                function () {

                    manualStop = true;
                    clearTimeout(silenceTimer);

                    try {
                        speechRecognition.stop();
                    } catch (error) {
                        console.log(
                            "Speech stop error:",
                            error
                        );

                        isListening = false;

                        hideVoiceBar();
                    }
                }
            );


        // ----------------------------------------------------
        // CANCEL
        // ----------------------------------------------------

        document
            .getElementById("voiceCancelButton")
            .addEventListener(
                "click",
                function () {

                    manualStop = true;
                    clearTimeout(silenceTimer);

                    try {
                        speechRecognition.abort();
                    } catch (error) {
                        console.log(
                            "Speech abort error:",
                            error
                        );
                    }

                    messageInput.value = "";

                    isListening = false;

                    hideVoiceBar();
                }
            );
    }


    function hideVoiceBar() {

        const bar =
            document.getElementById(
                "voiceListeningBar"
            );

        if (bar) {
            bar.remove();
        }

        messageInput.style.display =
            "";

        micButton.style.display =
            "";

        sendButton.style.display =
            "";

        messageInput.focus();
    }


    // ========================================================
    // MIC CLICK
    // ========================================================

    micButton.addEventListener(
        "click",
        function () {

            if (!speechRecognition) {
                return;
            }


            // ----------------------------------------------
            // STOP CURRENT LISTENING
            // ----------------------------------------------

            if (isListening) {

                manualStop = true;
                clearTimeout(silenceTimer);

                try {
                    speechRecognition.stop();
                } catch (error) {
                    console.log(
                        "Speech stop error:",
                        error
                    );
                }

                return;
            }


            // ----------------------------------------------
            // START LISTENING
            // ----------------------------------------------

            manualStop = false;
            messageInput.value = "";

            try {

                speechRecognition.start();

            } catch (error) {

                console.error(
                    "Speech recognition start error:",
                    error
                );

                isListening = false;

                hideVoiceBar();
            }
        }
    );


    // ========================================================
    // ON START
    // ========================================================

    speechRecognition.onstart =
        function () {

            console.log(
                "Speech recognition started."
            );

            isListening = true;

            micButton.classList.add(
                "listening"
            );

            showVoiceBar();

            // Start 15-second timer immediately.
            // If user says nothing, stop automatically.
            clearTimeout(silenceTimer);

            silenceTimer =
                setTimeout(
                    function () {

                        if (isListening) {

                            manualStop = true;

                            try {
                                speechRecognition.stop();
                            } catch (error) {

                                console.log(
                                    "Speech silence timeout:",
                                    error
                                );

                                isListening = false;
                                hideVoiceBar();
                            }
                        }

                    },
                    7000
                );
        };


    // ========================================================
    // ON RESULT
    // ========================================================

    speechRecognition.onresult =
        function (event) {

            let transcript = "";

            for (
                let i = event.resultIndex;
                i < event.results.length;
                i++
            ) {

                if (
                    event.results[i].isFinal
                ) {

                    transcript +=
                        event.results[i][0]
                            .transcript + " ";
                }
            }


            transcript =
                transcript.trim();


            if (!transcript) {
                return;
            }


            // Replace the current voice-session text
            messageInput.value =
                transcript;


            // Reset 15-second silence timer whenever speech is received
            clearTimeout(silenceTimer);

            silenceTimer =
                setTimeout(
                    function () {

                        if (isListening) {

                            manualStop = true;

                            try {

                                speechRecognition.stop();

                            } catch (error) {

                                console.log(
                                    "Speech silence timeout:",
                                    error
                                );

                                isListening = false;

                                hideVoiceBar();
                            }
                        }

                    },
                    7000
                );


            // Trigger input event if needed
            messageInput.dispatchEvent(
                new Event(
                    "input",
                    {
                        bubbles: true
                    }
                )
            );
        };


    // ========================================================
    // ON END
    // ========================================================

    speechRecognition.onend =
        function () {

            console.log(
                "Speech recognition ended."
            );
            clearTimeout(silenceTimer);


            // Browser automatically stopped
            // but user didn't press stop/cancel.
            if (
                isListening &&
                !manualStop
            ) {

                setTimeout(
                    function () {

                        if (!isListening) {
                            return;
                        }

                        try {

                            speechRecognition.start();

                        } catch (error) {

                            console.log(
                                "Speech recognition restart:",
                                error
                            );

                            isListening = false;

                            micButton.classList.remove(
                                "listening"
                            );

                            hideVoiceBar();
                        }

                    },
                    150
                );

                return;
            }


            isListening = false;

            micButton.classList.remove(
                "listening"
            );

            hideVoiceBar();
        };


    speechRecognition.onerror =
        function (event) {

            console.error(
                "SPEECH RECOGNITION ERROR:",
                event.error
            );


            // ----------------------------------------------
            // NO SPEECH
            // ----------------------------------------------

            if (
                event.error ===
                "no-speech"
            ) {

                console.warn(
                    "No speech detected. Waiting for 7-second timer."
                );

                return;
            }


            isListening = false;

            micButton.classList.remove(
                "listening"
            );


            // ----------------------------------------------
            // PERMISSION DENIED
            // ----------------------------------------------

            if (
                event.error ===
                "not-allowed"
            ) {

                micButton.title =
                    "Microphone permission denied. Allow microphone access in browser settings.";

                console.warn(
                    "Microphone permission was denied."
                );
            }


            // ----------------------------------------------
            // AUDIO CAPTURE ERROR
            // ----------------------------------------------

            else if (
                event.error ===
                "audio-capture"
            ) {

                micButton.title =
                    "Microphone could not be accessed.";

                console.warn(
                    "Microphone/audio capture failed."
                );
            }


            // ----------------------------------------------
            // NETWORK ERROR
            // ----------------------------------------------

            else if (
                event.error ===
                "network"
            ) {

                console.warn(
                    "Speech recognition network error."
                );
            }


            hideVoiceBar();
        };
}

// ============================================================
// PROFILE MENU
// ============================================================

async function initProfileMenu() {

    const onlineStatus =
        document.querySelector(
            ".online-status"
        );

    if (!onlineStatus) {
        return;
    }

    try {

        const response =
            await fetch(
                "/profile"
            );

        if (!response.ok) {
            return;
        }

        const data =
            await response.json();

        if (
            !data.success ||
            !data.user
        ) {
            return;
        }

        const user =
            data.user;

        const initial =
            (
                user.name ||
                "U"
            )
                .trim()
                .charAt(0)
                .toUpperCase();

        const wrapper =
            document.createElement(
                "div"
            );

        wrapper.className =
            "profile-menu-wrapper";

        wrapper.innerHTML = `

            <button
                type="button"
                class="profile-avatar-button"
                title="Account"
            >
                ${escapeHtml(initial)}
            </button>

            <div
                class="profile-dropdown"
            >

                <button
                    type="button"
                    class="profile-menu-item"
                    data-action="profile"
                >
                    <span>👤</span>
                    <span>Profile</span>
                </button>

                <button
                    type="button"
                    class="profile-menu-item"
                    data-action="bookings"
                >
                    <span>📅</span>
                    <span>My Bookings</span>
                </button>

                <button
                    type="button"
                    class="profile-menu-item"
                    data-action="diet"
                >
                    <span>🥗</span>
                    <span>Diet Planning</span>
                </button>
                <div class="profile-menu-divider"></div>

                <button
                    type="button"
                    class="profile-menu-item logout"
                    data-action="logout"
                >
                    <span>↪</span>
                    <span>Logout</span>
                </button>

            </div>
        `;

        onlineStatus.replaceWith(
            wrapper
        );

        const avatar =
            wrapper.querySelector(
                ".profile-avatar-button"
            );

        const dropdown =
            wrapper.querySelector(
                ".profile-dropdown"
            );

        avatar.addEventListener(
            "click",
            function (event) {

                event.stopPropagation();

                dropdown.classList.toggle(
                    "show"
                );
            }
        );

        wrapper.querySelector(
            '[data-action="profile"]'
        ).addEventListener(
            "click",
            function () {

                dropdown.classList.remove(
                    "show"
                );

                localStorage.setItem(
                    "activeDashboard",
                    "profile"
                );

                openProfileDashboard(
                    user
                );
            }
        );

        wrapper.querySelector(
            '[data-action="bookings"]'
        ).addEventListener(
            "click",
            function () {

                dropdown.classList.remove(
                    "show"
                );

                localStorage.setItem(
                    "activeDashboard",
                    "bookings"
                );

                openMyBookingsDashboard();
            }
        );

        wrapper.querySelector(
            '[data-action="diet"]'
        ).addEventListener(
            "click",
            function () {

                dropdown.classList.remove(
                    "show"
                );

                localStorage.setItem(
                    "activeDashboard",
                    "diet"
                );

                openDietPlanningDashboard();
            }
        );

        wrapper.querySelector(
            '[data-action="logout"]'
        ).addEventListener(
            "click",
            function () {

                window.location.href =
                    "/logout";
            }
        );

        document.addEventListener(
            "click",
            function () {

                dropdown.classList.remove(
                    "show"
                );
            }
        );

    } catch (error) {

        console.error(
            "PROFILE MENU ERROR:",
            error
        );
    }
}

// ============================================================
// PROFILE DASHBOARD
// ============================================================

function openProfileDashboard(
    user
) {

    const overlay =
        document.createElement(
            "div"
        );

    overlay.className =
        "profile-dashboard-overlay";

    overlay.innerHTML = `

        <div class="profile-dashboard">

            <div class="profile-dashboard-header">

                <div>
                    <h2>
                        Profile
                    </h2>

                    <p>
                        Manage your account
                        information.
                    </p>
                </div>

                <button
                    type="button"
                    class="profile-dashboard-close"
                >
                    ×
                </button>

            </div>

            <div class="profile-dashboard-body">

                <div class="profile-info-card">

                    <div class="profile-large-avatar">
                        ${escapeHtml(
        (
            user.name ||
            "U"
        )
            .charAt(0)
            .toUpperCase()
    )}
                    </div>

                    <div>

                        <h3>
                            ${escapeHtml(
        user.name
    )}
                        </h3>

                        <p>
                            ${escapeHtml(
        user.email
    )}
                        </p>

                    </div>

                </div>

                <div class="password-card">

                    <h3>
                        Change Password
                    </h3>

                    <p>
                        Enter your current password
                        and choose a new password.
                    </p>

                    <form
                        id="changePasswordForm"
                        class="change-password-form"
                    >

                        <label>
                            Old Password
                        </label>

                        <input
                            type="password"
                            id="oldPassword"
                            required
                        >

                        <label>
                            New Password
                        </label>

                        <input
                            type="password"
                            id="newPassword"
                            required
                        >

                        <label>
                            Re-enter New Password
                        </label>

                        <input
                            type="password"
                            id="confirmNewPassword"
                            required
                        >

                        <button
                            type="submit"
                            class="profile-primary-button"
                        >
                            Change Password
                        </button>

                    </form>

                </div>

            </div>

        </div>
    `;

    document.body.appendChild(
        overlay
    );

    overlay.querySelector(
        ".profile-dashboard-close"
    ).addEventListener(
        "click",
        function () {

            overlay.remove();

            localStorage.removeItem(
                "activeDashboard"
            );

        }
    );

    overlay.querySelector(
        "#changePasswordForm"
    ).addEventListener(
        "submit",
        async function (event) {

            event.preventDefault();

            const button =
                this.querySelector(
                    "button[type='submit']"
                );

            button.disabled =
                true;

            button.textContent =
                "Changing...";

            try {

                const response =
                    await fetch(
                        "/change-password",
                        {
                            method: "POST",

                            headers: {
                                "Content-Type":
                                    "application/json"
                            },

                            body:
                                JSON.stringify({

                                    old_password:
                                        document
                                            .getElementById(
                                                "oldPassword"
                                            )
                                            .value,

                                    new_password:
                                        document
                                            .getElementById(
                                                "newPassword"
                                            )
                                            .value,

                                    confirm_password:
                                        document
                                            .getElementById(
                                                "confirmNewPassword"
                                            )
                                            .value,
                                })
                        }
                    );

                const data =
                    await response.json();

                if (!response.ok) {

                    throw new Error(
                        data.error ||
                        "Unable to change password."
                    );
                }

                alert(
                    "Password changed successfully. Please log in again."
                );

                window.location.href =
                    "/login";

            } catch (error) {

                alert(
                    error.message
                );

                button.disabled =
                    false;

                button.textContent =
                    "Change Password";
            }
        }
    );
}


// ============================================================
// MY BOOKINGS DASHBOARD
// ============================================================

async function openMyBookingsDashboard() {

    const overlay =
        document.createElement(
            "div"
        );

    overlay.className =
        "profile-dashboard-overlay";

    overlay.innerHTML = `

        <div class="profile-dashboard bookings-dashboard">

            <div class="profile-dashboard-header">

                <div>
                    <h2>
                        My Bookings
                    </h2>

                    <p>
                        View and manage your appointments.
                    </p>
                </div>

                <button
                    type="button"
                    class="profile-dashboard-close"
                >
                    ×
                </button>

            </div>

            <div
                id="myBookingsContainer"
                class="my-bookings-container"
            >

                <div class="appointment-loading">
                    <div class="loading-spinner"></div>
                    <div class="loading-text">
                        Loading bookings...
                    </div>
                </div>

            </div>

        </div>
    `;

    document.body.appendChild(
        overlay
    );

    overlay.querySelector(
        ".profile-dashboard-close"
    ).addEventListener(
        "click",
        function () {

            overlay.remove();

            localStorage.removeItem(
                "activeDashboard"
            );

        }
    );

    await loadMyBookings(
        overlay
    );
}

// ============================================================
// DIET PLANNING DASHBOARD
// ============================================================

async function openDietPlanningDashboard() {

    const overlay =
        document.createElement(
            "div"
        );

    overlay.className =
        "profile-dashboard-overlay";

    overlay.innerHTML = `

        <div class="diet-dashboard">

            <div class="profile-dashboard-header">

                <div>
                    <h2>
                        Diet Planning
                    </h2>

                    <p>
                        Let's create your personalized 7-day diet plan.
                    </p>
                </div>

                <button
                    type="button"
                    class="diet-back-button"
                >
                    ×
                </button>

            </div>

            <div
                id="dietChatContainer"
                class="diet-chat-container"
            ></div>

            <form
                id="dietChatForm"
                class="diet-chat-form"
            >

                <input
                    type="text"
                    id="dietChatInput"
                    placeholder="Type your answer..."
                    autocomplete="off"
                    required
                >

                <button
                    type="submit"
                >
                    ➤
                </button>

            </form>

        </div>
    `;

    document.body.appendChild(
        overlay
    );

    const chat =
        overlay.querySelector(
            "#dietChatContainer"
        );

    const input =
        overlay.querySelector(
            "#dietChatInput"
        );

    const form =
        overlay.querySelector(
            "#dietChatForm"
        );

    const closeButton =
        overlay.querySelector(
            ".diet-back-button"
        );

    closeButton.addEventListener(
        "click",
        function () {

            overlay.remove();

            localStorage.removeItem(
                "activeDashboard"
            );

        }
    );

    const fields = [
        "age",
        "gender",
        "height",
        "weight",
        "medical_condition",
        "allergies",
        "medications",
        "dietary_preference",
        "goal"
    ];

    const answers = {};

    let currentIndex = 0;

    const history = [];

    function addDietMessage(
        content,
        type
    ) {

        const row =
            document.createElement(
                "div"
            );

        row.className =
            "diet-message " +
            type;

        row.textContent =
            content;

        chat.appendChild(
            row
        );

        chat.scrollTop =
            chat.scrollHeight;
    }

    async function askNextQuestion() {

        if (
            currentIndex >=
            fields.length
        ) {

            await generateDietPlan();

            return;
        }

        const field =
            fields[currentIndex];

        try {

            const response =
                await fetch(
                    "/diet-question",
                    {
                        method: "POST",

                        headers: {
                            "Content-Type":
                                "application/json"
                        },

                        body:
                            JSON.stringify({
                                field:
                                    field,

                                history:
                                    history
                            })
                    }
                );

            const data =
                await response.json();

            if (!response.ok) {

                throw new Error(
                    data.error ||
                    "Unable to continue diet consultation."
                );
            }

            addDietMessage(
                data.question,
                "assistant"
            );

            input.focus();

        } catch (error) {

            addDietMessage(
                error.message,
                "assistant"
            );
        }
    }

    form.addEventListener(
        "submit",
        async function (event) {

            event.preventDefault();

            const answer =
                input.value.trim();

            if (!answer) {
                return;
            }

            const field =
                fields[currentIndex];

            addDietMessage(
                answer,
                "user"
            );

            history.push({
                field:
                    field,

                answer:
                    answer
            });

            answers[field] =
                answer;

            input.value = "";

            currentIndex++;

            if (
                currentIndex <
                fields.length
            ) {

                await askNextQuestion();

            } else {

                await generateDietPlan();

            }

        }
    );

    async function generateDietPlan() {

        input.disabled =
            true;

        const submitButton =
            form.querySelector(
                "button"
            );

        submitButton.disabled =
            true;

        addDietMessage(
            "Preparing your personalized diet plan...",
            "assistant"
        );

        try {

            const response =
                await fetch(
                    "/diet-plan",
                    {
                        method: "POST",

                        headers: {
                            "Content-Type":
                                "application/json"
                        },

                        body:
                            JSON.stringify({
                                answers:
                                    answers,

                                history:
                                    history
                            })
                    }
                );

            const data =
                await response.json();

            if (!response.ok) {

                throw new Error(
                    data.error ||
                    "Unable to generate diet plan."
                );
            }

            addDietMessage(
                "BMI: " +
                data.bmi +
                "\n" +
                "BMI Category: " +
                data.bmi_category +
                "\n\n" +
                "Estimated Daily Calorie Intake: " +
                data.daily_calories +
                " kcal/day",
                "assistant"
            );

            addDietMessage(
                data.diet_plan,
                "assistant"
            );

            addDietMessage(
                data.email_sent
                    ? "📧 Your 7-day diet plan has also been sent to your registered email."
                    : "Your diet plan was generated, but the email could not be sent.",
                "assistant"
            );

            input.style.display =
                "none";

            submitButton.style.display =
                "none";

        } catch (error) {

            addDietMessage(
                error.message,
                "assistant"
            );

            input.disabled =
                false;

            submitButton.disabled =
                false;
        }
    }

    await askNextQuestion();
}

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

function formatBloodReport(content) {
    let html = content;

    // Escape HTML first for safety
    html = html
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");

    // Main title
    html = html.replace(
        /^# 🩺 Blood Report Summary$/gm,
        '<h1 class="blood-report-title">🩺 Blood Report Summary</h1>'
    );

    // Section headings
    html = html.replace(
        /^## (.+)$/gm,
        '<h2 class="blood-report-heading">$1</h2>'
    );

    // Bold
    html = html.replace(
        /\*\*(.+?)\*\*/g,
        '<strong>$1</strong>'
    );

    // Markdown table
    html = html.replace(
        /((?:^\|.*\|\n?)+)/gm,
        function (tableBlock) {
            const lines = tableBlock
                .trim()
                .split("\n")
                .filter(line => line.trim());

            if (lines.length < 2) return tableBlock;

            const header = lines[0]
                .split("|")
                .slice(1, -1)
                .map(cell => cell.trim());

            const rows = lines
                .slice(2)
                .map(line =>
                    line
                        .split("|")
                        .slice(1, -1)
                        .map(cell => cell.trim())
                );

            let table =
                '<div class="blood-table-wrapper">' +
                '<table class="blood-report-table">' +
                '<thead><tr>';

            header.forEach(cell => {
                table += `<th>${cell}</th>`;
            });

            table += '</tr></thead><tbody>';

            rows.forEach(row => {
                table += "<tr>";

                row.forEach(cell => {
                    table += `<td>${cell}</td>`;
                });

                table += "</tr>";
            });

            table += '</tbody></table></div>';

            return table;
        }
    );

    // Bullet points
    html = html.replace(
        /(?:^|\n)- (.+)/g,
        '<li>$1</li>'
    );

    // Wrap consecutive list items
    html = html.replace(
        /(<li>.*<\/li>)/gs,
        '<ul class="blood-report-list">$1</ul>'
    );

    // Convert line breaks
    // Convert remaining Markdown line breaks
    // without creating extra spacing around HTML blocks
    html = html.replace(/\n/g, "<br>");

    html = html
        .replace(/(<h1[^>]*>)<br>/g, "$1")
        .replace(/<br>(<\/h1>)/g, "$1")
        .replace(/(<h2[^>]*>)<br>/g, "$1")
        .replace(/<br>(<\/h2>)/g, "$1")
        .replace(/(<div class="blood-table-wrapper">)<br>/g, "$1")
        .replace(/<br>(<\/div>)/g, "$1")
        .replace(/(<table[^>]*>)<br>/g, "$1")
        .replace(/<br>(<\/table>)/g, "$1")
        .replace(/(<thead>)<br>/g, "$1")
        .replace(/<br>(<\/thead>)/g, "$1")
        .replace(/(<tbody>)<br>/g, "$1")
        .replace(/<br>(<\/tbody>)/g, "$1")
        .replace(/(<tr>)<br>/g, "$1")
        .replace(/<br>(<\/tr>)/g, "$1");

    return html;
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

    if (content.includes("# 🩺 Blood Report Summary")) {
        bubble.innerHTML = formatBloodReport(content);
    } else {
        bubble.textContent = content;
    }

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
    // HOME REMEDY + YOGA + APPOINTMENT BUTTONS
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


        // ----------------------------------------------------
        // BOOK APPOINTMENT
        // ----------------------------------------------------

        const appointmentButton =
            document.createElement("button");

        appointmentButton.type =
            "button";

        appointmentButton.className =
            "suggestion-button";

        appointmentButton.textContent =
            "📅 Book an Appointment";

        appointmentButton.addEventListener(
            "click",
            function () {

                openAppointmentBooking();

            }
        );

        suggestionContainer.appendChild(
            appointmentButton
        );


        // ----------------------------------------------------
        // ADD ALL BUTTONS
        // ----------------------------------------------------

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


function openAppointmentBooking() {

    const modal =
        document.createElement("div");

    modal.className =
        "appointment-modal-overlay";

    modal.innerHTML = `
        <div class="appointment-modal">

            <div class="appointment-modal-header">

                <div>
                    <h2>Book an Appointment</h2>

                    <p>
                        Select a doctor and choose
                        an available 30-minute slot.
                    </p>
                </div>

                <button
                    type="button"
                    class="appointment-close"
                >
                    ×
                </button>

            </div>

            <div
    id="appointmentDoctorList"
    class="appointment-doctor-list"
>
    <div class="appointment-loading">
        <div class="loading-spinner"></div>
        <div class="loading-text">
            Loading...
        </div>
    </div>
</div>
    `;

    document.body.appendChild(
        modal
    );

    modal.querySelector(
        ".appointment-close"
    ).addEventListener(
        "click",
        function () {

            modal.remove();

        }
    );

    loadAppointmentDoctors(
        modal
    );
}





async function loadAppointmentDoctors(
    modal
) {

    const container =
        modal.querySelector(
            "#appointmentDoctorList"
        );

    try {

        const response =
            await fetch(
                "/appointments/doctors",
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
                "Unable to find doctors."
            );
        }

        container.innerHTML = "";

        if (
            !data.doctors ||
            !data.doctors.length
        ) {

            container.innerHTML = `
                <div class="appointment-empty">
                    No relevant doctors found.
                </div>
            `;

            return;
        }

        data.doctors.forEach(
            function (doctor) {

                const card =
                    createDoctorCard(
                        doctor,
                        modal
                    );

                container.appendChild(
                    card
                );

            }
        );

    } catch (error) {

        console.error(
            "DOCTOR LIST ERROR:",
            error
        );

        container.innerHTML = `
            <div class="appointment-empty">
                Unable to find doctors.
                Please try again.
            </div>
        `;
    }
}

// ============================================================
// LOAD MY BOOKINGS
// ============================================================

async function loadMyBookings(
    overlay
) {

    const container =
        overlay.querySelector(
            "#myBookingsContainer"
        );

    try {

        const response =
            await fetch(
                "/my-bookings"
            );

        const data =
            await response.json();

        if (!response.ok) {

            throw new Error(
                data.error ||
                "Unable to load bookings."
            );
        }

        if (
            !data.bookings ||
            !data.bookings.length
        ) {

            container.innerHTML = `

                <div class="my-bookings-empty">

                    <div>
                        📅
                    </div>

                    <h3>
                        No Bookings
                    </h3>

                    <p>
                        You do not have any active
                        appointments.
                    </p>

                </div>
            `;

            return;
        }

        container.innerHTML = "";

        data.bookings.forEach(
            function (booking) {

                container.appendChild(
                    createBookingCard(
                        booking,
                        overlay
                    )
                );

            }
        );

    } catch (error) {

        console.error(
            "MY BOOKINGS ERROR:",
            error
        );

        container.innerHTML = `

            <div class="appointment-empty">
                ${escapeHtml(
            error.message
        )}
            </div>
        `;
    }
}

// ============================================================
// BOOKING CARD
// ============================================================

function createBookingCard(
    booking,
    overlay
) {

    const doctor =
        booking.doctor;

    const card =
        document.createElement(
            "div"
        );

    card.className =
        "my-booking-card";

    const date =
        formatBookingDate(
            booking.appointment_date
        );

    let actions = "";

    if (booking.can_modify) {

        actions = `

        <div class="booking-card-actions">

            <button
                type="button"
                class="booking-edit-button"
            >
                Edit
            </button>

            <button
                type="button"
                class="booking-cancel-button"
            >
                Cancel Booking
            </button>

        </div>
    `;

    } else {

        const now = new Date();

        function parseAppointmentDateTime(booking) {
            const dateValue = String(
                booking.appointment_date || ""
            ).trim();

            const timeValue = String(
                booking.slot_time || ""
            ).trim();

            if (!dateValue || !timeValue) {
                return null;
            }

            let year;
            let month;
            let day;

            // YYYY-MM-DD
            let match = dateValue.match(
                /^(\d{4})-(\d{1,2})-(\d{1,2})$/
            );

            if (match) {
                year = Number(match[1]);
                month = Number(match[2]) - 1;
                day = Number(match[3]);
            }

            // DD-MM-YYYY / DD/MM/YYYY
            if (!match) {
                match = dateValue.match(
                    /^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$/
                );

                if (match) {
                    day = Number(match[1]);
                    month = Number(match[2]) - 1;
                    year = Number(match[3]);
                }
            }

            // DD Mon YYYY
            if (!match) {
                const parsedDate =
                    new Date(dateValue);

                if (!Number.isNaN(parsedDate.getTime())) {
                    year = parsedDate.getFullYear();
                    month = parsedDate.getMonth();
                    day = parsedDate.getDate();
                }
            }

            if (
                year === undefined ||
                month === undefined ||
                day === undefined
            ) {
                return null;
            }

            // Supports:
            // 10:30 AM
            // 10:30 AM - 11:00 AM
            // 10:30
            // 10:30:00
            const timeMatch =
                timeValue.match(
                    /(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(AM|PM)?/i
                );

            if (!timeMatch) {
                return null;
            }

            let hours =
                Number(timeMatch[1]);

            const minutes =
                Number(timeMatch[2]);

            const seconds =
                Number(timeMatch[3] || 0);

            const period =
                timeMatch[4]
                    ? timeMatch[4].toUpperCase()
                    : null;

            // Convert 12-hour time to 24-hour time
            if (period === "PM" && hours !== 12) {
                hours += 12;
            }

            if (period === "AM" && hours === 12) {
                hours = 0;
            }

            return new Date(
                year,
                month,
                day,
                hours,
                minutes,
                seconds,
                0
            );
        }

        const appointmentDateTime =
            parseAppointmentDateTime(booking);

        const isExpired =
            appointmentDateTime !== null &&
            now.getTime() >= appointmentDateTime.getTime();

        console.log(
            "BOOKING TIME CHECK:",
            booking.appointment_date,
            booking.appointment_time,
            "=>",
            appointmentDateTime,
            "NOW:",
            now,
            "EXPIRED:",
            isExpired
        );

        actions = `

        <div class="booking-unavailable-message">

            <span>
                Changes unavailable within 6 hours
            </span>

            <span
                class="booking-status ${isExpired
                ? "booking-status-expired"
                : "booking-status-booked"
            }"
            >
                ${isExpired
                ? "Expired"
                : "Booked"
            }
            </span>

        </div>
    `;
    }

    card.innerHTML = `

        <div class="my-booking-main">

            <div>

                <h3>
                    ${escapeHtml(
        doctor.name
    )}
                </h3>

                <div class="booking-specialization">
                    ${escapeHtml(
        doctor.specialization
    )}
                </div>

                <div class="booking-rating">
                    ★ ${doctor.rating}
                    <span>
                        (${doctor.reviews} reviews)
                    </span>
                </div>

                <div class="booking-hospital">
                    ${escapeHtml(
        doctor.hospital
    )}
                </div>

                <div class="booking-address">
                    ${escapeHtml(
        doctor.address
    )}
                </div>

            </div>

            <div class="booking-date-time">

                <div>

                    <span>
                        Date
                    </span>

                    <strong>
                        ${escapeHtml(
        date
    )}
                    </strong>

                </div>

                <div>

                    <span>
                        Time
                    </span>

                    <strong>
                        ${escapeHtml(
        booking.slot_time
    )}
                    </strong>

                </div>

            </div>

        </div>

        ${actions}
    `;

    if (booking.can_modify) {

        card.querySelector(
            ".booking-edit-button"
        ).addEventListener(
            "click",
            function () {

                openEditBooking(
                    booking,
                    overlay
                );

            }
        );

        card.querySelector(
            ".booking-cancel-button"
        ).addEventListener(
            "click",
            function () {

                openCancelConfirmation(
                    booking,
                    overlay
                );

            }
        );
    }

    return card;
}

function formatBookingDate(
    dateString
) {

    const date =
        new Date(
            `${dateString}T00:00:00`
        );

    if (
        Number.isNaN(
            date.getTime()
        )
    ) {

        return dateString;
    }

    return date.toLocaleDateString(
        "en-IN",
        {
            day: "2-digit",
            month: "short",
            year: "numeric"
        }
    );
}

// ============================================================
// EDIT BOOKING
// ============================================================

async function openEditBooking(
    booking,
    overlay
) {

    const editOverlay =
        document.createElement(
            "div"
        );

    editOverlay.className =
        "edit-booking-overlay";

    editOverlay.innerHTML = `

        <div class="edit-booking-modal">

            <div class="edit-booking-header">

                <div>
                    <h2>
                        Edit Appointment
                    </h2>

                    <p>
                        ${escapeHtml(
        booking.doctor.name
    )}
                    </p>
                </div>

                <button
                    type="button"
                    class="edit-booking-close"
                >
                    ×
                </button>

            </div>

            <div
                id="editSlotsContainer"
                class="edit-slots-container"
            >

                <div class="appointment-loading">
                    <div class="loading-spinner"></div>
                    <div class="loading-text">
                        Loading available slots...
                    </div>
                </div>

            </div>

        </div>
    `;

    document.body.appendChild(
        editOverlay
    );

    editOverlay.querySelector(
        ".edit-booking-close"
    ).addEventListener(
        "click",
        function () {

            editOverlay.remove();

        }
    );

    await loadEditSlots(
        booking,
        editOverlay,
        overlay
    );
}

// ============================================================
// LOAD EDIT SLOTS
// ============================================================

async function loadEditSlots(
    booking,
    editOverlay,
    overlay
) {

    const container =
        editOverlay.querySelector(
            "#editSlotsContainer"
        );

    try {

        const response =
            await fetch(
                "/appointments/edit-slots",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body:
                        JSON.stringify({
                            appointment_id:
                                booking.id
                        })
                }
            );

        const data =
            await response.json();

        if (!response.ok) {

            throw new Error(
                data.error ||
                "Unable to load slots."
            );
        }

        container.innerHTML = `

            <div class="edit-booking-info">

                <span>
                    Appointment Date
                </span>

                <strong>
                    ${escapeHtml(
            formatBookingDate(
                data.date
            )
        )}
                </strong>

            </div>

            <div class="edit-slots-title">
                Available Slots
            </div>

            <div
                class="edit-slot-grid"
            ></div>

            <button
                type="button"
                class="edit-confirm-button"
                disabled
            >
                Update Appointment
            </button>
        `;

        const grid =
            container.querySelector(
                ".edit-slot-grid"
            );

        const updateButton =
            container.querySelector(
                ".edit-confirm-button"
            );

        let selectedSlot =
            null;

        data.slots.forEach(
            function (slot) {

                const wrapper =
                    document.createElement(
                        "div"
                    );

                wrapper.className =
                    "edit-slot-wrapper";

                const button =
                    document.createElement(
                        "button"
                    );

                button.type =
                    "button";

                button.className =
                    "edit-time-slot";

                button.textContent =
                    slot;

                const isCurrent =
                    slot ===
                    data.current_slot;

                const doctorBooked =
                    data.booked_slots.includes(
                        slot
                    );

                const userBooked =
                    data.user_booked_slots[
                    slot
                    ];

                if (isCurrent) {

                    button.classList.add(
                        "current-slot"
                    );

                    button.disabled =
                        false;

                    button.title =
                        "Current appointment";

                } else if (
                    doctorBooked
                ) {

                    button.classList.add(
                        "not-available"
                    );

                    button.disabled =
                        true;

                    button.title =
                        "Already booked by someone else";

                } else if (
                    userBooked
                ) {

                    button.classList.add(
                        "not-available"
                    );

                    button.disabled =
                        true;

                    button.title =
                        `You already have an appointment with ${userBooked.doctor_name} at this time`;

                } else {

                    button.addEventListener(
                        "click",
                        function () {

                            grid
                                .querySelectorAll(
                                    ".edit-time-slot.selected"
                                )
                                .forEach(
                                    function (
                                        item
                                    ) {

                                        item.classList.remove(
                                            "selected"
                                        );

                                    }
                                );

                            button.classList.add(
                                "selected"
                            );

                            selectedSlot =
                                slot;

                            updateButton.disabled =
                                false;

                        }
                    );
                }

                wrapper.appendChild(
                    button
                );

                if (
                    isCurrent
                ) {

                    const status =
                        document.createElement(
                            "span"
                        );

                    status.className =
                        "slot-status";

                    status.textContent =
                        "Current";

                    wrapper.appendChild(
                        status
                    );
                }

                grid.appendChild(
                    wrapper
                );
            }
        );

        updateButton.addEventListener(
            "click",
            async function () {

                if (!selectedSlot) {
                    return;
                }

                updateButton.disabled =
                    true;

                updateButton.textContent =
                    "Updating...";

                try {

                    const response =
                        await fetch(
                            "/appointments/edit",
                            {
                                method: "POST",

                                headers: {
                                    "Content-Type":
                                        "application/json"
                                },

                                body:
                                    JSON.stringify({

                                        appointment_id:
                                            booking.id,

                                        slot_time:
                                            selectedSlot
                                    })
                            }
                        );

                    const result =
                        await response.json();

                    if (!response.ok) {

                        throw new Error(
                            result.error ||
                            "Unable to update appointment."
                        );
                    }

                    alert(
                        "Appointment updated successfully."
                    );

                    editOverlay.remove();

                    await loadMyBookings(
                        overlay
                    );

                } catch (error) {

                    alert(
                        error.message
                    );

                    updateButton.disabled =
                        false;

                    updateButton.textContent =
                        "Update Appointment";
                }
            }
        );

    } catch (error) {

        container.innerHTML = `

            <div class="appointment-empty">
                ${escapeHtml(
            error.message
        )}
            </div>
        `;
    }
}

// ============================================================
// CANCEL CONFIRMATION
// ============================================================

function openCancelConfirmation(
    booking,
    overlay
) {

    const confirmation =
        document.createElement(
            "div"
        );

    confirmation.className =
        "cancel-confirm-overlay";

    confirmation.innerHTML = `

        <div class="cancel-confirm-card">

            <div class="cancel-confirm-icon">
                ?
            </div>

            <h3>
                Are you sure?
            </h3>

            <p>
                Do you want to cancel your
                appointment with
                <strong>
                    ${escapeHtml(
        booking.doctor.name
    )}
                </strong>
                at
                <strong>
                    ${escapeHtml(
        booking.slot_time
    )}
                </strong>?
            </p>

            <div class="cancel-confirm-actions">

                <button
                    type="button"
                    class="cancel-no-button"
                >
                    No
                </button>

                <button
                    type="button"
                    class="cancel-yes-button"
                >
                    Yes, Cancel
                </button>

            </div>

        </div>
    `;

    document.body.appendChild(
        confirmation
    );

    confirmation.querySelector(
        ".cancel-no-button"
    ).addEventListener(
        "click",
        function () {

            confirmation.remove();

        }
    );

    confirmation.querySelector(
        ".cancel-yes-button"
    ).addEventListener(
        "click",
        async function () {

            this.disabled =
                true;

            this.textContent =
                "Cancelling...";

            try {

                const response =
                    await fetch(
                        "/appointments/cancel",
                        {
                            method: "POST",

                            headers: {
                                "Content-Type":
                                    "application/json"
                            },

                            body:
                                JSON.stringify({
                                    appointment_id:
                                        booking.id
                                })
                        }
                    );

                const data =
                    await response.json();

                if (!response.ok) {

                    throw new Error(
                        data.error ||
                        "Unable to cancel appointment."
                    );
                }

                confirmation.remove();

                await loadMyBookings(
                    overlay
                );

            } catch (error) {

                alert(
                    error.message
                );

                this.disabled =
                    false;

                this.textContent =
                    "Yes, Cancel";
            }
        }
    );
}

function showDoctorDetails(
    doctor,
    modal
) {

    const container =
        modal.querySelector(
            "#appointmentDoctorList"
        );

    container.innerHTML = `

        <div class="doctor-details-card">

            <button
                type="button"
                class="doctor-details-back"
            >
                ← Back to Doctors
            </button>

            <div class="doctor-details-header">

                <h2>
                    ${escapeHtml(
        doctor.name
    )}
                </h2>

                <div class="doctor-details-specialization">
                    ${escapeHtml(
        doctor.specialization
    )}
                </div>

            </div>

            <div class="doctor-details-grid">

                <div class="doctor-detail-item">

                    <span>
                        Experience
                    </span>

                    <strong>
                        ${doctor.experience}
                        years
                    </strong>

                </div>

                <div class="doctor-detail-item">

                    <span>
                        Qualification
                    </span>

                    <strong>
                        ${escapeHtml(
        doctor.qualification
    )}
                    </strong>

                </div>

                <div class="doctor-detail-item">

                    <span>
                        Rating
                    </span>

                    <strong>
                        ★ ${doctor.rating}
                    </strong>

                </div>

                <div class="doctor-detail-item">

                    <span>
                        Reviews
                    </span>

                    <strong>
                        ${doctor.reviews}
                    </strong>

                </div>

                <div class="doctor-detail-item">

                    <span>
                        Hospital
                    </span>

                    <strong>
                        ${escapeHtml(
        doctor.hospital
    )}
                    </strong>

                </div>

                <div class="doctor-detail-item">

                    <span>
                        Address
                    </span>

                    <strong>
                        ${escapeHtml(
        doctor.address
    )}
                    </strong>

                </div>

                <div class="doctor-detail-item">

                    <span>
                        Phone
                    </span>

                    <strong>
                        ${escapeHtml(
        doctor.phone
    )}
                    </strong>

                </div>

                <div class="doctor-detail-item">

                    <span>
                        Email
                    </span>

                    <strong>
                        ${escapeHtml(
        doctor.email
    )}
                    </strong>

                </div>

            </div>

            <button
                type="button"
                class="doctor-details-book-button"
                ${doctor.already_booked
            ? "disabled"
            : ""
        }
            >
                ${doctor.already_booked
            ? "Already Booked"
            : "Book Slot"
        }
            </button>

        </div>
    `;

    container.querySelector(
        ".doctor-details-back"
    ).addEventListener(
        "click",
        function () {

            loadAppointmentDoctors(
                modal
            );

        }
    );

    const bookButton =
        container.querySelector(
            ".doctor-details-book-button"
        );

    if (
        !doctor.already_booked
    ) {

        bookButton.addEventListener(
            "click",
            function () {

                showDoctorSlots(
                    doctor,
                    modal
                );

            }
        );
    }
}

function createDoctorCard(
    doctor,
    modal
) {

    const card =
        document.createElement("div");

    card.className =
        "doctor-card";

    card.innerHTML = `

        <div class="doctor-card-main">

            <div class="doctor-info">

                <h3>
                    ${escapeHtml(
        doctor.name
    )}
                </h3>

                <div class="doctor-specialization">
                    ${escapeHtml(
        doctor.specialization
    )}
                </div>

                <div class="doctor-rating">
                    ★ ${doctor.rating}
                    <span>
                        (${doctor.reviews} reviews)
                    </span>
                </div>

                <div class="doctor-hospital">
                    ${escapeHtml(
        doctor.hospital
    )}
                </div>

                <div class="doctor-address">
                    ${escapeHtml(
        doctor.address
    )}
                </div>

                <div class="doctor-experience">
                    ${doctor.experience}
                    years experience
                </div>

            </div>

            <div class="doctor-actions">

                <button
                    type="button"
                    class="doctor-view-button"
                >
                    View
                </button>

                <button
                    type="button"
                    class="doctor-book-button"
                    ${doctor.already_booked
            ? "disabled"
            : ""
        }
                >
                    ${doctor.already_booked
            ? "Already Booked"
            : "Book Slot"
        }
                </button>

            </div>

        </div>
    `;

    // ========================================================
    // VIEW
    // ========================================================

    card.querySelector(
        ".doctor-view-button"
    ).addEventListener(
        "click",
        function () {

            showDoctorDetails(
                doctor,
                modal
            );

        }
    );




    // ========================================================
    // BOOK SLOT
    // ========================================================

    const bookButton =
        card.querySelector(
            ".doctor-book-button"
        );

    if (
        !doctor.already_booked
    ) {

        bookButton.addEventListener(
            "click",
            function () {

                showDoctorSlots(
                    doctor,
                    modal
                );

            }
        );

    }

    return card;
}


async function showDoctorSlots(
    doctor,
    modal
) {

    const container =
        modal.querySelector(
            "#appointmentDoctorList"
        );

    container.innerHTML = `

        <div class="slot-booking-header">

            <button
                type="button"
                class="back-to-doctors"
            >
                ← Back
            </button>

            <div class="slot-doctor-summary">

                <h3>
                    ${escapeHtml(
        doctor.name
    )}
                </h3>

                <div class="slot-doctor-specialization">
                    ${escapeHtml(
        doctor.specialization
    )}
                </div>

                <div class="slot-doctor-rating">
                    ★ ${doctor.rating}

                    <span>
                        (${doctor.reviews} reviews)
                    </span>
                </div>

                <div class="slot-doctor-hospital">
                    ${escapeHtml(
        doctor.hospital
    )}
                </div>

                <div class="slot-doctor-address">
                    ${escapeHtml(
        doctor.address
    )}
                </div>

                <div class="slot-doctor-experience">
                    ${doctor.experience}
                    years experience
                </div>

            </div>

        </div>

        <div class="slot-date-section">

            <label>
                Appointment Date
            </label>

            <input
                type="date"
                id="appointmentDate"
                class="appointment-date-input"
            >

        </div>

        <div
            id="availableSlots"
            class="available-slots"
        >
            Select a date to view available slots.
        </div>
    `;

    const dateInput =
        container.querySelector(
            "#appointmentDate"
        );

    const today =
        new Date();

    const year =
        today.getFullYear();

    const month =
        String(
            today.getMonth() + 1
        ).padStart(
            2,
            "0"
        );

    const day =
        String(
            today.getDate()
        ).padStart(
            2,
            "0"
        );

    dateInput.min =
        `${year}-${month}-${day}`;

    dateInput.addEventListener(
        "change",
        function () {

            loadAvailableSlots(
                doctor,
                dateInput.value,
                container
            );

        }
    );

    container.querySelector(
        ".back-to-doctors"
    ).addEventListener(
        "click",
        function () {

            loadAppointmentDoctors(
                modal
            );

        }
    );
}


async function loadAvailableSlots(
    doctor,
    date,
    container
) {

    const slotsContainer =
        container.querySelector(
            "#availableSlots"
        );

    if (!date) {

        slotsContainer.innerHTML =
            "Select a date to view available slots.";

        return;
    }

    slotsContainer.innerHTML = `
        <div class="appointment-loading">
            <div class="loading-spinner"></div>
            <div class="loading-text">
                Loading...
            </div>
        </div>
    `;

    try {

        const response =
            await fetch(
                "/appointments/slots",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({

                        doctor_id:
                            doctor.id,

                        date:
                            date
                    })
                }
            );

        const data =
            await response.json();

        if (!response.ok) {

            throw new Error(
                data.error ||
                "Unable to load slots."
            );
        }

        // ====================================================
        // SAME DOCTOR ALREADY BOOKED
        // ====================================================

        if (
            data.doctor_already_booked
        ) {

            slotsContainer.innerHTML = `

                <div class="doctor-already-booked">

                    <div class="doctor-already-booked-icon">
                        ✓
                    </div>

                    <strong>
                        Appointment Already Booked
                    </strong>

                    <span>
                        You already have an appointment
                        with ${escapeHtml(
                doctor.name
            )}.
                    </span>

                </div>
            `;

            return;
        }

        const slots =
            data.slots || [];

        if (!slots.length) {

            slotsContainer.innerHTML = `
                <div class="appointment-empty">
                    No slots available for this date.
                </div>
            `;

            return;
        }

        const bookedSlots =
            new Set(
                data.booked_slots || []
            );

        const userBookedSlots =
            data.user_booked_slots || {};

        slotsContainer.innerHTML = `

            <div class="slots-title">
                Available Slots
            </div>

            <div class="slot-grid"></div>

            <button
                type="button"
                class="confirm-slot-button"
                disabled
            >
                Confirm Booking
            </button>
        `;

        const slotGrid =
            slotsContainer.querySelector(
                ".slot-grid"
            );

        const confirmButton =
            slotsContainer.querySelector(
                ".confirm-slot-button"
            );

        let selectedSlot =
            null;

        slots.forEach(
            function (slot) {

                const wrapper =
                    document.createElement(
                        "div"
                    );

                wrapper.className =
                    "time-slot-wrapper";

                const button =
                    document.createElement(
                        "button"
                    );

                button.type =
                    "button";

                button.className =
                    "time-slot";

                button.textContent =
                    slot;

                // =================================================
                // SLOT BOOKED FOR THIS DOCTOR
                // =================================================

                if (
                    bookedSlots.has(
                        slot
                    )
                ) {

                    button.classList.add(
                        "booked"
                    );

                    button.disabled =
                        true;

                    const label =
                        document.createElement(
                            "span"
                        );

                    label.className =
                        "slot-status";

                    label.textContent =
                        "Not Available";

                    wrapper.appendChild(
                        button
                    );

                    wrapper.appendChild(
                        label
                    );

                    slotGrid.appendChild(
                        wrapper
                    );

                    return;
                }

                // =================================================
                // USER HAS SAME TIME WITH ANOTHER DOCTOR
                // =================================================

                const userBooking =
                    userBookedSlots[
                    slot
                    ];

                if (
                    userBooking &&
                    userBooking.doctor_id
                    !== doctor.id
                ) {

                    button.classList.add(
                        "conflict"
                    );

                    button.disabled =
                        true;

                    button.title =
                        "This time slot is already booked with " +
                        userBooking.doctor_name;

                    const label =
                        document.createElement(
                            "span"
                        );

                    label.className =
                        "slot-status conflict-text";

                    label.textContent =
                        "Not Available";

                    wrapper.appendChild(
                        button
                    );

                    wrapper.appendChild(
                        label
                    );

                    slotGrid.appendChild(
                        wrapper
                    );

                    return;
                }

                // =================================================
                // AVAILABLE SLOT
                // =================================================

                button.addEventListener(
                    "click",
                    function () {

                        slotGrid
                            .querySelectorAll(
                                ".time-slot.selected"
                            )
                            .forEach(
                                function (
                                    item
                                ) {

                                    item.classList.remove(
                                        "selected"
                                    );

                                }
                            );

                        button.classList.add(
                            "selected"
                        );

                        selectedSlot =
                            slot;

                        confirmButton.disabled =
                            false;

                    }
                );

                wrapper.appendChild(
                    button
                );

                slotGrid.appendChild(
                    wrapper
                );

            }
        );

        confirmButton.addEventListener(
            "click",
            async function () {

                if (
                    !selectedSlot
                ) {

                    return;
                }

                await confirmAppointment(
                    doctor,
                    date,
                    selectedSlot,
                    confirmButton,
                    container
                );

            }
        );

    } catch (error) {

        console.error(
            "SLOT ERROR:",
            error
        );

        slotsContainer.innerHTML = `
            <div class="appointment-empty">
                Unable to load available slots.
            </div>
        `;
    }
}




async function confirmAppointment(
    doctor,
    date,
    slot,
    button,
    container
) {

    button.disabled =
        true;

    button.textContent =
        "Booking...";

    try {

        const response =
            await fetch(
                "/appointments/book",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({

                        doctor_id:
                            doctor.id,

                        date:
                            date,

                        slot_time:
                            slot,

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
                "Unable to book appointment."
            );
        }

        container.innerHTML = `

            <div class="booking-success">

                <div class="booking-success-icon">
                    ✓
                </div>

                <h3>
                    Appointment Booked
                </h3>

                <p>
                    Your appointment with
                    <strong>
                        ${escapeHtml(doctor.name)}
                    </strong>
                    is confirmed.
                </p>

                <div class="booking-details">

                    <div>
                        <span>Date</span>
                        <strong>${date}</strong>
                    </div>

                    <div>
                        <span>Time</span>
                        <strong>${slot}</strong>
                    </div>

                </div>

                <button
                    type="button"
                    class="appointment-done-button"
                >
                    Done
                </button>

            </div>
        `;

        container.querySelector(
            ".appointment-done-button"
        ).addEventListener(
            "click",
            function () {

                const modal =
                    container.closest(
                        ".appointment-modal-overlay"
                    );

                if (modal) {
                    modal.remove();
                }

            }
        );

    } catch (error) {

        alert(
            error.message
        );

        button.disabled =
            false;

        button.textContent =
            "Confirm Booking";
    }
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

    if (content.includes("# 🩺 Blood Report Summary")) {
        bubble.innerHTML = formatBloodReport(content);
    } else {
        bubble.textContent = content;
    }

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

        // ====================================================
        // FIND LAST ASSISTANT MESSAGE
        // ====================================================

        const lastAssistantIndex =
            data.messages.reduce(
                function (
                    lastIndex,
                    message,
                    index
                ) {

                    if (
                        message.role ===
                        "assistant"
                    ) {

                        return index;
                    }

                    return lastIndex;

                },
                -1
            );

        // ====================================================
        // RESTORE CONVERSATION
        // ====================================================

        data.messages.forEach(
            function (
                message,
                index
            ) {

                addMessage(

                    message.content,

                    message.role === "user"
                        ? "user"
                        : "assistant",

                    message.created_at ||
                    message.timestamp ||
                    null,

                    // Show buttons ONLY on the
                    // last assistant response
                    message.role ===
                    "assistant" &&
                    index ===
                    lastAssistantIndex
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

    initProfileMenu();

    const savedConversationId =
        localStorage.getItem(
            "currentConversationId"
        );

    if (savedConversationId) {

        await openConversation(
            savedConversationId
        );
    }

    // ========================================================
    // RESTORE ACTIVE DASHBOARD AFTER REFRESH
    // ========================================================

    const activeDashboard =
        localStorage.getItem(
            "activeDashboard"
        );

    if (
        activeDashboard === "profile"
    ) {

        try {

            const response =
                await fetch(
                    "/profile"
                );

            if (response.ok) {

                const data =
                    await response.json();

                if (
                    data.success &&
                    data.user
                ) {

                    openProfileDashboard(
                        data.user
                    );
                }
            }

        } catch (error) {

            console.error(
                "PROFILE RESTORE ERROR:",
                error
            );
        }

    } else if (
        activeDashboard === "bookings"
    ) {

        try {

            await openMyBookingsDashboard();

        } catch (error) {

            console.error(
                "BOOKINGS RESTORE ERROR:",
                error
            );
        }

    } else if (
        activeDashboard === "diet"
    ) {

        try {

            await openDietPlanningDashboard();

        } catch (error) {

            console.error(
                "DIET RESTORE ERROR:",
                error
            );
        }
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

    if (content.includes("# 🩺 Blood Report Summary")) {
        bubble.innerHTML = formatBloodReport(content);
    } else {
        bubble.textContent = content;
    }



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
    // BOOK APPOINTMENT BUTTON
    // ========================================================

    if (currentConversationId) {

        const appointmentContainer =
            document.createElement("div");

        appointmentContainer.className =
            "suggestion-buttons";


        const appointmentButton =
            document.createElement("button");

        appointmentButton.type =
            "button";

        appointmentButton.className =
            "suggestion-button";

        appointmentButton.textContent =
            "📅 Book an Appointment";


        appointmentButton.addEventListener(
            "click",
            function () {

                openAppointmentBooking();

            }
        );


        appointmentContainer.appendChild(
            appointmentButton
        );


        wrapper.appendChild(
            appointmentContainer
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

function escapeHtml(
    value
) {

    return String(
        value ?? ""
    )
        .replace(
            /&/g,
            "&amp;"
        )
        .replace(
            /</g,
            "&lt;"
        )
        .replace(
            />/g,
            "&gt;"
        )
        .replace(
            /"/g,
            "&quot;"
        )
        .replace(
            /'/g,
            "&#039;"
        );
}

initializeApp();