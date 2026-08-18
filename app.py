import logging
import os
import sqlite3
import uuid

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

from langchain_groq import ChatGroq

from agent import agent


load_dotenv()


logging.disable(logging.INFO)

logging.getLogger("httpx").disabled = True
logging.getLogger("httpcore").disabled = True
logging.getLogger("groq").disabled = True


app = Flask(__name__)

app.secret_key = os.getenv(
    "FLASK_SECRET_KEY",
    "medical-rag-development-secret-key",
)

DATABASE = "app.db"

GROQ_API_KEY = os.getenv(
    "GROQ_API_KEY"
)

if not GROQ_API_KEY:
    raise ValueError(
        "GROQ_API_KEY is not set in .env"
    )


# ============================================================
# TITLE GENERATION LLM
# ============================================================

title_llm = ChatGroq(
    model="openai/gpt-oss-120b",
    temperature=0,
    api_key=GROQ_API_KEY,
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
- Do not use words like Chat, Conversation, Question, Medical, or Assistant.

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
        # ONLY CHANGE:
        # GENERATE AI TITLE WHEN THIS IS THE FIRST MESSAGE
        #
        # This works even when frontend sends a
        # conversation_id for a newly created conversation.
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
        # BUILD CONVERSATION MESSAGES
        # ====================================================

        conversation_messages = []

        for row in rows:

            conversation_messages.append({
                "role": row["role"],
                "content": row["content"],
            })

        conversation_messages.append({
            "role": "user",
            "content": question,
        })

        # ====================================================
        # CALL AGENT
        # ====================================================

        result = agent.invoke(
            {
                "messages":
                conversation_messages
            }
        )

        final_message = result[
            "messages"
        ][-1]

        answer = final_message.content

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

        # ====================================================
        # SAVE ASSISTANT MESSAGE
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
                now,
            ),
        )

        # ====================================================
        # UPDATE CONVERSATION TIME
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
        # GET FINAL TITLE
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

        return jsonify({
            "answer": answer,
            "conversation_id":
                conversation_id,
            "title":
                conversation_row["title"],
        })

    except Exception as e:

        connection.rollback()

        return jsonify({
            "error": str(e)
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

    return jsonify(result)


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
        "success": True
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
        "success": True
    })


# ============================================================
# INITIALIZE DATABASE
# ============================================================

init_db()


# ============================================================
# RUN APPLICATION
# ============================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=8000,
        debug=False,
    )