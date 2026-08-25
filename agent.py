import json
import os
import re

from datetime import datetime
from typing import TypedDict

from dotenv import load_dotenv

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END

from tools import (
    search_medical_guidelines,
    search_medical_web,
    search_home_remedies_web,
    search_yoga_web,
)


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()

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
# LLM
# ============================================================

llm = ChatOpenAI(
    model=QWEN_MODEL,
    temperature=0.1,
    api_key=QWEN_API_KEY,
    base_url=QWEN_BASE_URL,
)


# ============================================================
# STATE
# ============================================================

class AgentState(TypedDict, total=False):

    messages: list

    enough_information: bool

    intent: str

    consultation_response: str

    retrieved_information: str

    retrieval_source: str

    rag_relevant: bool

    final_answer: str

    already_given_advice: str


# ============================================================
# MESSAGE HELPERS
# ============================================================

def get_message_content(message):

    if isinstance(
        message,
        dict
    ):

        return str(
            message.get(
                "content",
                ""
            )
        )

    if hasattr(
        message,
        "content"
    ):

        return str(
            message.content
        )

    return str(
        message
    )


def get_message_role(message):

    if isinstance(
        message,
        dict
    ):

        role = message.get(
            "role",
            "user"
        )

        if role == "human":
            return "user"

        if role == "ai":
            return "assistant"

        return role

    message_type = getattr(
        message,
        "type",
        "user"
    )

    if message_type == "human":
        return "user"

    if message_type == "ai":
        return "assistant"

    return message_type


def conversation_text(messages):

    output = []

    for message in messages:

        role = get_message_role(
            message
        )

        content = get_message_content(
            message
        ).strip()

        if not content:
            continue

        output.append(
            f"{role}: {content}"
        )

    return "\n".join(
        output
    )


def user_conversation_text(messages):

    output = []

    for message in messages:

        role = get_message_role(
            message
        )

        if role != "user":
            continue

        content = get_message_content(
            message
        ).strip()

        if content:

            output.append(
                content
            )

    return "\n".join(
        output
    )

def current_topic_context(messages):
    """
    Return only the conversation belonging to the patient's
    current/latest medical complaint.

    Older completed complaints remain in chat history/database,
    but are not mixed into the current medical answer.
    """

    if not messages:
        return ""

    # --------------------------------------------------------
    # Find the latest user message that looks like a NEW
    # medical complaint.
    # --------------------------------------------------------

    complaint_patterns = [
        r"^\s*i\s+have\s+",
        r"^\s*i'm\s+having\s+",
        r"^\s*i\s+am\s+having\s+",
        r"^\s*i'm\s+experiencing\s+",
        r"^\s*i\s+am\s+experiencing\s+",
        r"^\s*i\s+feel\s+",
        r"^\s*i\s+am\s+feeling\s+",
        r"^\s*my\s+\w+",
        r"^\s*suffering\s+from\s+",
        r"^\s*i\s+have\s+been\s+",
        r"^\s*i've\s+been\s+",
    ]

    medication_patterns = [
        r"\bi\s+have\s+taken\b",
        r"\bi\s+have\s+been\s+taking\b",
        r"\bi\s+am\s+taking\b",
        r"\bi'm\s+taking\b",
        r"\bi\s+took\b",
        r"\bi\s+used\b",
    ]

    latest_complaint_index = None

    for index in range(len(messages) - 1, -1, -1):

        message = messages[index]

        if get_message_role(message) != "user":
            continue

        content = get_message_content(message).strip()

        if not content:
            continue

        # Do not mistake medicine answers for a new complaint.
        if any(
            re.search(
                pattern,
                content,
                flags=re.IGNORECASE,
            )
            for pattern in medication_patterns
        ):
            continue

        if any(
            re.search(
                pattern,
                content,
                flags=re.IGNORECASE,
            )
            for pattern in complaint_patterns
        ):
            latest_complaint_index = index
            break

    # --------------------------------------------------------
    # If no clear new complaint is found, use the recent
    # conversation. This handles follow-up answers such as:
    #
    # "60 days"
    # "thinning all over"
    # "no"
    # --------------------------------------------------------

    if latest_complaint_index is None:

        recent_messages = messages[-12:]

        return conversation_text(
            recent_messages
        )

    # --------------------------------------------------------
    # Keep only messages from the current complaint onwards.
    # --------------------------------------------------------

    current_messages = messages[
        latest_complaint_index:
    ]

    return conversation_text(
        current_messages
    )


def clean_json_response(text):

    text = str(
        text
    ).strip()

    text = re.sub(
        r"^```json\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"^```\s*",
        "",
        text,
    )

    text = re.sub(
        r"\s*```$",
        "",
        text,
    )

    return text.strip()


# ============================================================
# CURRENT DATE / TIME
# ============================================================

def get_current_datetime():

    now = datetime.now().astimezone()

    return {
        "date":
            now.strftime("%Y-%m-%d"),

        "time":
            now.strftime("%I:%M %p"),

        "day":
            now.strftime("%A"),

        "iso":
            now.isoformat(),
    }


# ============================================================
# SEARCH QUERY
# ============================================================

def build_search_query(
    messages,
    max_length=1200,
):

    """
    Build a clean medical search query.

    IMPORTANT:
    Do NOT send:
    - uploaded file names
    - UI messages
    - attachment labels
    - full conversation blindly
    - unnecessary filler

    Only patient-provided clinical information is used.
    """

    clinical_parts = []

    current_messages = current_topic_messages(
    messages
    )

    for message in current_messages:

        role = get_message_role(
            message
        )

        if role != "user":
            continue

        content = get_message_content(
            message
        ).strip()

        if not content:
            continue

        # ----------------------------------------------------
        # REMOVE UPLOADED FILE MESSAGES
        # ----------------------------------------------------

        if content.startswith(
            "📎 Uploaded blood report:"
        ):
            continue

        if content.lower().startswith(
            "uploaded blood report:"
        ):
            continue

        # ----------------------------------------------------
        # REMOVE UI / NON-CLINICAL CONTENT
        # ----------------------------------------------------

        if content.lower() in {
            "hi",
            "hello",
            "hey",
            "ok",
            "okay",
            "yes",
            "no",
            "nahi",
            "nhi",
            "haan",
            "han",
        }:
            continue

        clinical_parts.append(
            content
        )

    if not clinical_parts:

        return ""

    # --------------------------------------------------------
    # COMBINE ONLY PATIENT INFORMATION
    # --------------------------------------------------------

    text = " ".join(
        clinical_parts
    )

    # --------------------------------------------------------
    # REMOVE COMMON CONVERSATIONAL FILLERS
    # --------------------------------------------------------

    text = re.sub(
        r"\b(?:please|tell me|can you tell me|"
        r"what should i do|what can i do|"
        r"i want to know|let me know)\b",
        " ",
        text,
        flags=re.IGNORECASE,
    )

    # --------------------------------------------------------
    # NORMALIZE WHITESPACE
    # --------------------------------------------------------

    text = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()

    # --------------------------------------------------------
    # KEEP QUERY REASONABLY SMALL
    # --------------------------------------------------------

    if len(text) > max_length:

        text = text[
            -max_length:
        ]

    return text

def current_topic_messages(messages):
    """
    Return messages belonging to the latest medical complaint.
    """

    if not messages:
        return []

    complaint_patterns = [
        r"^\s*i\s+have\s+",
        r"^\s*i'm\s+having\s+",
        r"^\s*i\s+am\s+having\s+",
        r"^\s*i'm\s+experiencing\s+",
        r"^\s*i\s+am\s+experiencing\s+",
        r"^\s*i\s+feel\s+",
        r"^\s*i\s+am\s+feeling\s+",
        r"^\s*my\s+\w+",
        r"^\s*suffering\s+from\s+",
        r"^\s*i\s+have\s+been\s+",
        r"^\s*i've\s+been\s+",
    ]

    medication_patterns = [
        r"\bi\s+have\s+taken\b",
        r"\bi\s+have\s+been\s+taking\b",
        r"\bi\s+am\s+taking\b",
        r"\bi'm\s+taking\b",
        r"\bi\s+took\b",
        r"\bi\s+used\b",
    ]

    start_index = None

    for index in range(len(messages) - 1, -1, -1):

        message = messages[index]

        if get_message_role(message) != "user":
            continue

        content = get_message_content(message).strip()

        if not content:
            continue

        if any(
            re.search(
                pattern,
                content,
                flags=re.IGNORECASE,
            )
            for pattern in medication_patterns
        ):
            continue

        if any(
            re.search(
                pattern,
                content,
                flags=re.IGNORECASE,
            )
            for pattern in complaint_patterns
        ):
            start_index = index
            break

    if start_index is None:
        return messages[-12:]

    return messages[start_index:]


def current_topic_context(messages):

    return conversation_text(
        current_topic_messages(messages)
    )

# ============================================================
# CONSULTATION
# ============================================================

def consultation_node(
    state: AgentState
):

    messages = state.get(
        "messages",
        []
    )

    history = current_topic_context(
    messages
)

    current = get_current_datetime()

    prompt = f"""
You are the consultation doctor for MediGuide AI.

Your job is to collect the IMPORTANT clinical information
needed to give a safe and relevant medical answer.

Do NOT immediately give the final medical answer.

Ask questions naturally, ONE concise question at a time.

============================================================
CURRENT DATE AND TIME
============================================================

Current date:
{current["date"]}

Current time:
{current["time"]}

Current day:
{current["day"]}

Understand relative time naturally.

============================================================
MOST IMPORTANT RULE
============================================================

Before:

"enough_information": true

make sure enough useful clinical information has been
collected for THIS complaint.

Do not finish the consultation merely because the patient
mentioned the main symptom.

The information will be used by:

1. Standard Treatment Guidelines PDF
2. Medical web fallback

Therefore collect enough information for either source.

============================================================
BASIC CLINICAL INFORMATION
============================================================

Collect what is clinically relevant:

• Main complaint
• Duration / when it started
• Severity when relevant
• Important associated symptoms
• Medicine already taken
• Age when relevant
• Important medical conditions
• Medicine allergies

Do NOT ask unnecessary questions.

============================================================
FEVER
============================================================

If the patient has fever, DO NOT finish until you know:

1. Temperature
2. Duration
3. Important associated symptoms
4. Medicine already taken
5. Age
6. Important medical conditions or medicine allergies

Temperature is REQUIRED.

Example:

Patient:
"I have fever since yesterday."

Assistant:
"What is your temperature right now?"

============================================================
ASSOCIATED SYMPTOMS
============================================================

If the patient says:

"yes"

to:

"Do you have other symptoms?"

ask which symptoms.

Example:

"Which symptoms are you having — cough, sore throat,
body aches, headache, vomiting, diarrhea, or anything else?"

If patient says:

"no"

record that no other symptoms were reported.

============================================================
MEDICINE
============================================================

If medicine can affect the recommendation, ask:

"Have you taken any medicine for this?"

If yes, ask the medicine name if unknown.

Do NOT repeatedly ask information already provided.

============================================================
AGE
============================================================

Ask age when it can affect treatment, dosage or risk.

For fever, age is REQUIRED.

============================================================
CONDITIONS / ALLERGIES
============================================================

Ask:

"Do you have any medical conditions or medicine allergies?"

Do not ask for an exhaustive medical history.

============================================================
EMERGENCY
============================================================

If the patient clearly describes:

• severe difficulty breathing
• severe chest pain
• unconsciousness
• seizure
• severe bleeding
• sudden weakness or paralysis
• severe confusion
• severe dehydration
• rapidly worsening condition

stop routine questioning and advise urgent medical care.

============================================================
INTENT
============================================================

When enough information is available, determine intent.

Return exactly one:

medical
home_remedy
yoga

medical:
• medicine
• treatment
• dosage
• medical advice
• patient simply describes a complaint

home_remedy:
• home remedies
• natural remedies
• things to do at home

yoga:
• yoga
• yoga poses
• yoga exercises
• gentle yoga movements

============================================================
LANGUAGE
============================================================

Use the same language as the patient.

English → simple English.

Hinglish → simple Hinglish.

============================================================
OUTPUT
============================================================

Return ONLY valid JSON.

If information is NOT enough:

{{
    "enough_information": false,
    "intent": "medical",
    "response": "ONE short natural question"
}}

If information IS enough:

{{
    "enough_information": true,
    "intent": "medical",
    "response": ""
}}

============================================================
PATIENT CONVERSATION
============================================================

{history}
"""

    try:

        response = llm.invoke(
            [
                HumanMessage(
                    content=prompt
                )
            ]
        )

        raw = clean_json_response(
            response.content
        )

        data = json.loads(
            raw
        )

    except Exception as error:

        print(
            "CONSULTATION ERROR:",
            repr(error)
        )

        return {
            **state,

            "enough_information":
                False,

            "intent":
                "medical",

            "consultation_response":
                "I couldn't process that right now. Please try again.",

            "final_answer":
                "I couldn't process that right now. Please try again.",
        }

    enough = bool(
        data.get(
            "enough_information",
            False
        )
    )

    intent = str(
        data.get(
            "intent",
            "medical"
        )
    ).strip().lower()

    if intent not in {
        "medical",
        "home_remedy",
        "yoga",
    }:

        intent = "medical"

    response_text = str(
        data.get(
            "response",
            ""
        ) or ""
    ).strip()

    if not enough:

        if not response_text:

            response_text = (
                "Could you tell me a little more "
                "about your symptoms?"
            )

        return {
            **state,

            "enough_information":
                False,

            "intent":
                intent,

            "consultation_response":
                response_text,

            "final_answer":
                response_text,
        }

    return {
        **state,

        "enough_information":
            True,

        "intent":
            intent,

        "consultation_response":
            "",

        "final_answer":
            "",
    }


# ============================================================
# INTENT NODE
# ============================================================

def intent_node(
    state: AgentState
):

    intent = state.get(
        "intent",
        "medical"
    )

    if intent not in {
        "medical",
        "home_remedy",
        "yoga",
    }:

        intent = "medical"

    return {
        **state,
        "intent":
            intent,
    }


# ============================================================
# MEDICAL RAG
# ============================================================

def medical_retrieval_node(
    state: AgentState
):

    messages = state.get(
        "messages",
        []
    )

    conversation = current_topic_context(
    messages
)

    if not conversation:

        conversation = "medical complaint"

    query = (
        "Medical treatment and management question.\n\n"
        "Patient clinical information:\n"
        + conversation
    )

    print(
        "\n"
        + "=" * 70
    )

    print(
        "MEDICAL SOURCE: STANDARD TREATMENT GUIDELINES"
    )

    print(
        "Searching PDF..."
    )

    try:

        result = (
            search_medical_guidelines.invoke(
                {
                    "query":
                        query
                }
            )
        )

    except Exception as error:

        print(
            "RAG ERROR:",
            repr(error)
        )

        result = (
            "NO_RELEVANT_INFORMATION_FOUND"
        )

    if (
        not result
        or
        "NO_RELEVANT_INFORMATION_FOUND"
        in result
    ):

        print(
            "PDF: NO RESULT"
        )

        return {
            **state,

            "retrieved_information":
                "",

            "retrieval_source":
                "NONE",

            "rag_relevant":
                False,
        }

    print(
        "PDF chunks found."
    )

    return {
        **state,

        "retrieved_information":
            result,

        "retrieval_source":
            "PDF",

        "rag_relevant":
            False,
    }


# ============================================================
# RAG RELEVANCE CHECK
# ============================================================

def rag_relevance_node(
    state: AgentState
):

    retrieved = state.get(
        "retrieved_information",
        ""
    )

    messages = state.get(
        "messages",
        []
    )

    conversation = current_topic_context(
    messages
    )

    if not retrieved:

        return {
            **state,

            "rag_relevant":
                False,

            "retrieval_source":
                "NONE",
        }

    prompt = f"""
You are a medical information relevance checker.

Determine whether the retrieved Standard Treatment
Guideline content is actually relevant enough to answer
the patient's CURRENT medical problem.

Patient information:

{conversation}

Retrieved guideline content:

{retrieved}

============================================================
RULES
============================================================

Return RELEVANT only if the retrieved content contains
useful information directly applicable to the patient's
complaint and current clinical situation.

Examples:

Patient has fever and retrieved content contains fever
management → RELEVANT.

Patient has headache and retrieved content is only about
unrelated surgery → NOT_RELEVANT.

Do not mark relevant merely because the words "fever",
"medicine", "patient", etc. appear somewhere.

The content must actually help answer the patient.

Return ONLY JSON:

{{
    "relevant": true
}}

or:

{{
    "relevant": false
}}
"""

    try:

        response = llm.invoke(
            [
                HumanMessage(
                    content=prompt
                )
            ]
        )

        raw = clean_json_response(
            response.content
        )

        data = json.loads(
            raw
        )

        relevant = bool(
            data.get(
                "relevant",
                False
            )
        )

    except Exception as error:

        print(
            "RAG RELEVANCE ERROR:",
            repr(error)
        )

        relevant = False

    print(
        "RAG RELEVANT:",
        relevant
    )

    if relevant:

        return {
            **state,

            "rag_relevant":
                True,

            "retrieval_source":
                "PDF",
        }

    return {
        **state,

        "rag_relevant":
            False,

        "retrieval_source":
            "NONE",

        "retrieved_information":
            "",
    }


# ============================================================
# MEDICAL WEB FALLBACK
# ============================================================

def medical_web_node(
    state: AgentState
):

    messages = state.get(
        "messages",
        []
    )

    # ========================================================
    # BUILD CLEAN CLINICAL QUERY
    # ========================================================

    conversation = build_search_query(
        messages
    )

    if not conversation:

        conversation = (
            "medical symptoms treatment guidance"
        )

    print(
        "\n"
        + "=" * 70
    )

    print(
        "PDF NOT RELEVANT"
    )

    print(
        "SWITCHING TO MEDICAL WEB SEARCH"
    )

    print(
        "CLEAN MEDICAL QUERY:"
    )

    print(
        conversation
    )

    try:

        result = (
            search_medical_web.invoke(
                {
                    "query":
                        conversation
                }
            )
        )

    except Exception as error:

        print(
            "MEDICAL WEB ERROR:",
            repr(error)
        )

        result = (
            "NO_MEDICAL_WEB_CONTENT_FOUND"
        )

    if (
        not result
        or
        "NO_MEDICAL_WEB_CONTENT_FOUND"
        in result
    ):

        print(
            "MEDICAL WEB: NO RESULT"
        )

        return {
            **state,

            "retrieved_information":
                "",

            "retrieval_source":
                "NONE",
        }

    print(
        "MEDICAL WEB: RESULT FOUND"
    )

    return {
        **state,

        "retrieved_information":
            result,

        "retrieval_source":
            "WEB",
    }


# ============================================================
# HOME REMEDY
# ============================================================

def home_remedy_node(
    state: AgentState
):

    messages = state.get(
        "messages",
        []
    )

    query = build_search_query(
        messages
    )

    if not query:

        query = (
            "safe home remedies self care"
        )

    # ========================================================
    # FIND MAIN MEDICAL ANSWER
    # ========================================================

    already_given = (
        extract_main_answer_from_history(
            messages
        )
    )

    print(
        "\n"
        + "=" * 70
    )

    print(
        "HOME REMEDY SEARCH"
    )

    print(
        "Already-given medical answer:"
    )

    print(
        already_given[:1500]
    )

    # ========================================================
    # WEB SEARCH
    # DDGS FIRST -> GOOGLE FALLBACK
    # ========================================================

    try:

        result = (
            search_home_remedies_web.invoke(
                {
                    "query":
                        query
                }
            )
        )

    except Exception as error:

        print(
            "HOME REMEDY ERROR:",
            repr(error)
        )

        result = (
            "NO_HOME_REMEDY_RESULTS_FOUND"
        )

    return {
        **state,

        "retrieved_information":
            result,

        "retrieval_source":
            "WEB",

        # IMPORTANT:
        # Pass previous medical answer to answer_node.
        "already_given_advice":
            already_given,
    }


# ============================================================
# YOGA
# ============================================================

def yoga_node(
    state: AgentState
):

    messages = state.get(
        "messages",
        []
    )

    query = build_search_query(
        messages
    )

    if not query:

        query = "safe gentle yoga"

    try:

        result = (
            search_yoga_web.invoke(
                {
                    "query":
                        query
                }
            )
        )

    except Exception as error:

        print(
            "YOGA ERROR:",
            repr(error)
        )

        result = (
            "NO_YOGA_RESULTS_FOUND"
        )

    return {
        **state,

        "retrieved_information":
            result,

        "retrieval_source":
            "WEB",
    }


# ============================================================
# FINAL ANSWER
# ============================================================

def answer_node(
    state: AgentState
):

    messages = state.get(
        "messages",
        []
    )

    history = current_topic_context(
    messages
)

    intent = state.get(
        "intent",
        "medical"
    )

    retrieved = state.get(
        "retrieved_information",
        ""
    )

    source = state.get(
        "retrieval_source",
        "NONE"
    )

    # ========================================================
    # RESPONSE SOURCE - TERMINAL ONLY
    # ========================================================

    if source == "PDF":

        print(
            "\n"
            + "=" * 70
        )

        print(
            "FINAL RESPONSE SOURCE: "
            "RAG / STANDARD TREATMENT GUIDELINES"
        )

        print(
            "=" * 70
        )

    elif source == "WEB":

        print(
            "\n"
            + "=" * 70
        )

        print(
            "FINAL RESPONSE SOURCE: "
            "WEB SEARCH / AGENT"
        )

        print(
            "=" * 70
        )

    else:

        print(
            "\n"
            + "=" * 70
        )

        print(
            "FINAL RESPONSE SOURCE: NONE"
        )

        print(
            "=" * 70
        )

    # ========================================================
    # NOTHING FOUND
    # ========================================================

    if (
        source == "NONE"
        or not retrieved
    ):

        if intent == "home_remedy":

            fallback = (
                "I couldn't find enough reliable information "
                "to suggest specific home remedies."
            )

        elif intent == "yoga":

            fallback = (
                "I couldn't find enough reliable information "
                "to suggest specific yoga or physical activity."
            )

        else:

            fallback = (
                "I couldn't find enough reliable information "
                "to give a specific medical recommendation."
            )

        return {
            **state,

            "final_answer":
                fallback,
        }

    # ========================================================
    # HOME REMEDIES PROMPT
    # ========================================================

    if intent == "home_remedy":

        already_given = state.get(
            "already_given_advice",
            ""
        )

        prompt = f"""
You are MediGuide AI.

Generate ONLY a short HOME REMEDIES response for the patient.

============================================================
PATIENT CONVERSATION
============================================================

{history}

============================================================
ALREADY GIVEN MAIN MEDICAL RESPONSE
============================================================

{already_given}

============================================================
NEW WEB INFORMATION
============================================================

{retrieved}

============================================================
MOST IMPORTANT RULE — NO DUPLICATES
============================================================

The "ALREADY GIVEN MAIN MEDICAL RESPONSE" has already been
shown to the patient.

You MUST NOT repeat any advice that is already present there.

This includes:

• Exact duplicate advice
• Same advice with different wording
• Paraphrased advice
• Advice that has the same practical action
• Advice that is only slightly reworded

Examples:

Already given:
"Drink plenty of fluids."

DO NOT write:
"Drink lots of water."
"Keep yourself hydrated."
"Have plenty of fluids."

These are the SAME recommendation.

------------------------------------------------------------

Already given:
"Get enough rest."

DO NOT write:
"Take adequate rest."
"Rest properly."
"Avoid exertion and get plenty of rest."

These are the SAME recommendation.

------------------------------------------------------------

Already given:
"Gargle with warm salt water."

DO NOT write:
"Try warm salt-water gargles."
"Rinse your throat with warm salty water."

These are the SAME recommendation.

============================================================
WHAT YOU SHOULD DO
============================================================

From the NEW WEB INFORMATION:

1. Identify useful home-care recommendations.

2. Compare every recommendation with the
   ALREADY GIVEN MAIN MEDICAL RESPONSE.

3. Remove anything that is already given or substantially
   overlaps with something already given.

4. Return ONLY genuinely additional recommendations.

5. If there are no genuinely new recommendations,
   say:

"No additional home remedies were found beyond the advice
already provided."

Do NOT invent a remedy just to make the answer longer.

============================================================
SAFETY
============================================================

Use only information supported by the retrieved web content.

Do NOT provide:

• Medicines
• Drug names
• Dosages
• Medication frequency
• Prescription instructions
• Diagnosis
• Treatment plan
• Unsupported medical claims

Do NOT tell the patient to start or stop medication.

Do NOT turn a general home remedy into a medical treatment.

============================================================
FORMAT
============================================================

Start the response with this exact heading:

**Home Remedies**

Then write one short introductory sentence.

Then use:

For now:
• ...
• ...
• ...
• ...

Example format:

**Home Remedies**

Based on your symptoms, here are some home remedies that may help.

For now:
• Drink plenty of fluids like water, juices, or warm broth to stay hydrated.
• Get enough rest and wear light clothing to keep your body comfortable.
• Gargle with warm salt water to soothe your sore throat.
• Keep your room cool and use a damp cloth on your forehead for relief.

============================================================
MINIMUM 4 UNIQUE HOME REMEDIES
============================================================

You MUST try to provide AT LEAST 4 genuinely different
additional home-remedy recommendations.

However, the 4 recommendations MUST satisfy all of these:

• They must NOT already appear in the main medical response.
• They must NOT be paraphrases of existing advice.
• They must NOT be duplicates of each other.
• They must be supported by the NEW WEB INFORMATION.
• They must be appropriate for the patient's symptoms.
• Do NOT invent a recommendation just to reach 4.

If the retrieved web information contains fewer than
4 safe and genuinely new recommendations, return only
the genuinely supported recommendations.

NEVER repeat an existing recommendation merely to reach 4.

============================================================
DUPLICATE CHECK
============================================================

Before returning each recommendation, compare it against:

1. ALREADY GIVEN MAIN MEDICAL RESPONSE
2. ALL OTHER HOME REMEDIES YOU ARE ABOUT TO RETURN

Reject a recommendation if it:

• Has the same practical action
• Is only a wording change
• Is a paraphrase
• Is a more general version of an existing point
• Is a more specific version of an existing point

Example:

Already given:
"Drink plenty of fluids."

Reject:
"Drink more water."
"Stay hydrated."
"Drink warm fluids."

These are overlapping recommendations.

Example:

Already given:
"Get enough rest."

Reject:
"Take adequate rest."
"Avoid strenuous activity and rest."
"Sleep well."

These substantially overlap with the existing advice.

============================================================
FORMAT
============================================================

Start with:

"Here are some additional home remedies that may help:"

Then:

For now:
• ...
• ...
• ...
• ...

Prefer 4 unique bullets when 4 genuinely supported
recommendations are available.

Do not use more than 4 bullets.

If fewer than 4 genuinely new and supported remedies
are available, use fewer than 4 rather than inventing
or duplicating advice.

Do not use tables.

Do not explain the filtering process.

Do not mention internal systems.

Every bullet must be genuinely different from the
already-given medical advice.

Do not repeat the same recommendation using different words.

Do not use tables.

Do not explain your filtering process.

Do not mention internal systems.

============================================================
LANGUAGE
============================================================

Use the same language as the patient.

English → simple English.

Hinglish → simple Hinglish.

============================================================
FINAL RULE
============================================================

The patient has ALREADY SEEN the main medical response.

Therefore:

NEW INFORMATION ONLY.

No duplicates.
No paraphrased duplicates.
No overlapping recommendations.
"""

    # ========================================================
    # YOGA PROMPT
    # ========================================================

    elif intent == "yoga":

        prompt = f"""
You are MediGuide AI.

Generate ONLY a short YOGA / PHYSICAL ACTIVITY response
for the patient.

============================================================
PATIENT CONVERSATION
============================================================

{history}

============================================================
RETRIEVED INFORMATION
============================================================

{retrieved}

============================================================
YOGA RULES
============================================================

Use ONLY information supported by the retrieved content.

This response is ONLY about:

• Yoga
• Gentle stretching
• Physical activity
• Rest related to physical activity
• Whether yoga should be avoided

DO NOT include:

• Medicine
• Medicines
• Medication
• Drug names
• Dosages
• A "Medicine:" section
• A "See a doctor if:" section
• Doctor/medical warning sections
• General medical treatment unrelated to yoga

If the patient has fever or another condition where yoga
should be avoided, clearly say so.

Do NOT repeat the main medical treatment response.

Keep it SHORT.

============================================================
FORMAT
============================================================

Start the response with this exact heading:

**Yoga**

Then write one short introductory sentence.

Then use:

For now:
• ...
• ...
• ...
• ...

Use 4 concise bullets.

Every actionable point MUST start with:

•

Each bullet must be on its own line.

Do not use:

-
*
1.
2.
3.

Do not use tables.

Do not explain reasoning.

Do not copy the retrieved content word-for-word.

Do not mention internal systems.

============================================================
LANGUAGE
============================================================

Use the same language as the patient.

English → simple English.

Hinglish → simple Hinglish.

============================================================
FINAL ANSWER
============================================================

Return ONLY the patient-facing yoga answer.
"""

    # ========================================================
    # MAIN MEDICAL PROMPT
    # ========================================================

    else:

        prompt = f"""
You are MediGuide AI.

The patient consultation is complete.

Give a SHORT, clear, practical patient-facing answer.

============================================================
PATIENT CONVERSATION
============================================================

{history}

============================================================
PATIENT INTENT
============================================================

{intent}

============================================================
SOURCE
============================================================

{source}

============================================================
RETRIEVED INFORMATION
============================================================

{retrieved}

============================================================
ANSWER RULES
============================================================

Use ONLY information supported by the retrieved content.

Do not invent:

• diagnosis
• medicine
• dosage
• frequency
• duration
• contraindications

If medicine information is available and relevant,
state it clearly.

============================================================
FORMAT
============================================================

Start with ONE short sentence.

Example:

Based on what you've told me, ...

Then:

For now:
• ...
• ...
• ...

Medicine:
• ...
• ...

See a doctor if:
• ...
• ...

Only include sections that are relevant.

============================================================
VERY IMPORTANT
============================================================

Keep it SHORT.

Target:

1 opening sentence

2–4 For now bullets

1–3 Medicine bullets if supported

2–3 See a doctor if bullets

Maximum about 8–10 bullets.

Do not repeat information.

Do not explain reasoning.

Do not copy the source.

Do not mention internal systems.

============================================================
BULLETS
============================================================

Every actionable point MUST start with:

•

Each bullet must be on its own line.

Do not use:

-
*
1.
2.
3.

Do not use tables.

============================================================
LANGUAGE
============================================================

Use the same language as the patient.

English → simple English.

Hinglish → simple Hinglish.

============================================================
DO NOT MENTION
============================================================

Never mention:

RAG
Chroma
FlashRank
PDF retrieval
web search
retrieval
vector database
tools
agent
internal reasoning
sources

============================================================
FINAL ANSWER
============================================================

Return ONLY the patient-facing answer.
"""

    # ========================================================
    # LLM RESPONSE
    # ========================================================

    try:

        response = llm.invoke(
            [
                HumanMessage(
                    content=prompt
                )
            ]
        )

        answer = str(
            response.content
        ).strip()

    except Exception as error:

        print(
            "FINAL ANSWER ERROR:",
            repr(error)
        )

        if intent == "home_remedy":

            answer = (
                "I couldn't complete the home-remedy "
                "response right now. Please try again."
            )

        elif intent == "yoga":

            answer = (
                "I couldn't complete the yoga response "
                "right now. Please try again."
            )

        else:

            answer = (
                "I couldn't complete the response right now. "
                "Please try again."
            )

    # ========================================================
    # CLEAN FORMAT
    # ========================================================

    answer = answer.replace(
        "\r\n",
        "\n"
    )

    answer = answer.replace(
        "\r",
        "\n"
    )

    answer = re.sub(
        r"```(?:text|markdown)?",
        "",
        answer,
        flags=re.IGNORECASE,
    )



    # ========================================================
    # EXTRA SAFETY:
    # REMOVE MEDICINE / DOCTOR SECTIONS FROM
    # HOME REMEDY AND YOGA RESPONSES ONLY
    # ========================================================

    if intent in {
        "home_remedy",
        "yoga",
    }:

        answer = re.split(
            r"\n\s*(?:Medicine|Medicines|Medication)\s*:",
            answer,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]

        answer = re.split(
            r"\n\s*See a doctor(?: if)?\s*:",
            answer,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]

        answer = re.split(
            r"\n\s*(?:When to see a doctor|Seek medical help|Medical attention)\s*:",
            answer,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]

    # Convert markdown bullets
    answer = re.sub(
        r"(?m)^\s*[-*]\s+",
        "• ",
        answer,
    )

    # Normalize bullet spacing
    answer = re.sub(
        r"[ \t]*•[ \t]*",
        "\n• ",
        answer,
    )

    # Remove duplicate blank lines
    answer = re.sub(
        r"\n\s*\n+",
        "\n",
        answer,
    )

    lines = []

    headers = {
        "for now:",
        "medicine:",
        "see a doctor if:",
    }

    current_section = None

    for line in answer.split("\n"):

        line = line.strip()

        if not line:
            continue

        lower = line.lower()

        # ====================================================
        # HOME/YOGA SAFETY:
        # Never allow these headers in suggestion responses
        # ====================================================

        if intent in {
            "home_remedy",
            "yoga",
        }:

            if lower in {
                "medicine:",
                "medicines:",
                "medication:",
                "see a doctor if:",
                "see a doctor:",
                "when to see a doctor:",
                "seek medical help:",
                "medical attention:",
            }:

                current_section = None
                continue

        if lower in headers:

            current_section = lower

            # Home remedy and yoga should only have
            # the "For now:" section.
            if intent in {
                "home_remedy",
                "yoga",
            }:

                if lower != "for now:":

                    continue

            lines.append(
                line
            )

            continue

        if line.startswith("•"):

            text = line[1:].strip()

            if text:

                lines.append(
                    "• " + text
                )

            continue

        if current_section:

            sentences = re.split(
                r"(?<=[.!?])\s+",
                line,
            )

            for sentence in sentences:

                sentence = sentence.strip()

                if sentence:

                    lines.append(
                        "• " + sentence
                    )

        else:

            lines.append(
                line
            )

    answer = "\n".join(
        lines
    ).strip()


# ========================================================
# ENSURE HOME REMEDIES / YOGA HEADING
# ========================================================

        # ========================================================
    # ENSURE HOME REMEDIES / YOGA HEADING
    # ========================================================

    if intent == "home_remedy":

        # Remove any existing variation of the heading
        answer = re.sub(
            r"(?im)^\s*(?:\*\*)?home remedies(?:\*\*)?\s*$",
            "",
            answer,
        )

        answer = (
            "**Home Remedies**\n"
            + answer.strip()
        )

    elif intent == "yoga":

        # Remove any existing variation of the heading
        answer = re.sub(
            r"(?im)^\s*(?:\*\*)?yoga(?:\*\*)?\s*$",
            "",
            answer,
        )

        answer = (
            "**Yoga**\n"
            + answer.strip()
        )

    return {
        **state,

        "final_answer":
            answer,
    }


# ============================================================
# CONSULTATION ROUTER
# ============================================================

def consultation_router(
    state: AgentState
):

    if state.get(
        "enough_information",
        False
    ):

        return "intent"

    return "end"


# ============================================================
# INTENT ROUTER
# ============================================================

def intent_router(
    state: AgentState
):

    intent = state.get(
        "intent",
        "medical"
    )

    if intent == "home_remedy":

        return "home_remedy"

    if intent == "yoga":

        return "yoga"

    return "medical"


# ============================================================
# EXTRACT ALREADY-GIVEN ADVICE
# ============================================================

def extract_main_answer_from_history(messages):
    """
    Find the most recent useful medical assistant answer.

    This is used by Home Remedies and Yoga so they do not
    repeat advice that was already given to the patient.
    """

    for message in reversed(messages):

        role = get_message_role(message)

        if role != "assistant":
            continue

        content = get_message_content(message).strip()

        if not content:
            continue

        # Ignore previous home-remedy/yoga style responses
        # if they are explicitly marked.
        lower = content.lower()

        if (
            "here are some home remedies" in lower
            or
            "suggestion for home remedies" in lower
            or
            "suggestion for yoga" in lower
        ):
            continue

        return content

    return ""


# ============================================================
# MEDICAL SOURCE ROUTER
# ============================================================

def medical_source_router(
    state: AgentState
):

    if state.get(
        "rag_relevant",
        False
    ):

        return "answer"

    return "medical_web"


# ============================================================
# GRAPH
# ============================================================

graph = StateGraph(
    AgentState
)


# ============================================================
# NODES
# ============================================================

graph.add_node(
    "consultation",
    consultation_node,
)

graph.add_node(
    "intent",
    intent_node,
)

graph.add_node(
    "medical",
    medical_retrieval_node,
)

graph.add_node(
    "rag_relevance",
    rag_relevance_node,
)

graph.add_node(
    "medical_web",
    medical_web_node,
)

graph.add_node(
    "home_remedy",
    home_remedy_node,
)

graph.add_node(
    "yoga",
    yoga_node,
)

graph.add_node(
    "answer",
    answer_node,
)


# ============================================================
# START
# ============================================================

graph.set_entry_point(
    "consultation"
)


# ============================================================
# CONSULTATION ROUTER
# ============================================================

graph.add_conditional_edges(
    "consultation",
    consultation_router,
    {
        "end":
            END,

        "intent":
            "intent",
    },
)


# ============================================================
# INTENT ROUTER
# ============================================================

graph.add_conditional_edges(
    "intent",
    intent_router,
    {
        "medical":
            "medical",

        "home_remedy":
            "home_remedy",

        "yoga":
            "yoga",
    },
)


# ============================================================
# MEDICAL RAG → RELEVANCE CHECK
# ============================================================

graph.add_edge(
    "medical",
    "rag_relevance",
)


# ============================================================
# RELEVANCE → ANSWER / WEB
# ============================================================

graph.add_conditional_edges(
    "rag_relevance",
    medical_source_router,
    {
        "answer":
            "answer",

        "medical_web":
            "medical_web",
    },
)


# ============================================================
# WEB → ANSWER
# ============================================================

graph.add_edge(
    "medical_web",
    "answer",
)


# ============================================================
# HOME REMEDY → ANSWER
# ============================================================

graph.add_edge(
    "home_remedy",
    "answer",
)


# ============================================================
# YOGA → ANSWER
# ============================================================

graph.add_edge(
    "yoga",
    "answer",
)


# ============================================================
# COMPILE
# ============================================================

agent = graph.compile()


# ============================================================
# BLOOD REPORT AGENT
# DIGITAL PDF ONLY
# ============================================================

from typing import TypedDict

from langgraph.graph import StateGraph, END

from tools import analyze_blood_report


# ============================================================
# BLOOD REPORT STATE
# ============================================================

class BloodReportState(
    TypedDict,
    total=False,
):

    file_path: str

    report_analysis: str

    final_answer: str


# ============================================================
# BLOOD REPORT NODE
# ============================================================

def analyze_blood_report_node(
    state: BloodReportState,
):

    file_path = state.get(
        "file_path",
        "",
    )

    print(
        "\n"
        + "=" * 70
    )

    print(
        "BLOOD REPORT AGENT"
    )

    print(
        "FILE:",
        file_path
    )

    print(
        "CALLING BLOOD REPORT TOOL"
    )

    result = analyze_blood_report.invoke(
        {
            "file_path":
                file_path,
        }
    )

    print(
        "BLOOD REPORT TOOL COMPLETED"
    )

    return {
        "file_path":
            file_path,

        "report_analysis":
            result,

        "final_answer":
            result,
    }


# ============================================================
# BLOOD REPORT GRAPH
# ============================================================

blood_report_graph = StateGraph(
    BloodReportState
)


# ============================================================
# NODE
# ============================================================

blood_report_graph.add_node(
    "analyze_blood_report",
    analyze_blood_report_node,
)


# ============================================================
# ENTRY
# ============================================================

blood_report_graph.set_entry_point(
    "analyze_blood_report"
)


# ============================================================
# END
# ============================================================

blood_report_graph.add_edge(
    "analyze_blood_report",
    END,
)


# ============================================================
# COMPILE
# ============================================================

blood_report_agent = (
    blood_report_graph.compile()
)