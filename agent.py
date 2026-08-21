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
    "qwen-plus",
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
    max_length=5000,
):

    text = user_conversation_text(
        messages
    )

    if not text:
        return ""

    if len(text) > max_length:

        text = text[
            -max_length:
        ]

    return text


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

    history = conversation_text(
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

    conversation = user_conversation_text(
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

    conversation = user_conversation_text(
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

    conversation = user_conversation_text(
        messages
    )

    if not conversation:

        conversation = "medical complaint"

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

    history = conversation_text(
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

        print("\n" + "=" * 70)
        print(
            "FINAL RESPONSE SOURCE: "
            "RAG / STANDARD TREATMENT GUIDELINES"
        )
        print("=" * 70)

    elif source == "WEB":

        print("\n" + "=" * 70)
        print(
            "FINAL RESPONSE SOURCE: "
            "WEB SEARCH / AGENT"
        )
        print("=" * 70)

    else:

        print("\n" + "=" * 70)
        print(
            "FINAL RESPONSE SOURCE: NONE"
        )
        print("=" * 70)

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

        prompt = f"""
You are MediGuide AI.

Generate ONLY a short HOME REMEDIES response for the patient.

============================================================
PATIENT CONVERSATION
============================================================

{history}

============================================================
RETRIEVED INFORMATION
============================================================

{retrieved}

============================================================
HOME REMEDIES RULES
============================================================

Use ONLY information supported by the retrieved content.

This response is ONLY for home remedies and self-care.

DO NOT include:

• Medicine
• Medicines
• Medication
• Drug names
• Dosages
• Frequency of medicines
• A "Medicine:" section
• A "See a doctor if:" section
• Doctor/medical warning sections
• Yoga recommendations unless specifically part of safe
  home self-care relevant to the patient's condition

Do NOT repeat the main medical treatment response.

Keep it SHORT.

============================================================
FORMAT
============================================================

Start with ONE short sentence.

Example:

Based on your symptoms, here are some home remedies that may help.

Then:

For now:
• ...
• ...
• ...
• ...

Use 2–4 concise bullets.

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

Return ONLY the patient-facing home-remedy answer.
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

Start with ONE short sentence.

Example:

Based on your fever, you should skip yoga for now.

Then:

For now:
• ...
• ...
• ...

Use 2–4 concise bullets.

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

    answer = answer.replace(
        "**",
        ""
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