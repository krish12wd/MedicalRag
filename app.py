import logging
import os
import re
import sqlite3
import uuid
from pathlib import Path
import tempfile
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta
from doctors import DOCTORS
from werkzeug.utils import secure_filename
from langchain_openai import ChatOpenAI
import smtplib
import threading
import time

from email.message import EmailMessage
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

# ============================================================
# EMAIL CONFIGURATION
# ============================================================

SMTP_HOST = os.getenv(
    "SMTP_HOST",
    "smtp.gmail.com"
)

SMTP_PORT = int(
    os.getenv(
        "SMTP_PORT",
        "587"
    )
)

SMTP_USERNAME = os.getenv(
    "SMTP_USERNAME"
)

SMTP_PASSWORD = os.getenv(
    "SMTP_PASSWORD"
)

SMTP_FROM = os.getenv(
    "SMTP_FROM",
    SMTP_USERNAME
)

QWEN_API_KEY = os.getenv(
    "QWEN_API_KEY"
)

QWEN_BASE_URL = os.getenv(
    "QWEN_BASE_URL",
    "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
)

QWEN_MODEL = os.getenv(
    "QWEN_MODEL",
    "qwen-plus-character",
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
# SEND EMAIL
# ============================================================

def send_email(
    recipient,
    subject,
    body
):

    if not SMTP_USERNAME or not SMTP_PASSWORD:
        print(
            "EMAIL ERROR: SMTP credentials are not configured."
        )
        return False

    try:

        message = EmailMessage()

        message["From"] = SMTP_FROM
        message["To"] = recipient
        message["Subject"] = subject

        message.set_content(
            body
        )

        with smtplib.SMTP(
            SMTP_HOST,
            SMTP_PORT,
            timeout=20
        ) as server:

            server.starttls()

            server.login(
                SMTP_USERNAME,
                SMTP_PASSWORD
            )

            server.send_message(
                message
            )

        print(
            f"EMAIL SENT: {recipient} | {subject}"
        )

        return True

    except Exception as error:

        print(
            "EMAIL ERROR:",
            repr(error)
        )

        return False


# ============================================================
# APPOINTMENT EMAIL HELPERS
# ============================================================

def send_booking_confirmation_email(
    user,
    doctor,
    appointment_date,
    slot_time
):

    subject = (
        "MediGuide - Appointment Confirmed"
    )

    body = f"""
Hello {user["name"]},

Your appointment has been successfully booked with MediGuide.

Appointment Details
-------------------

Doctor: {doctor["name"]}
Specialization: {doctor["specialization"]}
Hospital: {doctor["hospital"]}
Address: {doctor["address"]}

Date: {appointment_date}
Time: {slot_time}

Please arrive a few minutes before your appointment.

Thank you for using MediGuide.

MediGuide Team
"""

    return send_email(
        user["email"],
        subject,
        body.strip()
    )


def send_cancellation_email(
    user,
    doctor,
    appointment_date,
    slot_time
):

    subject = (
        "MediGuide - Appointment Cancelled"
    )

    body = f"""
Hello {user["name"]},

Your MediGuide appointment has been successfully cancelled.

Cancelled Appointment
---------------------

Doctor: {doctor["name"]}
Specialization: {doctor["specialization"]}
Hospital: {doctor["hospital"]}

Date: {appointment_date}
Time: {slot_time}

If you need another appointment, you can book a new slot anytime.

MediGuide Team
"""

    return send_email(
        user["email"],
        subject,
        body.strip()
    )


def send_appointment_reminder_email(
    user,
    doctor,
    appointment_date,
    slot_time,
    reminder_type
):

    if reminder_type == "24h":

        subject = (
            "MediGuide - Appointment Tomorrow"
        )

        heading = (
            "Your appointment is tomorrow."
        )

    else:

        subject = (
            "MediGuide - Appointment in 1 Hour"
        )

        heading = (
            "Your appointment is in 1 hour."
        )

    body = f"""
Hello {user["name"]},

{heading}

Appointment Details
-------------------

Doctor: {doctor["name"]}
Specialization: {doctor["specialization"]}
Hospital: {doctor["hospital"]}
Address: {doctor["address"]}

Date: {appointment_date}
Time: {slot_time}

Please make sure you are ready for your appointment.

MediGuide Team
"""

    return send_email(
        user["email"],
        subject,
        body.strip()
    )


# ============================================================
# APPOINTMENT REMINDER WORKER
# ============================================================

def appointment_reminder_worker():

    while True:

        connection = None

        try:

            now = datetime.now(IST)

            connection = get_db()

            appointments = connection.execute(
                """
                SELECT
                    id,
                    user_id,
                    doctor_id,
                    appointment_date,
                    slot_time,
                    reminder_24h_sent,
                    reminder_1h_sent
                FROM appointments
                WHERE status = 'booked'
                """
            ).fetchall()

            for appointment in appointments:

                try:

                    appointment_datetime = (
                        get_appointment_datetime(
                            appointment["appointment_date"],
                            appointment["slot_time"]
                        )
                    )

                    remaining = (
                        appointment_datetime - now
                    )

                    # ====================================================
                    # 24 HOUR REMINDER
                    #
                    # Send once when appointment is within 24 hours
                    # but still more than 1 hour away.
                    # ====================================================

                    if (
                        appointment["reminder_24h_sent"] == 0
                        and timedelta(hours=1)
                        < remaining
                        <= timedelta(hours=24)
                    ):

                        user = connection.execute(
                            """
                            SELECT
                                name,
                                email
                            FROM users
                            WHERE id = ?
                            """,
                            (
                                appointment["user_id"],
                            ),
                        ).fetchone()

                        doctor = get_doctor_by_id(
                            appointment["doctor_id"]
                        )

                        if user and doctor:

                            email_sent = (
                                send_appointment_reminder_email(
                                    user,
                                    doctor,
                                    appointment["appointment_date"],
                                    appointment["slot_time"],
                                    "24h",
                                )
                            )

                            # Mark as sent ONLY if email was
                            # successfully delivered.
                            if email_sent:

                                connection.execute(
                                    """
                                    UPDATE appointments
                                    SET reminder_24h_sent = 1
                                    WHERE id = ?
                                    """,
                                    (
                                        appointment["id"],
                                    ),
                                )

                                connection.commit()

                    # ====================================================
                    # 1 HOUR REMINDER
                    #
                    # Send once when appointment is within 1 hour.
                    # ====================================================

                    if (
                        appointment["reminder_1h_sent"] == 0
                        and timedelta(0)
                        < remaining
                        <= timedelta(hours=1)
                    ):

                        user = connection.execute(
                            """
                            SELECT
                                name,
                                email
                            FROM users
                            WHERE id = ?
                            """,
                            (
                                appointment["user_id"],
                            ),
                        ).fetchone()

                        doctor = get_doctor_by_id(
                            appointment["doctor_id"]
                        )

                        if user and doctor:

                            email_sent = (
                                send_appointment_reminder_email(
                                    user,
                                    doctor,
                                    appointment["appointment_date"],
                                    appointment["slot_time"],
                                    "1h",
                                )
                            )

                            # Mark as sent ONLY if email was
                            # successfully delivered.
                            if email_sent:

                                connection.execute(
                                    """
                                    UPDATE appointments
                                    SET reminder_1h_sent = 1
                                    WHERE id = ?
                                    """,
                                    (
                                        appointment["id"],
                                    ),
                                )

                                connection.commit()

                except Exception as appointment_error:

                    print(
                        "REMINDER APPOINTMENT ERROR:",
                        repr(appointment_error)
                    )

        except Exception as worker_error:

            print(
                "REMINDER WORKER ERROR:",
                repr(worker_error)
            )

        finally:

            if connection:

                connection.close()

        # Check every minute.
        time.sleep(60)


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


def identify_required_specializations(
    conversation_messages
):

    conversation_text = "\n".join(
        [
            f"{message['role']}: {message['content']}"
            for message in conversation_messages
        ]
    )

    prompt = f"""
You are a medical appointment routing assistant.

Your job is ONLY to identify which doctor specialization
is appropriate for the patient's current medical problem.

Do NOT diagnose the patient.
Do NOT provide treatment.
Do NOT provide medicine.
Do NOT provide medical advice.

Use the complete conversation.

Available doctor specializations:

- General Physician
- Cardiologist
- Dermatologist
- Orthopedic Surgeon
- Gynecologist
- Neurologist
- Pediatrician
- Gastroenterologist
- Psychiatrist
- Pulmonologist
- Endocrinologist
- Nephrologist
- Ophthalmologist
- ENT Specialist

Rules:

1. Return ONLY a comma-separated list.
2. Return only specializations from the available list.
3. Prefer the most directly relevant specialist.
4. Use General Physician when the problem is general,
   unclear, or does not clearly require a specialist.
5. You may return more than one specialization only when
   the conversation clearly involves multiple medical areas.
6. Never return all specializations.
7. Do not invent a specialization.

Conversation:

{conversation_text}

Required specializations:
"""

    response = title_llm.invoke(
        prompt
    )

    raw = str(
        response.content
    ).strip()

    allowed_specializations = {
        doctor["specialization"]
        for doctor in DOCTORS
    }

    requested = []

    for item in raw.split(","):

        specialization = item.strip()

        if specialization in allowed_specializations:

            if specialization not in requested:

                requested.append(
                    specialization
                )

    if not requested:

        requested = [
            "General Physician"
        ]

    return requested


def generate_doctor_slots(
    doctor,
    appointment_date
):

    timings = doctor.get(
        "timings",
        ""
    )

    match = re.search(
        r"(\d{1,2}:\d{2}\s*[AP]M)"
        r"\s*-\s*"
        r"(\d{1,2}:\d{2}\s*[AP]M)",
        timings,
        re.IGNORECASE,
    )

    if not match:

        return []

    start_text = match.group(1)
    end_text = match.group(2)

    start = datetime.strptime(
        start_text.upper(),
        "%I:%M %p"
    )

    end = datetime.strptime(
        end_text.upper(),
        "%I:%M %p"
    )

    slots = []

    current = start

    while current + timedelta(
        minutes=30
    ) <= end:

        slots.append(
            current.strftime(
                "%I:%M %p"
            )
        )

        current += timedelta(
            minutes=30
        )

    return slots


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

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            user_id INTEGER NOT NULL,

            conversation_id TEXT,

            doctor_id INTEGER NOT NULL,

            appointment_date TEXT NOT NULL,

            slot_time TEXT NOT NULL,

            status TEXT NOT NULL DEFAULT 'booked',

            created_at TEXT NOT NULL,

            reminder_24h_sent INTEGER NOT NULL DEFAULT 0,

            reminder_1h_sent INTEGER NOT NULL DEFAULT 0,

            FOREIGN KEY(user_id)
            REFERENCES users(id)
            ON DELETE CASCADE,

            FOREIGN KEY(conversation_id)
            REFERENCES conversations(id)
            ON DELETE SET NULL,

            UNIQUE(
                doctor_id,
                appointment_date,
                slot_time
            )
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
# APPOINTMENT TIME HELPERS
# ============================================================

IST = ZoneInfo("Asia/Kolkata")


def get_appointment_datetime(
    appointment_date,
    slot_time
):

    return datetime.strptime(
        f"{appointment_date} {slot_time}",
        "%Y-%m-%d %I:%M %p"
    ).replace(
        tzinfo=IST
    )


def appointment_changes_allowed(
    appointment_date,
    slot_time
):

    appointment_datetime = (
        get_appointment_datetime(
            appointment_date,
            slot_time
        )
    )

    now = datetime.now(IST)

    remaining = (
        appointment_datetime - now
    )

    return (
        remaining.total_seconds()
        >= 6 * 60 * 60
    )


def get_doctor_by_id(
    doctor_id
):

    try:

        doctor_id = int(
            doctor_id
        )

    except (
        TypeError,
        ValueError
    ):

        return None

    return next(
        (
            doctor
            for doctor in DOCTORS
            if doctor["id"] == doctor_id
        ),
        None
    )


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


@app.route(
    "/appointments/doctors",
    methods=["POST"]
)
@login_required
def appointment_doctors():

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
        # VERIFY CONVERSATION BELONGS TO CURRENT USER
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
        # GET FULL CONVERSATION
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
                    "No medical conversation found."
            }), 400

        conversation_messages = []

        for row in rows:

            conversation_messages.append({
                "role":
                    row["role"],

                "content":
                    row["content"],
            })

        # ====================================================
        # IDENTIFY REQUIRED SPECIALIZATIONS
        # ====================================================

        specializations = (
            identify_required_specializations(
                conversation_messages
            )
        )

        print(
            "APPOINTMENT SPECIALIZATIONS:",
            specializations
        )

        # ====================================================
        # GET DOCTORS ALREADY BOOKED BY CURRENT USER
        # ====================================================

        booked_doctor_rows = connection.execute(
            """
            SELECT DISTINCT doctor_id
            FROM appointments
            WHERE user_id = ?
            AND status = 'booked'
            """,
            (
                user_id,
            ),
        ).fetchall()

        booked_doctor_ids = {
            int(row["doctor_id"])
            for row in booked_doctor_rows
        }

        # ====================================================
        # FILTER RELEVANT DOCTORS
        # ====================================================

        relevant_doctors = []

        for doctor in DOCTORS:

            if (
                doctor["specialization"]
                not in specializations
            ):
                continue

            doctor_data = dict(
                doctor
            )

            doctor_data[
                "already_booked"
            ] = (
                doctor["id"]
                in booked_doctor_ids
            )

            relevant_doctors.append(
                doctor_data
            )

        # ====================================================
        # SORT
        # Higher rating first
        # ====================================================

        relevant_doctors.sort(
            key=lambda doctor: (
                doctor.get(
                    "rating",
                    0
                ),
                doctor.get(
                    "reviews",
                    0
                )
            ),
            reverse=True
        )

        return jsonify({

            "success":
                True,

            "specializations":
                specializations,

            "doctors":
                relevant_doctors,
        })

    except Exception as error:

        print(
            "APPOINTMENT DOCTOR ERROR:",
            repr(error)
        )

        return jsonify({
            "error":
                "Unable to find relevant doctors."
        }), 500

    finally:

        connection.close()


@app.route(
    "/appointments/slots",
    methods=["POST"]
)
@login_required
def appointment_slots():

    data = request.get_json(
        silent=True
    )

    if not data:

        return jsonify({
            "error":
                "Invalid request data."
        }), 400

    doctor_id = data.get(
        "doctor_id"
    )

    appointment_date = data.get(
        "date"
    )

    if not doctor_id or not appointment_date:

        return jsonify({
            "error":
                "Doctor and date are required."
        }), 400

    if (
        appointment_date
        < datetime.now().strftime(
            "%Y-%m-%d"
        )
    ):

        return jsonify({
            "error":
                "Appointment date cannot be in the past."
        }), 400

    try:

        datetime.strptime(
            appointment_date,
            "%Y-%m-%d"
        )

    except ValueError:

        return jsonify({
            "error":
                "Invalid appointment date."
        }), 400

    doctor = next(
        (
            doctor
            for doctor in DOCTORS
            if doctor["id"] == int(doctor_id)
        ),
        None
    )

    if not doctor:

        return jsonify({
            "error":
                "Doctor not found."
        }), 404

    user_id = session["user_id"]

    connection = get_db()

    try:

        # ====================================================
        # ALL SLOTS FOR THIS DOCTOR
        # ====================================================

        all_slots = generate_doctor_slots(
            doctor,
            appointment_date
        )

        # ====================================================
        # SLOTS ALREADY BOOKED FOR THIS DOCTOR
        # BY ANY USER
        # ====================================================

        booked_rows = connection.execute(
            """
            SELECT slot_time
            FROM appointments
            WHERE doctor_id = ?
            AND appointment_date = ?
            AND status = 'booked'
            """,
            (
                doctor_id,
                appointment_date,
            ),
        ).fetchall()

        booked_slots = {
            row["slot_time"]
            for row in booked_rows
        }

        # ====================================================
        # CURRENT USER'S BOOKINGS ON SAME DATE
        # FOR OTHER DOCTORS
        # ====================================================

        user_booking_rows = connection.execute(
            """
            SELECT
                slot_time,
                doctor_id
            FROM appointments
            WHERE user_id = ?
            AND appointment_date = ?
            AND status = 'booked'
            """,
            (
                user_id,
                appointment_date,
            ),
        ).fetchall()

        user_booked_slots = {}

        for row in user_booking_rows:

            booked_doctor = next(
                (
                    item
                    for item in DOCTORS
                    if item["id"]
                    == int(row["doctor_id"])
                ),
                None
            )

            if not booked_doctor:
                continue

            user_booked_slots[
                row["slot_time"]
            ] = {
                "doctor_id":
                    booked_doctor["id"],

                "doctor_name":
                    booked_doctor["name"],
            }

        # ====================================================
        # CHECK WHETHER USER ALREADY BOOKED THIS DOCTOR
        # ====================================================

        existing_doctor_booking = connection.execute(
            """
            SELECT id
            FROM appointments
            WHERE user_id = ?
            AND doctor_id = ?
            AND status = 'booked'
            LIMIT 1
            """,
            (
                user_id,
                doctor_id,
            ),
        ).fetchone()

        doctor_already_booked = (
            existing_doctor_booking
            is not None
        )

        return jsonify({

            "success":
                True,

            "doctor":
                doctor,

            "date":
                appointment_date,

            "slots":
                all_slots,

            "booked_slots":
                list(
                    booked_slots
                ),

            "user_booked_slots":
                user_booked_slots,

            "doctor_already_booked":
                doctor_already_booked,
        })

    finally:

        connection.close()


# ============================================================
# EDIT APPOINTMENT - AVAILABLE SLOTS
# ============================================================

@app.route(
    "/appointments/edit-slots",
    methods=["POST"]
)
@login_required
def edit_appointment_slots():

    data = request.get_json(
        silent=True
    )

    if not data:

        return jsonify({
            "error":
                "Invalid request data."
        }), 400

    appointment_id = data.get(
        "appointment_id"
    )

    if not appointment_id:

        return jsonify({
            "error":
                "Appointment ID is required."
        }), 400

    connection = get_db()

    try:

        appointment = connection.execute(
            """
            SELECT
                id,
                user_id,
                doctor_id,
                appointment_date,
                slot_time,
                status
            FROM appointments
            WHERE id = ?
            AND user_id = ?
            AND status = 'booked'
            """,
            (
                appointment_id,
                session["user_id"],
            ),
        ).fetchone()

        if not appointment:

            return jsonify({
                "error":
                    "Appointment not found."
            }), 404

        if not appointment_changes_allowed(
            appointment["appointment_date"],
            appointment["slot_time"],
        ):

            return jsonify({
                "error":
                    "This appointment can no longer be modified because it is less than 6 hours away."
            }), 403

        doctor = get_doctor_by_id(
            appointment["doctor_id"]
        )

        if not doctor:

            return jsonify({
                "error":
                    "Doctor not found."
            }), 404

        all_slots = generate_doctor_slots(
            doctor,
            appointment["appointment_date"]
        )

        booked_rows = connection.execute(
            """
            SELECT
                slot_time
            FROM appointments
            WHERE doctor_id = ?
            AND appointment_date = ?
            AND status = 'booked'
            AND id != ?
            """,
            (
                appointment["doctor_id"],
                appointment["appointment_date"],
                appointment["id"],
            ),
        ).fetchall()

        booked_slots = {
            row["slot_time"]
            for row in booked_rows
        }

        user_rows = connection.execute(
            """
            SELECT
                slot_time,
                doctor_id
            FROM appointments
            WHERE user_id = ?
            AND appointment_date = ?
            AND status = 'booked'
            AND id != ?
            """,
            (
                session["user_id"],
                appointment["appointment_date"],
                appointment["id"],
            ),
        ).fetchall()

        user_booked_slots = {}

        for row in user_rows:

            other_doctor = get_doctor_by_id(
                row["doctor_id"]
            )

            if not other_doctor:
                continue

            user_booked_slots[
                row["slot_time"]
            ] = {
                "doctor_id":
                    other_doctor["id"],

                "doctor_name":
                    other_doctor["name"],
            }

        return jsonify({

            "success":
                True,

            "appointment_id":
                appointment["id"],

            "doctor":
                doctor,

            "date":
                appointment["appointment_date"],

            "current_slot":
                appointment["slot_time"],

            "slots":
                all_slots,

            "booked_slots":
                list(booked_slots),

            "user_booked_slots":
                user_booked_slots,
        })

    finally:

        connection.close()


# ============================================================
# EDIT APPOINTMENT
# ============================================================

@app.route(
    "/appointments/edit",
    methods=["POST"]
)
@login_required
def edit_appointment():

    data = request.get_json(
        silent=True
    )

    if not data:

        return jsonify({
            "error":
                "Invalid request data."
        }), 400

    appointment_id = data.get(
        "appointment_id"
    )

    new_slot_time = data.get(
        "slot_time"
    )

    if not appointment_id or not new_slot_time:

        return jsonify({
            "error":
                "Appointment and slot are required."
        }), 400

    connection = get_db()

    try:

        appointment = connection.execute(
            """
            SELECT *
            FROM appointments
            WHERE id = ?
            AND user_id = ?
            AND status = 'booked'
            """,
            (
                appointment_id,
                session["user_id"],
            ),
        ).fetchone()

        if not appointment:

            return jsonify({
                "error":
                    "Appointment not found."
            }), 404

        if not appointment_changes_allowed(
            appointment["appointment_date"],
            appointment["slot_time"],
        ):

            return jsonify({
                "error":
                    "This appointment can no longer be modified because it is less than 6 hours away."
            }), 403

        doctor = get_doctor_by_id(
            appointment["doctor_id"]
        )

        if not doctor:

            return jsonify({
                "error":
                    "Doctor not found."
            }), 404

        valid_slots = generate_doctor_slots(
            doctor,
            appointment["appointment_date"]
        )

        if new_slot_time not in valid_slots:

            return jsonify({
                "error":
                    "This slot is not available."
            }), 400

        same_doctor_booking = connection.execute(
            """
            SELECT id
            FROM appointments
            WHERE doctor_id = ?
            AND appointment_date = ?
            AND slot_time = ?
            AND status = 'booked'
            AND id != ?
            """,
            (
                appointment["doctor_id"],
                appointment["appointment_date"],
                new_slot_time,
                appointment["id"],
            ),
        ).fetchone()

        if same_doctor_booking:

            return jsonify({
                "error":
                    "This slot is already booked by someone else."
            }), 409

        other_doctor_booking = connection.execute(
            """
            SELECT
                doctor_id
            FROM appointments
            WHERE user_id = ?
            AND appointment_date = ?
            AND slot_time = ?
            AND status = 'booked'
            AND id != ?
            LIMIT 1
            """,
            (
                session["user_id"],
                appointment["appointment_date"],
                new_slot_time,
                appointment["id"],
            ),
        ).fetchone()

        if other_doctor_booking:

            other_doctor = get_doctor_by_id(
                other_doctor_booking["doctor_id"]
            )

            doctor_name = (
                other_doctor["name"]
                if other_doctor
                else "another doctor"
            )

            return jsonify({
                "error":
                    f"You already have an appointment with {doctor_name} at this time."
            }), 409

        connection.execute(
            """
            UPDATE appointments
            SET slot_time = ?
            WHERE id = ?
            AND user_id = ?
            AND status = 'booked'
            """,
            (
                new_slot_time,
                appointment["id"],
                session["user_id"],
            ),
        )

        connection.commit()

        return jsonify({
            "success":
                True,

            "message":
                "Appointment updated successfully.",

            "slot":
                new_slot_time,
        })

    except Exception as error:

        connection.rollback()

        print(
            "EDIT APPOINTMENT ERROR:",
            repr(error)
        )

        return jsonify({
            "error":
                "Unable to update appointment."
        }), 500

    finally:

        connection.close()


# ============================================================
# CANCEL APPOINTMENT
# ============================================================

@app.route(
    "/appointments/cancel",
    methods=["POST"]
)
@login_required
def cancel_appointment():

    data = request.get_json(
        silent=True
    )

    if not data:

        return jsonify({
            "error":
                "Invalid request data."
        }), 400

    appointment_id = data.get(
        "appointment_id"
    )

    if not appointment_id:

        return jsonify({
            "error":
                "Appointment ID is required."
        }), 400

    connection = get_db()

    try:

        appointment = connection.execute(
            """
            SELECT
                id,
                doctor_id,
                appointment_date,
                slot_time
            FROM appointments
            WHERE id = ?
            AND user_id = ?
            AND status = 'booked'
            """,
            (
                appointment_id,
                session["user_id"],
            ),
        ).fetchone()

        if not appointment:

            return jsonify({
                "error":
                    "Appointment not found."
            }), 404

        if not appointment_changes_allowed(
            appointment["appointment_date"],
            appointment["slot_time"],
        ):

            return jsonify({
                "error":
                    "This appointment can no longer be cancelled because it is less than 6 hours away."
            }), 403

        connection.execute(
            """
            UPDATE appointments
            SET status = 'cancelled'
            WHERE id = ?
            AND user_id = ?
            AND status = 'booked'
            """,
            (
                appointment_id,
                session["user_id"],
            ),
        )

        connection.commit()

        # ====================================================
        # SEND CANCELLATION EMAIL
        # ====================================================

        user = connection.execute(
            """
            SELECT
                name,
                email
            FROM users
            WHERE id = ?
            """,
            (
                session["user_id"],
            ),
        ).fetchone()

        doctor = get_doctor_by_id(
            appointment["doctor_id"]
        )

        if user and doctor:

            send_cancellation_email(
                user,
                doctor,
                appointment["appointment_date"],
                appointment["slot_time"],
            )

        return jsonify({
            "success":
                True,

            "message":
                "Appointment cancelled successfully."
        })

    except Exception as error:

        connection.rollback()

        print(
            "CANCEL APPOINTMENT ERROR:",
            repr(error)
        )

        return jsonify({
            "error":
                "Unable to cancel appointment."
        }), 500

    finally:

        connection.close()


@app.route(
    "/appointments/book",
    methods=["POST"]
)
@login_required
def book_appointment():

    data = request.get_json(
        silent=True
    )

    if not data:

        return jsonify({
            "error":
                "Invalid request data."
        }), 400

    doctor_id = data.get(
        "doctor_id"
    )

    appointment_date = data.get(
        "date"
    )

    slot_time = data.get(
        "slot_time"
    )

    conversation_id = data.get(
        "conversation_id"
    )

    if not all([
        doctor_id,
        appointment_date,
        slot_time,
        conversation_id,
    ]):

        return jsonify({
            "error":
                "Doctor, date, slot and conversation are required."
        }), 400

    try:

        appointment_date_obj = datetime.strptime(
            appointment_date,
            "%Y-%m-%d"
        )

    except ValueError:

        return jsonify({
            "error":
                "Invalid appointment date."
        }), 400

    if appointment_date < datetime.now().strftime("%Y-%m-%d"):

        return jsonify({
            "error":
                "Appointment date cannot be in the past."
        }), 400

    doctor = next(
        (
            doctor
            for doctor in DOCTORS
            if doctor["id"] == int(doctor_id)
        ),
        None
    )

    if not doctor:

        return jsonify({
            "error":
                "Doctor not found."
        }), 404

    # --------------------------------------------------------
    # VERIFY THAT SLOT BELONGS TO DOCTOR'S TIMINGS
    # --------------------------------------------------------

    valid_slots = generate_doctor_slots(
        doctor,
        appointment_date
    )

    if slot_time not in valid_slots:

        return jsonify({
            "error":
                "This slot is not available."
        }), 400

    user_id = session["user_id"]

    connection = get_db()

    try:

        # ----------------------------------------------------
        # VERIFY CONVERSATION BELONGS TO CURRENT USER
        # ----------------------------------------------------

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

        now = datetime.now().isoformat()

        # ====================================================
        # PREVENT USER FROM BOOKING SAME DOCTOR AGAIN
        # ====================================================

        existing_doctor_booking = connection.execute(
            """
            SELECT id
            FROM appointments
            WHERE user_id = ?
            AND doctor_id = ?
            AND status = 'booked'
            LIMIT 1
            """,
            (
                user_id,
                doctor_id,
            ),
        ).fetchone()

        if existing_doctor_booking:

            return jsonify({
                "success":
                    False,

                "error":
                    "You already have an appointment with this doctor."
            }), 409

        # ----------------------------------------------------
        # ATOMIC BOOKING
        # UNIQUE CONSTRAINT PREVENTS DOUBLE BOOKING
        # ----------------------------------------------------

        try:

            connection.execute(
                """
                INSERT INTO appointments (
                    user_id,
                    conversation_id,
                    doctor_id,
                    appointment_date,
                    slot_time,
                    status,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    conversation_id,
                    doctor_id,
                    appointment_date,
                    slot_time,
                    "booked",
                    now,
                ),
            )

            connection.commit()

        except sqlite3.IntegrityError:

            connection.rollback()

            return jsonify({
                "success":
                    False,

                "error":
                    "Sorry, this slot has just been booked by another user. Please choose another slot."
            }), 409

        # ====================================================
        # SEND BOOKING CONFIRMATION EMAIL
        # ====================================================

        user = connection.execute(
            """
            SELECT
                name,
                email
            FROM users
            WHERE id = ?
            """,
            (
                user_id,
            ),
        ).fetchone()

        if user:

            send_booking_confirmation_email(
                user,
                doctor,
                appointment_date,
                slot_time,
            )

        return jsonify({
            "success":
                True,

            "message":
                "Appointment booked successfully.",

            "doctor":
                doctor["name"],

            "date":
                appointment_date,

            "slot":
                slot_time,
        })

    except Exception as error:

        connection.rollback()

        print(
            "APPOINTMENT BOOKING ERROR:",
            repr(error)
        )

        return jsonify({
            "error":
                "Unable to book the appointment."
        }), 500

    finally:

        connection.close()


# ============================================================
# PROFILE
# ============================================================

@app.route(
    "/profile",
    methods=["GET"]
)
@login_required
def profile():

    connection = get_db()

    try:

        user = connection.execute(
            """
            SELECT
                id,
                name,
                email
            FROM users
            WHERE id = ?
            """,
            (
                session["user_id"],
            ),
        ).fetchone()

        if not user:

            session.clear()

            return jsonify({
                "error":
                    "User not found."
            }), 404

        return jsonify({
            "success":
                True,

            "user": {
                "id":
                    user["id"],

                "name":
                    user["name"],

                "email":
                    user["email"],
            }
        })

    finally:

        connection.close()


# ============================================================
# CHANGE PASSWORD
# ============================================================

@app.route(
    "/change-password",
    methods=["POST"]
)
@login_required
def change_password():

    data = request.get_json(
        silent=True
    )

    if not data:

        return jsonify({
            "error":
                "Invalid request data."
        }), 400

    old_password = data.get(
        "old_password",
        ""
    )

    new_password = data.get(
        "new_password",
        ""
    )

    confirm_password = data.get(
        "confirm_password",
        ""
    )

    if not all([
        old_password,
        new_password,
        confirm_password,
    ]):

        return jsonify({
            "error":
                "Please fill in all password fields."
        }), 400

    if new_password != confirm_password:

        return jsonify({
            "error":
                "New passwords do not match."
        }), 400

    if len(new_password) < 6:

        return jsonify({
            "error":
                "New password must contain at least 6 characters."
        }), 400

    connection = get_db()

    try:

        user = connection.execute(
            """
            SELECT password
            FROM users
            WHERE id = ?
            """,
            (
                session["user_id"],
            ),
        ).fetchone()

        if not user:

            return jsonify({
                "error":
                    "User not found."
            }), 404

        if not check_password_hash(
            user["password"],
            old_password,
        ):

            return jsonify({
                "error":
                    "Old password is incorrect."
            }), 400

        new_password_hash = (
            generate_password_hash(
                new_password
            )
        )

        connection.execute(
            """
            UPDATE users
            SET password = ?
            WHERE id = ?
            """,
            (
                new_password_hash,
                session["user_id"],
            ),
        )

        connection.commit()

        session.clear()

        return jsonify({
            "success":
                True,

            "message":
                "Password changed successfully."
        })

    except Exception as error:

        connection.rollback()

        print(
            "CHANGE PASSWORD ERROR:",
            repr(error)
        )

        return jsonify({
            "error":
                "Unable to change password."
        }), 500

    finally:

        connection.close()


# ============================================================
# MY BOOKINGS
# ============================================================

@app.route(
    "/my-bookings",
    methods=["GET"]
)
@login_required
def my_bookings():

    connection = get_db()

    try:

        rows = connection.execute(
            """
            SELECT
                id,
                doctor_id,
                appointment_date,
                slot_time,
                status,
                created_at
            FROM appointments
            WHERE user_id = ?
            AND status = 'booked'
            ORDER BY
                appointment_date ASC,
                slot_time ASC
            """,
            (
                session["user_id"],
            ),
        ).fetchall()

        bookings = []

        for row in rows:

            doctor = get_doctor_by_id(
                row["doctor_id"]
            )

            if not doctor:
                continue

            can_modify = (
                appointment_changes_allowed(
                    row["appointment_date"],
                    row["slot_time"]
                )
            )

            bookings.append({

                "id":
                    row["id"],

                "doctor": {
                    "id":
                        doctor["id"],

                    "name":
                        doctor["name"],

                    "specialization":
                        doctor["specialization"],

                    "experience":
                        doctor["experience"],

                    "qualification":
                        doctor["qualification"],

                    "rating":
                        doctor["rating"],

                    "reviews":
                        doctor["reviews"],

                    "hospital":
                        doctor["hospital"],

                    "address":
                        doctor["address"],

                    "phone":
                        doctor["phone"],

                    "email":
                        doctor["email"],
                },

                "appointment_date":
                    row["appointment_date"],

                "slot_time":
                    row["slot_time"],

                "status":
                    row["status"],

                "can_modify":
                    can_modify,
            })

        return jsonify({
            "success":
                True,

            "bookings":
                bookings,
        })

    finally:

        connection.close()


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

    # ========================================================
    # ACCOUNT CREATION EMAIL
    # ========================================================

    send_email(
        email,
        "Welcome to MediGuide",
        f"""
Hello {name},

Welcome to MediGuide!

Your account has been successfully created.

You can now use MediGuide to:
- Get medical guidance
- Analyze blood reports
- Find relevant doctors
- Book appointments

We are happy to have you with us.

MediGuide Team
""".strip()
    )

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

        result = home_remedy_node(
            {
                "messages":
                    messages,

                "intent":
                    "home_remedy",
            }
        )

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

    if extension not in ALLOWED_REPORT_EXTENSIONS:

        return jsonify({
            "error":
                "Only digital PDF blood reports are supported."
        }), 400

    temporary_directory = tempfile.mkdtemp(
        prefix="mediguide_report_"
    )

    file_path = os.path.join(
        temporary_directory,
        filename,
    )

    connection = get_db()

    try:

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

        conversation_id = request.form.get(
            "conversation_id"
        )

        user_id = session[
            "user_id"
        ]

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

        if answer.startswith(
            "REPORT_ANALYSIS_ERROR:"
        ):

            error_message = answer.replace(
                "REPORT_ANALYSIS_ERROR:",
                "",
                1,
            ).strip()

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

    # ========================================================
    # START APPOINTMENT REMINDER WORKER
    # ========================================================

    reminder_thread = threading.Thread(
        target=appointment_reminder_worker,
        daemon=True,
    )

    reminder_thread.start()

    app.run(
        host="0.0.0.0",
        port=8000,
        debug=True,
        use_reloader=False,
    )