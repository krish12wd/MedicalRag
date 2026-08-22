import logging
import os
import re
import sqlite3
import uuid
from pathlib import Path
import tempfile

from werkzeug.utils import secure_filename

from datetime import datetime
from functools import wraps

from dotenv import load_dotenv

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    redirect,
    url_for,
    session,
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash,
)

from langchain_openai import ChatOpenAI

from agent import (
    agent,
    home_remedy_node,
    yoga_node,
    answer_node,
    blood_report_agent,
)


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()


# ============================================================
# LOGGING
# ============================================================

logging.disable(logging.INFO)

logging.getLogger("httpx").disabled = True
logging.getLogger("httpcore").disabled = True
logging.getLogger("groq").disabled = True


# ============================================================
# FLASK
# ============================================================

app = Flask(__name__)

app.config[
    "MAX_CONTENT_LENGTH"
] = 15 * 1024 * 1024

app.secret_key = os.getenv(
    "FLASK_SECRET_KEY",
    "medical-rag-development-secret-key",
)


# ============================================================
# CONFIGURATION
# ============================================================

DATABASE = "app.db"

QWEN_API_KEY = os.getenv(
    "QWEN_API_KEY"
)

QWEN_BASE_URL = os.getenv(
    "QWEN_BASE_URL",
    "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
)

QWEN_MODEL = os.getenv(
    "QWEN_MODEL",
    "qwen-plus",
)

if not QWEN_API_KEY:
    raise ValueError(
        "QWEN_API_KEY is not set in .env"
    )


# ============================================================
# TITLE GENERATION LLM
# ============================================================

title_llm = ChatOpenAI(
    model=QWEN_MODEL,
    temperature=0,
    api_key=QWEN_API_KEY,
    base_url=QWEN_BASE_URL,
)


# ============================================================
# TITLE PROMPT
# ============================================================

TITLE_PROMPT = """
Generate a short title for the user's medical question.

Rules:
- Return only the title.
- Use 2 to 5 words.
- Prefer 2 to 4 words.
- Identify the main topic and intent.
- Make it natural and concise.
- Do not include age.
- Do not include duration.
- Do not include temperature.
- Do not include unnecessary patient details.
- Do not answer the question.
- Do not use quotation marks.
- Do not use words like Chat, Conversation, Question,
  Medical, or Assistant.

Examples:

User: Hello I want insulin dose for type 1 diabetes
Title: Insulin for Type 1 Diabetes

User: Today I have fever 103F from last 3 days, give medication
Title: Fever Medication

User: What is the treatment for Type 2 diabetes?
Title: Type 2 Diabetes Treatment

User: What investigations are recommended for Type 2 diabetes?
Title: Diabetes Investigations

User: What are the symptoms of dengue?
Title: Dengue Symptoms

User: I am vomiting and have abdominal pain
Title: Vomiting and Abdominal Pain

User: What are the treatment options for malaria?
Title: Malaria Treatment

User: What medicines are used for hypertension?
Title: Hypertension Medication

User message:
"""


# ============================================================
# GENERATE CHAT TITLE
# ============================================================

def generate_chat_title(question):

    try:

        response = title_llm.invoke(
            TITLE_PROMPT
            + "\n"
            + question
        )

        title = response.content.strip()

        title = title.replace(
            '"',
            ""
        )

        title = title.replace(
            "'",
            ""
        )

        title = " ".join(
            title.split()
        )

        words = title.split()

        if not words:
            return "New Conversation"

        if len(words) > 5:
            title = " ".join(
                words[:5]
            )

        return title

    except Exception as e:

        print(
            "TITLE GENERATION ERROR:",
            str(e)
        )

        return "New Conversation"


# ============================================================
# DATABASE
# ============================================================

def get_db():

    connection = sqlite3.connect(
        DATABASE
    )

    connection.row_factory = sqlite3.Row

    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    return connection


# ============================================================
# SAVE ASSISTANT MESSAGE
# ============================================================

def save_suggestion_message(
    connection,
    conversation_id,
    content,
):

    if content.startswith(
        "The AI model has reached its daily token limit."
    ):

        previous = connection.execute(
            """
            SELECT content
            FROM messages
            WHERE conversation_id = ?
            AND role = 'assistant'
            ORDER BY id DESC
            LIMIT 1
            """,
            (
                conversation_id,
            ),
        ).fetchone()

        if (
            previous
            and previous["content"].startswith(
                "The AI model has reached its daily token limit."
            )
        ):
            return

    now = datetime.now().isoformat()

    connection.execute(
        """
        INSERT INTO messages (
            conversation_id,
            role,
            content,
            created_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            conversation_id,
            "assistant",
            content,
            now,
        ),
    )

    connection.execute(
        """
        UPDATE conversations
        SET updated_at = ?
        WHERE id = ?
        """,
        (
            now,
            conversation_id,
        ),
    )

    connection.commit()


# ============================================================
# INITIALIZE DATABASE
# ============================================================

def init_db():

    connection = get_db()

    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,

            FOREIGN KEY(user_id)
            REFERENCES users(id)
            ON DELETE CASCADE
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,

            FOREIGN KEY(conversation_id)
            REFERENCES conversations(id)
            ON DELETE CASCADE
        )
        """
    )

    connection.commit()

    connection.close()


# ============================================================
# LOGIN REQUIRED
# ============================================================

def login_required(function):

    @wraps(function)
    def wrapper(*args, **kwargs):

        if "user_id" not in session:

            return redirect(
                url_for("login")
            )

        return function(
            *args,
            **kwargs
        )

    return wrapper


# ============================================================
# CURRENT USER
# ============================================================

def current_user():

    if "user_id" not in session:
        return None

    connection = get_db()

    user = connection.execute(
        """
        SELECT id, name, email
        FROM users
        WHERE id = ?
        """,
        (
            session["user_id"],
        ),
    ).fetchone()

    connection.close()

    return user


# ============================================================
# CLEAN PATIENT RESPONSE
# ============================================================

def clean_patient_response(answer):

    if not answer:
        return ""

    answer = str(answer).replace("\r\n", "\n")
    answer = answer.replace("\r", "\n")

    answer = answer.replace(
        "[CLARIFICATION]",
        ""
    )

    answer = answer.replace(
        "[FINAL]",
        ""
    )

    answer = re.sub(
        r"```(?:text|markdown)?",
        "",
        answer,
        flags=re.IGNORECASE,
    )

    answer = answer.replace(
        "≈",
        " approximately "
    )

    answer = answer.replace(
        "~",
        " approximately "
    )

    answer = re.sub(
        r"(\d)\s*[–—-]\s*(\d)",
        r"\1 to \2",
        answer,
    )

    answer = answer.replace(
        "**",
        "",
    )

    answer = re.sub(
        r"(?im)^\s*(answer:|treatment:|treatment / management:|important points:)\s*$",
        "",
        answer,
    )

    answer = re.sub(
        r"(?m)^\s*[-*]\s+",
        "• ",
        answer,
    )

    answer = re.sub(
        r"(?m)^\s*•\s*",
        "• ",
        answer,
    )

    answer = re.sub(
        r"\n\s*\n+",
        "\n",
        answer,
    )

    lines = []

    for line in answer.split("\n"):

        line = line.strip()

        if not line:
            continue

        if line.startswith("•"):
            bullet_text = line[1:].strip()

            if bullet_text:
                lines.append(
                    "• " + bullet_text
                )

        else:
            lines.append(line)

    return "\n".join(lines).strip()


# ============================================================
# EXTRACT ANSWER FROM AGENT STATE
# ============================================================

def extract_agent_answer(result):

    if not isinstance(result, dict):

        raise RuntimeError(
            "Agent returned an invalid state."
        )

    answer = result.get(
        "final_answer"
    )

    if answer:
        return clean_patient_response(
            answer
        )

    answer = result.get(
        "consultation_response"
    )

    if answer:
        return clean_patient_response(
            answer
        )

    messages = result.get(
        "messages",
        []
    )

    if messages:

        last_message = messages[-1]

        if hasattr(
            last_message,
            "content"
        ):

            answer = last_message.content

        elif isinstance(
            last_message,
            dict
        ):

            answer = last_message.get(
                "content",
                ""
            )

        else:

            answer = ""

        if answer:

            return clean_patient_response(
                answer
            )

    raise RuntimeError(
        "Agent returned no usable answer."
    )


# ============================================================
# HOME
# ============================================================

@app.route("/")
@login_required
def home():

    user = current_user()

    if not user:

        session.clear()

        return redirect(
            url_for("login")
        )

    return render_template(
        "index.html",
        user=user,
    )


# ============================================================
# LOGIN
# ============================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if request.method == "GET":

        if "user_id" in session:

            return redirect(
                url_for("home")
            )

        return render_template(
            "login.html"
        )

    email = request.form.get(
        "email",
        ""
    ).strip().lower()

    password = request.form.get(
        "password",
        ""
    )

    if not email or not password:

        return render_template(
            "login.html",
            error="Please enter email and password."
        )

    connection = get_db()

    user = connection.execute(
        """
        SELECT *
        FROM users
        WHERE email = ?
        """,
        (
            email,
        ),
    ).fetchone()

    connection.close()

    if not user:

        return render_template(
            "login.html",
            error="Invalid email or password."
        )

    if not check_password_hash(
        user["password"],
        password,
    ):

        return render_template(
            "login.html",
            error="Invalid email or password."
        )

    session.clear()

    session["user_id"] = user["id"]

    return redirect(
        url_for("home")
    )


# ============================================================
# REGISTER
# ============================================================

@app.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    if request.method == "GET":

        if "user_id" in session:

            return redirect(
                url_for("home")
            )

        return render_template(
            "register.html"
        )

    name = request.form.get(
        "name",
        ""
    ).strip()

    email = request.form.get(
        "email",
        ""
    ).strip().lower()

    password = request.form.get(
        "password",
        ""
    )

    confirm_password = request.form.get(
        "confirm_password",
        ""
    )

    if not name or not email or not password:

        return render_template(
            "register.html",
            error="Please fill in all fields."
        )

    if password != confirm_password:

        return render_template(
            "register.html",
            error="Passwords do not match."
        )

    if len(password) < 6:

        return render_template(
            "register.html",
            error="Password must contain at least 6 characters."
        )

    connection = get_db()

    existing_user = connection.execute(
        """
        SELECT id
        FROM users
        WHERE email = ?
        """,
        (
            email,
        ),
    ).fetchone()

    if existing_user:

        connection.close()

        return render_template(
            "register.html",
            error="An account with this email already exists."
        )

    password_hash = generate_password_hash(
        password
    )

    cursor = connection.execute(
        """
        INSERT INTO users (
            name,
            email,
            password,
            created_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            name,
            email,
            password_hash,
            datetime.now().isoformat(),
        ),
    )

    connection.commit()

    user_id = cursor.lastrowid

    connection.close()

    session.clear()

    session["user_id"] = user_id

    return redirect(
        url_for("home")
    )


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("login")
    )


# ============================================================
# CHAT
# ============================================================

@app.route(
    "/chat",
    methods=["POST"]
)
@login_required
def chat():

    data = request.get_json(
        silent=True
    )

    if not data:

        return jsonify({
            "error":
                "Invalid request data."
        }), 400

    question = (
        data.get(
            "message",
            ""
        )
        .strip()
    )

    conversation_id = data.get(
        "conversation_id"
    )

    if not question:

        return jsonify({
            "error":
                "Please enter a question."
        }), 400

    user_id = session["user_id"]

    connection = get_db()

    try:

        # ====================================================
        # CREATE OR GET CONVERSATION
        # ====================================================

        if conversation_id:

            conversation = connection.execute(
                """
                SELECT id
                FROM conversations
                WHERE id = ?
                AND user_id = ?
                """,
                (
                    conversation_id,
                    user_id,
                ),
            ).fetchone()

            if not conversation:

                return jsonify({
                    "error":
                        "Conversation not found."
                }), 404

        else:

            conversation_id = str(
                uuid.uuid4()
            )

            now = datetime.now().isoformat()

            connection.execute(
                """
                INSERT INTO conversations (
                    id,
                    user_id,
                    title,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    conversation_id,
                    user_id,
                    "New Conversation",
                    now,
                    now,
                ),
            )

            connection.commit()

        # ====================================================
        # GET EXISTING MESSAGES
        # ====================================================

        rows = connection.execute(
            """
            SELECT role, content
            FROM messages
            WHERE conversation_id = ?
            ORDER BY id ASC
            """,
            (
                conversation_id,
            ),
        ).fetchall()

        # ====================================================
        # GENERATE TITLE FOR FIRST MESSAGE
        # ====================================================

        if len(rows) == 0:

            title = generate_chat_title(
                question
            )

            connection.execute(
                """
                UPDATE conversations
                SET title = ?
                WHERE id = ?
                AND user_id = ?
                """,
                (
                    title,
                    conversation_id,
                    user_id,
                ),
            )

            connection.commit()

        # ====================================================
        # BUILD CONVERSATION HISTORY
        # ====================================================

        conversation_messages = []

        for row in rows:

            conversation_messages.append({
                "role":
                    row["role"],

                "content":
                    row["content"],
            })

        conversation_messages.append({
            "role":
                "user",

            "content":
                question,
        })

        # ====================================================
        # SAVE USER MESSAGE
        # ====================================================

        now = datetime.now().isoformat()

        connection.execute(
            """
            INSERT INTO messages (
                conversation_id,
                role,
                content,
                created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                conversation_id,
                "user",
                question,
                now,
            ),
        )

        connection.commit()

        # ====================================================
        # RUN AGENT
        # ====================================================

        result = agent.invoke(
            {
                "messages":
                    conversation_messages
            }
        )

        # ====================================================
        # EXTRACT PATIENT-FRIENDLY ANSWER
        # ====================================================

        answer = extract_agent_answer(
            result
        )

        # ====================================================
        # READ AGENT STATE
        # ====================================================

        enough_information = bool(
            result.get(
                "enough_information",
                False,
            )
        )

        intent = (
            result.get(
                "intent",
                ""
            )
            or ""
        )

        # ====================================================
        # RESPONSE SOURCE
        #
        # IMPORTANT:
        # This is a separate API field only.
        # It is NOT added to "answer".
        #
        # Therefore the existing UI can continue to
        # display only the answer text.
        # ====================================================

        retrieval_source = (
            result.get(
                "retrieval_source",
                "NONE"
            )
            or "NONE"
        )

        if retrieval_source == "PDF":

            response_source = (
                "RAG / STANDARD TREATMENT GUIDELINES"
            )

        elif retrieval_source == "WEB":

            response_source = (
                "WEB SEARCH / AGENT"
            )

        else:

            response_source = (
                "AGENT / CONSULTATION"
            )

        # ====================================================
        # SUGGESTIONS
        # ====================================================

        show_suggestions = (
            enough_information
        )

        print(
            "AGENT STATE:",
            {
                "enough_information":
                    enough_information,

                "intent":
                    intent,

                "answer":
                    answer,
            }
        )

        # ====================================================
        # SAVE ASSISTANT ANSWER
        # ====================================================

        now = datetime.now().isoformat()

        connection.execute(
            """
            INSERT INTO messages (
                conversation_id,
                role,
                content,
                created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                conversation_id,
                "assistant",
                answer,
                now,
            ),
        )

        # ====================================================
        # UPDATE CONVERSATION
        # ====================================================

        connection.execute(
            """
            UPDATE conversations
            SET updated_at = ?
            WHERE id = ?
            """,
            (
                now,
                conversation_id,
            ),
        )

        connection.commit()

        # ====================================================
        # GET TITLE
        # ====================================================

        conversation_row = connection.execute(
            """
            SELECT title
            FROM conversations
            WHERE id = ?
            """,
            (
                conversation_id,
            ),
        ).fetchone()

        # ====================================================
        # RETURN TO FRONTEND
        # ====================================================

        return jsonify({
            "answer":
                answer,

            "conversation_id":
                conversation_id,

            "title":
                conversation_row["title"],

            "show_suggestions":
                show_suggestions,

            "intent":
                intent,

            # Separate field.
            # Frontend does not need to display it.
            "source":
                response_source,
        })

    except Exception as e:

        connection.rollback()

        error_text = str(e)

        print(
            "CHAT ERROR:",
            repr(e)
        )

        if (
            "rate_limit_exceeded"
            in error_text.lower()
            or
            "error code: 429"
            in error_text.lower()
            or
            "429"
            in error_text
        ):

            wait_match = re.search(
                r"try again in\s+"
                r"([0-9]+h)?\s*"
                r"([0-9]+m)?\s*"
                r"([0-9]+(?:\.[0-9]+)?s)?",
                error_text,
                flags=re.IGNORECASE,
            )

            wait_time = (
                wait_match
                .group(0)
                .replace(
                    "try again in",
                    "",
                )
                .strip()
                if wait_match
                else "a few minutes"
            )

            error_message = (
                "The AI model has reached its daily token limit. "
                f"It should reset in approximately {wait_time}. "
                "Please try again after that."
            )

            save_suggestion_message(
                connection,
                conversation_id,
                error_message,
            )

            return jsonify({
                "error":
                    error_message
            }), 429

        error_message = (
            "I could not complete that response right now. "
            "Please try again in a moment."
        )

        save_suggestion_message(
            connection,
            conversation_id,
            error_message,
        )

        return jsonify({
            "error":
                error_message
        }), 500

    finally:

        connection.close()


# ============================================================
# CHAT HISTORY
# ============================================================

@app.route("/history")
@login_required
def history():

    user_id = session["user_id"]

    connection = get_db()

    conversations = connection.execute(
        """
        SELECT
            id,
            title,
            created_at,
            updated_at
        FROM conversations
        WHERE user_id = ?
        ORDER BY updated_at DESC
        """,
        (
            user_id,
        ),
    ).fetchall()

    connection.close()

    result = []

    for conversation in conversations:

        result.append({
            "id":
                conversation["id"],

            "title":
                conversation["title"],

            "created_at":
                conversation["created_at"],

            "updated_at":
                conversation["updated_at"],
        })

    return jsonify(
        result
    )


# ============================================================
# GET SINGLE CONVERSATION
# ============================================================

@app.route(
    "/conversation/<conversation_id>"
)
@login_required
def get_conversation(
    conversation_id
):

    user_id = session["user_id"]

    connection = get_db()

    conversation = connection.execute(
        """
        SELECT *
        FROM conversations
        WHERE id = ?
        AND user_id = ?
        """,
        (
            conversation_id,
            user_id,
        ),
    ).fetchone()

    if not conversation:

        connection.close()

        return jsonify({
            "error":
                "Conversation not found."
        }), 404

    messages = connection.execute(
        """
        SELECT
            role,
            content,
            created_at
        FROM messages
        WHERE conversation_id = ?
        ORDER BY id ASC
        """,
        (
            conversation_id,
        ),
    ).fetchall()

    connection.close()

    return jsonify({
        "id":
            conversation["id"],

        "title":
            conversation["title"],

        "messages": [
            {
                "role":
                    message["role"],

                "content":
                    message["content"],

                "created_at":
                    message["created_at"],
            }

            for message in messages
        ],
    })


# ============================================================
# DELETE CONVERSATION
# ============================================================

@app.route(
    "/conversation/<conversation_id>",
    methods=["DELETE"]
)
@login_required
def delete_conversation(
    conversation_id
):

    user_id = session["user_id"]

    connection = get_db()

    conversation = connection.execute(
        """
        SELECT id
        FROM conversations
        WHERE id = ?
        AND user_id = ?
        """,
        (
            conversation_id,
            user_id,
        ),
    ).fetchone()

    if not conversation:

        connection.close()

        return jsonify({
            "error":
                "Conversation not found."
        }), 404

    connection.execute(
        """
        DELETE FROM messages
        WHERE conversation_id = ?
        """,
        (
            conversation_id,
        ),
    )

    connection.execute(
        """
        DELETE FROM conversations
        WHERE id = ?
        """,
        (
            conversation_id,
        ),
    )

    connection.commit()

    connection.close()

    return jsonify({
        "success":
            True
    })


# ============================================================
# CLEAR
# ============================================================

@app.route(
    "/clear",
    methods=["POST"]
)
@login_required
def clear():

    return jsonify({
        "success":
            True
    })


# ============================================================
# HOME REMEDY SUGGESTION
# ============================================================

@app.route(
    "/suggestions/home-remedies",
    methods=["POST"]
)
@login_required
def home_remedy_suggestions():

    data = request.get_json(
        silent=True
    )

    if not data:

        return jsonify({
            "error":
                "Invalid request data."
        }), 400

    conversation_id = data.get(
        "conversation_id"
    )

    if not conversation_id:

        return jsonify({
            "error":
                "Conversation ID is required."
        }), 400

    user_id = session["user_id"]

    connection = get_db()

    try:

        # ====================================================
        # VERIFY CONVERSATION
        # ====================================================

        conversation = connection.execute(
            """
            SELECT id
            FROM conversations
            WHERE id = ?
            AND user_id = ?
            """,
            (
                conversation_id,
                user_id,
            ),
        ).fetchone()

        if not conversation:

            return jsonify({
                "error":
                    "Conversation not found."
            }), 404

        # ====================================================
        # LOAD COMPLETE CONVERSATION
        # ====================================================

        rows = connection.execute(
            """
            SELECT role, content
            FROM messages
            WHERE conversation_id = ?
            ORDER BY id ASC
            """,
            (
                conversation_id,
            ),
        ).fetchall()

        if not rows:

            return jsonify({
                "error":
                    "No conversation found."
            }), 400

        messages = []

        for row in rows:

            messages.append({
                "role":
                    row["role"],

                "content":
                    row["content"],
            })

        # ====================================================
        # RUN HOME REMEDY NODE
        # ====================================================

        result = home_remedy_node(
            {
                "messages":
                    messages,

                "intent":
                    "home_remedy",
            }
        )

        # ====================================================
        # GENERATE FINAL HOME REMEDY RESPONSE
        # ====================================================

        result = answer_node(
            result
        )

        suggestions = result.get(
            "final_answer",
            ""
        )

        if not suggestions:

            suggestions = (
                "No additional home remedies were found "
                "beyond the advice already provided."
            )

        suggestions = clean_patient_response(
            suggestions
        )

        # ====================================================
        # SAVE SUGGESTION
        # ====================================================

        save_suggestion_message(
            connection,
            conversation_id,
            suggestions,
        )

        return jsonify({
            "suggestions":
                suggestions
        })

    except Exception as error:

        print(
            "HOME REMEDY ENDPOINT ERROR:",
            repr(error)
        )

        return jsonify({
            "error":
                "Unable to generate home remedy suggestions."
        }), 500

    finally:

        connection.close()


# ============================================================
# YOGA SUGGESTIONS
# ============================================================

@app.route(
    "/suggestions/yoga",
    methods=["POST"]
)
@login_required
def yoga_suggestions():

    data = request.get_json(
        silent=True
    )

    if not data:

        return jsonify({
            "error":
                "Invalid request data."
        }), 400

    conversation_id = data.get(
        "conversation_id"
    )

    if not conversation_id:

        return jsonify({
            "error":
                "Conversation ID is required."
        }), 400

    user_id = session["user_id"]

    connection = get_db()

    try:

        conversation = connection.execute(
            """
            SELECT id
            FROM conversations
            WHERE id = ?
            AND user_id = ?
            """,
            (
                conversation_id,
                user_id,
            ),
        ).fetchone()

        if not conversation:

            return jsonify({
                "error":
                    "Conversation not found."
            }), 404

        rows = connection.execute(
            """
            SELECT role, content
            FROM messages
            WHERE conversation_id = ?
            ORDER BY id ASC
            """,
            (
                conversation_id,
            ),
        ).fetchall()

        if not rows:

            return jsonify({
                "error":
                    "No conversation context found."
            }), 400

        conversation_messages = []

        for row in rows:

            conversation_messages.append({
                "role":
                    row["role"],

                "content":
                    row["content"],
            })

        state = {
            "messages":
                conversation_messages,

            "enough_information":
                True,

            "intent":
                "yoga",

            "retrieved_information":
                "",
        }

        state = yoga_node(
            state
        )

        state = answer_node(
            state
        )

        answer = extract_agent_answer(
            state
        )

        save_suggestion_message(
            connection,
            conversation_id,
            answer,
        )

        return jsonify({
            "success":
                True,

            "suggestions":
                answer,

            "next":
                "home_remedy",

            "source":
                "WEB SEARCH / AGENT",
        })

    except Exception as error:

        print(
            "YOGA SUGGESTION ERROR:",
            repr(error)
        )

        return jsonify({
            "error":
                "Unable to get yoga suggestions."
        }), 500

    finally:

        connection.close()




# ============================================================
# BLOOD REPORT UPLOAD
# DIGITAL PDF ONLY
# ============================================================

ALLOWED_REPORT_EXTENSIONS = {
    ".pdf",
}


@app.route(
    "/analyze-report",
    methods=["POST"],
)
@login_required
def analyze_report():

    # ========================================================
    # CHECK FILE
    # ========================================================

    if "report" not in request.files:

        return jsonify({
            "error":
                "Please upload a digital blood report PDF."
        }), 400

    uploaded_file = request.files[
        "report"
    ]

    if not uploaded_file.filename:

        return jsonify({
            "error":
                "Please select a blood report PDF."
        }), 400

    filename = secure_filename(
        uploaded_file.filename
    )

    extension = Path(
        filename
    ).suffix.lower()

    # ========================================================
    # PDF ONLY
    # ========================================================

    if extension not in ALLOWED_REPORT_EXTENSIONS:

        return jsonify({
            "error":
                "Only digital PDF blood reports are supported."
        }), 400

    # ========================================================
    # TEMP DIRECTORY
    # ========================================================

    temporary_directory = tempfile.mkdtemp(
        prefix="mediguide_report_"
    )

    file_path = os.path.join(
        temporary_directory,
        filename,
    )

    connection = get_db()

    try:

        # ====================================================
        # SAVE PDF
        # ====================================================

        uploaded_file.save(
            file_path
        )

        print(
            "\n"
            + "=" * 70
        )

        print(
            "BLOOD REPORT UPLOAD"
        )

        print(
            f"FILE: {filename}"
        )

        print(
            "FORMAT: DIGITAL PDF ONLY"
        )

        # ====================================================
        # CONVERSATION ID
        #
        # Upload works even when there is NO existing
        # conversation/message.
        # ====================================================

        conversation_id = request.form.get(
            "conversation_id"
        )

        user_id = session[
            "user_id"
        ]

        # ====================================================
        # VALIDATE EXISTING CONVERSATION
        # ====================================================

        if conversation_id:

            conversation = connection.execute(
                """
                SELECT id
                FROM conversations
                WHERE id = ?
                AND user_id = ?
                """,
                (
                    conversation_id,
                    user_id,
                ),
            ).fetchone()

            if not conversation:

                conversation_id = None

        # ====================================================
        # CREATE NEW CONVERSATION
        #
        # This is what allows the report to work even if
        # the user has not sent a chat message.
        # ====================================================

        if not conversation_id:

            conversation_id = str(
                uuid.uuid4()
            )

            now = datetime.now().isoformat()

            connection.execute(
                """
                INSERT INTO conversations (
                    id,
                    user_id,
                    title,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    conversation_id,
                    user_id,
                    "Blood Report Analysis",
                    now,
                    now,
                ),
            )

            connection.commit()

        # ====================================================
        # SAVE UPLOAD MESSAGE
        # ====================================================

        upload_message = (
            "📎 Uploaded blood report: "
            + filename
        )

        connection.execute(
            """
            INSERT INTO messages (
                conversation_id,
                role,
                content,
                created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                conversation_id,
                "user",
                upload_message,
                datetime.now().isoformat(),
            ),
        )

        connection.commit()

        # ====================================================
        # RUN BLOOD REPORT AGENT
        #
        # NO CHAT MESSAGE IS REQUIRED.
        # ====================================================

        print(
            "\n"
            + "=" * 70
        )

        print(
            "RUNNING BLOOD REPORT AGENT"
        )

        result = blood_report_agent.invoke(
            {
                "file_path":
                    file_path,
            }
        )

        answer = result.get(
            "final_answer",
            "",
        )

        # ====================================================
        # ANALYSIS ERROR
        # ====================================================

        if answer.startswith(
            "REPORT_ANALYSIS_ERROR:"
        ):

            error_message = answer.replace(
                "REPORT_ANALYSIS_ERROR:",
                "",
                1,
            ).strip()

            # Remove upload message because analysis failed
            connection.execute(
                """
                DELETE FROM messages
                WHERE conversation_id = ?
                AND role = 'user'
                AND content = ?
                """,
                (
                    conversation_id,
                    upload_message,
                ),
            )

            # Remove newly-created empty conversation
            remaining_messages = connection.execute(
                """
                SELECT COUNT(*)
                FROM messages
                WHERE conversation_id = ?
                """,
                (
                    conversation_id,
                ),
            ).fetchone()[0]

            if remaining_messages == 0:

                connection.execute(
                    """
                    DELETE FROM conversations
                    WHERE id = ?
                    AND user_id = ?
                    """,
                    (
                        conversation_id,
                        user_id,
                    ),
                )

            connection.commit()

            return jsonify({
                "error":
                    error_message
            }), 400

        # ====================================================
        # SAVE ANALYSIS
        # ====================================================

        connection.execute(
            """
            INSERT INTO messages (
                conversation_id,
                role,
                content,
                created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                conversation_id,
                "assistant",
                answer,
                datetime.now().isoformat(),
            ),
        )

        # ====================================================
        # UPDATE CONVERSATION
        # ========================================================

        connection.execute(
            """
            UPDATE conversations
            SET
                updated_at = ?
            WHERE id = ?
            AND user_id = ?
            """,
            (
                datetime.now().isoformat(),
                conversation_id,
                user_id,
            ),
        )

        connection.commit()

        print(
            "\n"
            + "=" * 70
        )

        print(
            "BLOOD REPORT ANALYSIS SAVED"
        )

        print(
            "CONVERSATION:",
            conversation_id
        )

        print(
            "=" * 70
        )

        # ====================================================
        # RESPONSE
        # ====================================================

        return jsonify({
            "success":
                True,

            "conversation_id":
                conversation_id,

            "filename":
                filename,

            "analysis":
                answer,
        })

    except Exception as error:

        connection.rollback()

        print(
            "\n"
            + "=" * 70
        )

        print(
            "BLOOD REPORT ROUTE ERROR:",
            repr(error)
        )

        print(
            "=" * 70
        )

        return jsonify({
            "error":
                "Unable to analyze the blood report."
        }), 500

    finally:

        connection.close()

        # ====================================================
        # DELETE TEMPORARY PDF
        # ====================================================

        try:

            if os.path.exists(
                file_path
            ):

                os.remove(
                    file_path
                )

            if os.path.exists(
                temporary_directory
            ):

                os.rmdir(
                    temporary_directory
                )

        except Exception as cleanup_error:

            print(
                "REPORT CLEANUP ERROR:",
                repr(cleanup_error)
            )



# ============================================================
# RUN FLASK APPLICATION
# ============================================================

if __name__ == "__main__":

    init_db()

    app.run(
        host="0.0.0.0",
        port=8000,
        debug=True,
    )