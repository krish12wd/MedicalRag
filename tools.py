import html
import re

from urllib.parse import unquote

import requests

from ddgs import DDGS

from langchain_core.tools import tool

from retriever import search_guidelines




# ============================================================
# MEDICAL GUIDELINE TOOL
# ============================================================

@tool
def search_medical_guidelines(
    query: str
) -> str:
    """
    Search the Standard Treatment Guidelines PDF.

    This is the primary medical knowledge source.
    Use this for medical treatment, medicines, dosage,
    management, and guideline-based information.
    """

    documents = search_guidelines(
        query=query,
        retrieval_k=15,
        rerank_k=5,
        min_score=0.30,
    )

    # ========================================================
    # SECOND SEARCH
    # ========================================================

    if not documents:

        focused_query = re.sub(
            r"\b\d+(?:\.\d+)?\s*"
            r"(?:year|years|yr|yrs|day|days|week|weeks|"
            r"month|months|kg|mg|g|°?f|°?c)\b",
            "",
            query,
            flags=re.IGNORECASE,
        )

        focused_query = re.sub(
            r"\b(?:male|female|man|woman|adult|age|"
            r"temperature|temp|currently|today|yesterday|"
            r"please|tell|me|what|should|i|do)\b",
            "",
            focused_query,
            flags=re.IGNORECASE,
        )

        focused_query = " ".join(
            focused_query.split()
        )

        if (
            focused_query
            and
            focused_query.lower()
            != query.lower()
        ):

            documents = search_guidelines(
                query=focused_query,
                retrieval_k=15,
                rerank_k=5,
                min_score=0.30,
            )

    # ========================================================
    # NO RESULT
    # ========================================================

    if not documents:

        return (
            "NO_RELEVANT_INFORMATION_FOUND"
        )

    # ========================================================
    # RESULTS
    # ========================================================

    results = []

    for index, document in enumerate(
        documents,
        start=1,
    ):

        page_number = document.metadata.get(
            "page_number",
            "Unknown",
        )

        score = document.metadata.get(
            "rerank_score",
            "Unknown",
        )

        results.append(
            f"""
RESULT {index}

PAGE:
{page_number}

RELEVANCE SCORE:
{score}

CONTENT:
{document.page_content.strip()}
"""
        )

    return "\n".join(
        results
    )


# ============================================================
# HTML CLEANER
# ============================================================

def _clean_html(
    text: str
):

    text = re.sub(
        r"<script.*?</script>",
        " ",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    text = re.sub(
        r"<style.*?</style>",
        " ",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    text = re.sub(
        r"<[^>]+>",
        " ",
        text,
    )

    text = html.unescape(
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


# ============================================================
# SPECIALIZED SEARCH QUERY CLEANER
# ============================================================

def _clean_specialized_query(query: str) -> str:
    """
    Create a short search query for Home Remedies / Yoga.

    The agent may pass the entire conversation history as
    `query`. Search engines perform better with only the
    current symptom/topic.
    """

    query = str(query).strip()

    # Remove common conversational phrases
    query = re.sub(
        r"\b(?:i|im|i'm|ive|i've|my|me|please|tell|me|"
        r"what|should|can|could|would|do|have|has|had|"
        r"experiencing|experience)\b",
        " ",
        query,
        flags=re.IGNORECASE,
    )

    # Remove durations / measurements
    query = re.sub(
        r"\b\d+(?:\.\d+)?\s*"
        r"(?:year|years|yr|yrs|day|days|week|weeks|"
        r"month|months|hour|hours|kg|mg|g|°?f|°?c)\b",
        " ",
        query,
        flags=re.IGNORECASE,
    )

    # Remove standalone numbers
    query = re.sub(
        r"\b\d+(?:\.\d+)?\b",
        " ",
        query,
    )

    # Remove common medication details
    query = re.sub(
        r"\b(?:mr tablets?|tablets?|tablet|medicine|"
        r"medicines?|medication|medications|"
        r"capsules?|capsule|syrup)\b",
        " ",
        query,
        flags=re.IGNORECASE,
    )

    # Remove duplicate whitespace
    query = " ".join(query.split())

    # Keep the most relevant recent terms.
    # This prevents the entire previous conversation from
    # becoming part of the search query.
    words = query.split()

    if len(words) > 10:
        words = words[-10:]

    query = " ".join(words)

    return query.strip()





# ============================================================
# URL VALIDATION
# ============================================================

def _is_valid_url(
    url: str
):

    if not url:
        return False

    if not (
        url.startswith("http://")
        or url.startswith("https://")
    ):
        return False

    blocked = [
        "google.com",
        "google.co.in",
        "accounts.google.com",
        "support.google.com",
        "bing.com",
    ]

    lower_url = url.lower()

    return not any(
        domain in lower_url
        for domain in blocked
    )


# ============================================================
# GOOGLE URL
# ============================================================

def _extract_google_url(
    url: str
):

    if "/url?q=" in url:

        url = url.split(
            "/url?q=",
            1
        )[1]

    elif "url?q=" in url:

        url = url.split(
            "url?q=",
            1
        )[1]

    url = url.split(
        "&",
        1
    )[0]

    return unquote(
        url
    )


# ============================================================
# GOOGLE RESULTS
# ============================================================

def _parse_google_results(
    html_text: str
):

    results = []

    pattern = re.findall(
        r'<a[^>]+href="([^"]+)"[^>]*>'
        r'.*?<h3[^>]*>(.*?)</h3>',
        html_text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    for url, title_html in pattern:

        title = _clean_html(
            title_html
        )

        url = _extract_google_url(
            url
        )

        if (
            title
            and
            _is_valid_url(url)
        ):

            result = {
                "title":
                    title,

                "url":
                    url,

                "body":
                    "",
            }

            if result not in results:

                results.append(
                    result
                )

    return results[:10]


# ============================================================
# GOOGLE SEARCH
# ============================================================

def _google_search(
    query: str,
    num_results: int = 10,
):

    response = requests.get(
        "https://www.google.com/search",
        params={
            "q":
                query,

            "num":
                num_results,

            "hl":
                "en",
        },
        headers={
            "User-Agent":
                "Mozilla/5.0 "
                "(Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/150.0 Safari/537.36"
        },
        timeout=15,
    )

    response.raise_for_status()

    return _parse_google_results(
        response.text
    )


# ============================================================
# GENERIC WEB SEARCH
#
# DDGS FIRST
# GOOGLE FALLBACK
# ============================================================

def web_search(
    query: str,
    num_results: int = 10,
):

    print(
        "\n"
        + "=" * 70
    )

    print(
        "WEB SEARCH"
    )

    print(
        "QUERY:",
        query
    )

    # ========================================================
    # 1. DDGS FIRST
    # ========================================================

    try:

        print(
            "Trying DDGS..."
        )

        with DDGS(
            timeout=15
        ) as ddgs:

            results = ddgs.text(
                query,
                region="us-en",
                safesearch="moderate",
                max_results=num_results,
                backend="auto",
            )

        cleaned_results = []

        if results:

            for result in results:

                title = str(
                    result.get(
                        "title",
                        ""
                    )
                ).strip()

                url = str(
                    result.get(
                        "href",
                        ""
                    )
                ).strip()

                body = str(
                    result.get(
                        "body",
                        ""
                    )
                ).strip()

                if not url:
                    continue

                if not _is_valid_url(
                    url
                ):
                    continue

                cleaned_results.append(
                    {
                        "title":
                            title,

                        "url":
                            url,

                        "body":
                            body,
                    }
                )

        if cleaned_results:

            print(
                "DDGS returned "
                f"{len(cleaned_results)} results."
            )

            return cleaned_results

        print(
            "DDGS returned no usable results."
        )

    except Exception as error:

        print(
            "DDGS failed:",
            repr(error)
        )

    # ========================================================
    # 2. GOOGLE FALLBACK
    # ========================================================

    print(
        "Falling back to Google..."
    )

    try:

        google_results = _google_search(
            query,
            num_results=num_results,
        )

        if google_results:

            print(
                "Google returned "
                f"{len(google_results)} results."
            )

            return google_results

        print(
            "Google returned no results."
        )

    except Exception as error:

        print(
            "Google fallback failed:",
            repr(error)
        )

    # ========================================================
    # 3. NOTHING FOUND
    # ========================================================

    print(
        "No web search results found."
    )

    return []


# ============================================================
# FETCH WEBPAGE
# ============================================================

def _fetch_webpage_text(
    url: str,
    max_chars: int = 8000,
):

    try:

        response = requests.get(
            url,
            headers={
                "User-Agent":
                    "Mozilla/5.0 "
                    "(Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/150.0 Safari/537.36"
            },
            timeout=12,
        )

        response.raise_for_status()

        content_type = response.headers.get(
            "Content-Type",
            "",
        ).lower()

        if (
            "text/html"
            not in content_type
        ):

            return ""

        text = _clean_html(
            response.text
        )

        return text[:max_chars]

    except Exception as error:

        print(
            "WEBPAGE FETCH ERROR:",
            repr(error)
        )

        return ""


# ============================================================
# MEDICAL WEB SEARCH
# ============================================================

@tool
def search_medical_web(
    query: str
) -> str:
    """
    Search the web for medical information when the
    Standard Treatment Guidelines do not contain
    relevant information.

    DDGS is always tried first.
    Google is used as fallback.
    """

    # ========================================================
    # CLEAN QUERY
    # ========================================================

    query = str(
        query
    ).strip()

    query = re.sub(
        r"\s+",
        " ",
        query,
    )

    # ========================================================
    # TARGETED MEDICAL QUERY
    # ========================================================

    search_query = (
        f"{query} "
        f"medical guidance "
        f"clinical management"
    )

    print(
        "\n"
        + "=" * 70
    )

    print(
        "MEDICAL WEB FALLBACK"
    )

    print(
        "QUERY:"
    )

    print(
        search_query
    )

    try:

        results = web_search(
            search_query,
            num_results=10,
        )

    except Exception as error:

        print(
            "MEDICAL WEB SEARCH ERROR:",
            repr(error)
        )

        return (
            "NO_MEDICAL_WEB_CONTENT_FOUND"
        )

    if not results:

        return (
            "NO_MEDICAL_WEB_CONTENT_FOUND"
        )

    output = [
        "MEDICAL WEB SOURCES:"
    ]

    source_count = 0

    for result in results:

        url = result.get(
            "url",
            "",
        )

        title = result.get(
            "title",
            "",
        )

        snippet = result.get(
            "body",
            "",
        )

        if not url:
            continue

        # ----------------------------------------------------
        # TRY TO FETCH ACTUAL PAGE
        # ----------------------------------------------------

        content = _fetch_webpage_text(
            url
        )

        # ----------------------------------------------------
        # FALLBACK TO SEARCH SNIPPET
        # ----------------------------------------------------

        if not content:

            content = snippet

        if not content:

            continue

        source_count += 1

        output.append(
            f"""
SOURCE {source_count}

TITLE:
{title}

URL:
{url}

CONTENT:
{content}
"""
        )

        if source_count >= 5:

            break

    if source_count == 0:

        return (
            "NO_MEDICAL_WEB_CONTENT_FOUND"
        )

    print(
        f"MEDICAL WEB SOURCES USED: "
        f"{source_count}"
    )

    return "\n".join(
        output
    )

# ============================================================
# HOME REMEDY WEB SEARCH
# ============================================================

@tool
def search_home_remedies_web(
    query: str
) -> str:
    """
    Search the web for safe home-remedy and self-care
    information relevant to the patient's current symptoms.
    """

    clean_query = _clean_specialized_query(query)

    search_query = (
        f"{clean_query} "
        f"home remedies self care"
    )

    print(
        "\nHOME REMEDY WEB SEARCH:"
    )

    print(
        "CLEAN QUERY:",
        clean_query
    )

    print(
        "SEARCH QUERY:",
        search_query
    )

    try:

        results = web_search(
            search_query,
            num_results=8,
        )

    except Exception as error:

        print(
            "HOME REMEDY SEARCH ERROR:",
            repr(error)
        )

        return (
            "HOME_REMEDY_SEARCH_ERROR: "
            + str(error)
        )

    if not results:

        return (
            "NO_HOME_REMEDY_RESULTS_FOUND"
        )

    output = [
        "WEB HOME REMEDY SEARCH RESULTS:"
    ]

    for index, result in enumerate(
        results,
        start=1,
    ):

        title = result.get(
            "title",
            "",
        )

        url = result.get(
            "url",
            "",
        )

        snippet = result.get(
            "body",
            "",
        )

        output.append(
            f"""
RESULT {index}

TITLE:
{title}

URL:
{url}

SUMMARY:
{snippet}
"""
        )

    return "\n".join(
        output
    )

# ============================================================
# YOGA WEB SEARCH
# ============================================================

@tool
def search_yoga_web(
    query: str
) -> str:
    """
    Search the web for gentle and safe yoga information
    relevant to the patient's current symptoms.

    Do not claim that yoga cures or treats a disease.
    """

    clean_query = _clean_specialized_query(query)

    search_query = (
        f"{clean_query} "
        f"gentle yoga stretches beginner safe"
    )

    print(
        "\nYOGA WEB SEARCH:"
    )

    print(
        "CLEAN QUERY:",
        clean_query
    )

    print(
        "SEARCH QUERY:",
        search_query
    )

    try:

        results = web_search(
            search_query,
            num_results=8,
        )

    except Exception as error:

        print(
            "YOGA SEARCH ERROR:",
            repr(error)
        )

        return (
            "YOGA_SEARCH_ERROR: "
            + str(error)
        )

    if not results:

        return (
            "NO_YOGA_RESULTS_FOUND"
        )

    output = [
        "WEB YOGA SEARCH RESULTS:"
    ]

    for index, result in enumerate(
        results,
        start=1,
    ):

        title = result.get(
            "title",
            "",
        )

        url = result.get(
            "url",
            "",
        )

        snippet = result.get(
            "body",
            "",
        )

        output.append(
            f"""
RESULT {index}

TITLE:
{title}

URL:
{url}

SUMMARY:
{snippet}
"""
        )

    return "\n".join(
        output
    )

# ============================================================
# BLOOD REPORT ANALYSIS
# DIGITAL PDF ONLY
# ============================================================

import os
from pathlib import Path

from dotenv import load_dotenv
from pypdf import PdfReader

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI


load_dotenv()


# ============================================================
# BLOOD REPORT MODEL
# ============================================================

REPORT_MODEL = os.getenv(
    "QWEN_MODEL",
    "qwen-qwen-plus-character",
)


report_llm = ChatOpenAI(
    model=REPORT_MODEL,
    temperature=0.0,
    api_key=os.getenv("QWEN_API_KEY"),
    base_url=os.getenv(
        "QWEN_BASE_URL",
        "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    ),
)


BLOOD_REPORT_PROMPT = """
You are MediGuide AI's Blood Report Analysis Agent.

Your job is to analyze ONLY the uploaded digital/text-based
laboratory report.

The uploaded report is the PRIMARY and AUTHORITATIVE source
for all patient-specific values.

============================================================
STRICT REPORT ACCURACY
============================================================

1. Read the COMPLETE uploaded report before answering.

2. Use ONLY values actually present in the uploaded report.

3. NEVER invent:
   - test names
   - values
   - units
   - reference ranges
   - patient details
   - laboratory interpretations

4. Preserve every reported value exactly.

5. Preserve the laboratory's own reference range whenever
   it is present.

6. Determine Normal / High / Low ONLY by comparing the value
   with the reference range printed in that report.

7. If the report itself marks a value as Borderline,
   preserve that wording.

8. If the laboratory has its own interpretation, report it
   accurately.

9. Do NOT convert "possible", "suggestive", "may indicate",
   or "further confirmation required" into a confirmed
   diagnosis.

10. Do NOT diagnose from a laboratory value alone.

11. Do NOT prescribe medication or dosage.

12. Do NOT recommend supplements solely because a laboratory
    value is low or high.

============================================================
STANDARD BLOOD REPORT FORMAT
============================================================

The following structure MUST be used for every blood or
laboratory report.

The structure must remain the same across different PDFs.

Only the actual report-specific content should change.

============================================================
🩺 Blood Report Summary
============================================================

Start with:

# 🩺 Blood Report Summary

Then provide:

**Investigation:** [Actual investigation/report name]

**Patient:** [Age and gender only if available]

Do NOT invent patient information.

============================================================
Overall Assessment
============================================================

Provide a concise summary of the complete report.

Mention the main abnormal, borderline, or notable findings.

Also mention important normal findings when useful.

Do not make a diagnosis based only on laboratory results.

============================================================
Key Abnormal Findings
============================================================

Include ONLY abnormal, borderline, or clinically notable
results that are actually present in the uploaded report.

If there are abnormal findings, use this exact table format:

| Parameter | Result | Reference Range | Interpretation |
|-----------|--------|-----------------|----------------|

Example format only:

| Hemoglobin | 12.5 g/dL | 13.0–17.0 g/dL | Mildly low |

The example is NOT patient data.

Never copy example values unless they actually appear
in the uploaded report.

If there are no abnormal or notable findings, write:

No significant abnormalities are reported.

============================================================
Other Findings
============================================================

Mention important normal findings that are actually present
in the report.

Examples of formatting:

- RBC: [actual value] — Normal
- WBC: [actual value] — Normal
- Platelets: [actual value] — Normal

Only include tests that actually appear in the report.

Do not invent tests.

============================================================
Clinical Impression
============================================================

Provide a concise, patient-friendly interpretation of the
overall findings.

Explain what the important abnormalities may mean without
turning them into a confirmed diagnosis.

Use careful wording such as:

- may be associated with
- can be seen with
- should be interpreted in clinical context
- warrants clinical correlation

If the laboratory itself provides an interpretation,
preserve it accurately.

IMPORTANT:

Do not infer a diagnosis from an abnormal laboratory value.

For example, if Hemoglobin is below the reference range,
say:

"The hemoglobin level is below the laboratory reference
range."

Do NOT automatically say:

"This indicates anemia."

unless the uploaded report itself explicitly describes it
as anemia.

Similarly, do not infer dehydration, nutritional deficiency,
iron deficiency, vitamin deficiency, infection, or any other
cause unless the uploaded report explicitly supports it.

============================================================
Recommended Follow-up
============================================================

Provide safe and practical next steps based on the report.

Examples:

- Discuss notable findings with the treating physician.
- Correlate the results with symptoms and clinical history.
- Repeat the test if recommended by the physician.
- Seek medical review for significantly abnormal findings.

Do NOT prescribe medicines.

Do NOT provide medicine dosage.

Do NOT tell the patient to start, stop, or change medication.

Do NOT recommend supplements solely from laboratory values.

Only recommend follow-up actions that are directly supported
by the uploaded report.

Prefer:

"Discuss this finding with your treating physician."

Do not automatically recommend specific additional tests,
supplements, medicines, hydration, or treatment unless the
uploaded report itself recommends them.

============================================================
Bottom Line
============================================================

Provide a short 1–2 sentence summary of the most important
findings.

============================================================
DISCLAIMER
============================================================

End with:

*This is an AI-generated interpretation of the uploaded
laboratory report and is not a medical diagnosis. Please
discuss significant or persistent abnormalities with a
qualified healthcare professional.*

============================================================
FORMATTING RULES
============================================================

1. Follow the exact same structure for EVERY blood/laboratory
   PDF.

2. Only the report-specific values, test names, reference
   ranges, patient information, and findings should change.

3. Use these exact section headings:

# 🩺 Blood Report Summary

## Overall Assessment

## Key Abnormal Findings

## Other Findings

## Clinical Impression

## Recommended Follow-up

## Bottom Line

4. Use **bold** only for important parameter names and values.

5. Use a Markdown table for Key Abnormal Findings.

6. Use bullet points for Other Findings.

7. Do NOT use numbered sections except where useful inside
   Recommended Follow-up.

8. Do NOT use decorative separators such as:
   ---
   ===
   *** 

9. Do NOT use raw Markdown formatting characters in the
   patient-facing response other than the required Markdown
   headings, bold text, tables, and bullets.

10. Do NOT add sections such as:
    - For now
    - Medicine
    - See a doctor if
    - Home Remedies
    - Yoga

11. These sections belong to other MediGuide response types
    and MUST NOT be used in blood report summaries.

12. Do NOT invent medical conditions or diagnoses.

13. Do NOT call a laboratory abnormality a confirmed disease
    unless the uploaded report itself explicitly states that
    diagnosis.

14. Do NOT add possible causes unless they are explicitly
    supported by the uploaded report.

15. Do NOT add tests, supplements, medicines, or treatment
    recommendations that are not supported by the report.

16. If a value is abnormal, describe it according to the
    laboratory reference range.

17. If the report does not provide enough information to
    determine a cause, say that clinical correlation may be
    needed instead of guessing the cause.

18. Keep the language professional, clear, concise, and
    patient-friendly.

19. The final answer must contain ONLY the patient-facing
    blood report summary.

============================================================
FINAL RULE
============================================================

The uploaded laboratory report is the source of truth.

The structure is fixed.

The values, test names, reference ranges, patient details,
abnormalities, and interpretation are dynamic and must come
only from the uploaded report.
"""

# ============================================================
# BLOOD REPORT DOCUMENT CLASSIFICATION
# ============================================================

BLOOD_REPORT_CLASSIFICATION_PROMPT = """
You are MediGuide AI's Blood Report Document Classification Agent.

Your ONLY task is to determine whether the uploaded PDF text
is actually a medical laboratory / blood test report.

The application supports digital/text PDFs only.
The PDF text has already been extracted using pypdf.

============================================================
IMPORTANT
============================================================

Do NOT classify a document as a blood report merely because
it contains words such as:

blood
medical
laboratory
patient
specimen
hemoglobin
CBC
doctor

Those words alone are NOT sufficient.

You must understand the actual DOCUMENT CONTENT and STRUCTURE.

============================================================
CLASSIFY AS BLOOD_REPORT ONLY IF:
============================================================

The document actually contains laboratory test results.

For example, it may contain:

- test names
- measured patient values
- units
- laboratory reference ranges
- normal/high/low flags
- laboratory interpretations

The document does NOT need to contain every one of these,
but it must clearly represent actual laboratory test results.

CBC, blood chemistry, lipid profile, thyroid blood tests,
iron studies, vitamin blood tests and similar laboratory
reports can be classified as BLOOD_REPORT.

============================================================
CLASSIFY AS NOT_BLOOD_REPORT:
============================================================

Examples include:

- Resume / CV
- Invoice
- Certificate
- Research paper
- Medical article
- Prescription without laboratory results
- Discharge summary without laboratory report data
- Doctor notes
- General medical information
- Hospital information
- Unrelated PDF
- Any document that does not actually contain laboratory
  test results

============================================================
IMPORTANT
============================================================

Use ONLY the uploaded document text.

Do NOT use outside knowledge.

Do NOT perform blood report analysis.

Do NOT diagnose anything.

Return ONLY one of these exact values:

BLOOD_REPORT

or

NOT_BLOOD_REPORT
"""


def classify_blood_report_document(
    report_text: str,
) -> str:

    if not report_text:

        return "NOT_BLOOD_REPORT"

    prompt = f"""
{BLOOD_REPORT_CLASSIFICATION_PROMPT}

============================================================
UPLOADED DOCUMENT TEXT
============================================================

{report_text}

============================================================
END DOCUMENT
============================================================

Return ONLY:

BLOOD_REPORT

or

NOT_BLOOD_REPORT
"""

    try:

        response = report_llm.invoke(
            [
                HumanMessage(
                    content=prompt
                )
            ]
        )

        classification = str(
            response.content
        ).strip().upper()

        # Remove accidental markdown/code formatting
        classification = re.sub(
            r"[^A-Z_]",
            "",
            classification,
        )

        if classification == "BLOOD_REPORT":

            return "BLOOD_REPORT"

        return "NOT_BLOOD_REPORT"

    except Exception as error:

        print(
            "BLOOD REPORT CLASSIFICATION ERROR:",
            repr(error)
        )

        # Fail closed:
        # If classifier cannot decide, do NOT analyze
        # the document as a blood report.
        return "NOT_BLOOD_REPORT"


# ============================================================
# DIGITAL PDF TEXT EXTRACTION
# ============================================================

def extract_digital_pdf_text(
    file_path: str,
) -> str:
    """
    Extract text from a genuine digital/text PDF.

    Scanned/image-only PDFs are rejected.

    No OCR is used.
    """

    try:

        reader = PdfReader(
            file_path
        )

    except Exception as error:

        raise ValueError(
            "Unable to read the uploaded PDF: "
            + str(error)
        )

    if not reader.pages:

        raise ValueError(
            "The uploaded PDF contains no pages."
        )

    extracted_pages = []

    total_characters = 0

    for page_number, page in enumerate(
        reader.pages,
        start=1,
    ):

        try:

            text = page.extract_text()

        except Exception:

            text = ""

        if text:

            text = text.strip()

        # ----------------------------------------------------
        # SAVE ONLY PAGES WITH DIGITAL TEXT
        # ----------------------------------------------------

        if text:

            extracted_pages.append(
                f"""
PAGE {page_number}

{text}
"""
            )

            total_characters += len(
                text
            )

    # ========================================================
    # SCANNED / IMAGE PDF CHECK
    # ========================================================

    if not extracted_pages:

        raise ValueError(
            "This PDF appears to be scanned or image-based. "
            "Only digital/text-based PDFs are supported."
        )

    # ========================================================
    # VERY LOW TEXT CHECK
    # ========================================================

    if total_characters < 50:

        raise ValueError(
            "This PDF does not contain enough extractable "
            "digital text. Scanned or image-based PDFs "
            "are not supported."
        )

    print(
        f"DIGITAL PDF TEXT EXTRACTED: "
        f"{total_characters} characters"
    )

    return "\n".join(
        extracted_pages
    )


# ============================================================
# BLOOD REPORT WEB CONTEXT
# ============================================================

def get_blood_report_web_context():

    """
    Uses the SAME existing web_search() used by the
    medical/home-remedy/yoga features.

    Therefore:

        DDGS
          ↓
        Google fallback

    No separate search implementation is created.
    """

    query = (
        "CBC blood test interpretation "
        "hemoglobin hematocrit PCV platelet "
        "MCV MCH MCHC RDW reference ranges "
        "medical explanation"
    )

    print(
        "\n"
        + "=" * 70
    )

    print(
        "BLOOD REPORT WEB CONTEXT"
    )

    print(
        "Using existing DDGS → Google fallback"
    )

    try:

        results = web_search(
            query,
            num_results=8,
        )

    except Exception as error:

        print(
            "BLOOD REPORT WEB SEARCH ERROR:",
            repr(error)
        )

        return ""

    if not results:

        print(
            "BLOOD REPORT WEB: NO RESULTS"
        )

        return ""

    context_parts = []

    for index, result in enumerate(
        results[:5],
        start=1,
    ):

        title = result.get(
            "title",
            "",
        )

        url = result.get(
            "url",
            "",
        )

        body = result.get(
            "body",
            "",
        )

        if not body:

            continue

        context_parts.append(
            f"""
WEB SOURCE {index}

TITLE:
{title}

URL:
{url}

GENERAL INFORMATION:
{body}
"""
        )

    context = "\n".join(
        context_parts
    )

    print(
        f"BLOOD REPORT WEB SOURCES USED: "
        f"{len(context_parts)}"
    )

    return context


# ============================================================
# BLOOD REPORT TOOL
# ============================================================

@tool
def analyze_blood_report(
    file_path: str,
) -> str:
    """
    Analyze a digital/text-based blood report PDF.

    Supported:
        Digital PDF containing selectable/extractable text.

    Not supported:
        Scanned PDF
        Image PDF
        PNG/JPG
        Screenshot
        Photograph
    """

    try:

        # ====================================================
        # FILE CHECK
        # ====================================================

        if not file_path:

            return (
                "REPORT_ANALYSIS_ERROR: "
                "No blood report was provided."
            )

        if not os.path.exists(
            file_path
        ):

            return (
                "REPORT_ANALYSIS_ERROR: "
                "The uploaded blood report could not be found."
            )

        extension = Path(
            file_path
        ).suffix.lower()

        if extension != ".pdf":

            return (
                "REPORT_ANALYSIS_ERROR: "
                "Only digital PDF blood reports are supported."
            )

        print(
            "\n"
            + "=" * 70
        )

        print(
            "BLOOD REPORT ANALYSIS"
        )

        print(
            f"FILE: {Path(file_path).name}"
        )

        print(
            "FORMAT: DIGITAL/TEXT PDF ONLY"
        )

        # ====================================================
        # EXTRACT REPORT
        # ====================================================

        print(
            "\nExtracting digital PDF text..."
        )

        report_text = extract_digital_pdf_text(
            file_path
        )

        # ====================================================
        # CLASSIFY DOCUMENT USING BLOOD REPORT AGENT / LLM
        # ====================================================

        print(
            "\nClassifying uploaded document..."
        )

        document_type = classify_blood_report_document(
            report_text
        )

        print(
            "DOCUMENT CLASSIFICATION:",
            document_type
        )

        if document_type != "BLOOD_REPORT":

            return (
        "REPORT_ANALYSIS_ERROR: "
        "I am sorry, but the uploaded document is not a "
        "digital or text-based laboratory blood report.\n\n"
        "Because the uploaded document does not contain "
        "actual blood/laboratory test results, I cannot "
        "perform a Blood Report Summary.\n\n"
        "Please upload the correct digital laboratory "
        "blood report."
    )




        # ====================================================
        # LIMIT VERY LARGE REPORTS
        # ====================================================

        maximum_characters = 100000

        if len(report_text) > maximum_characters:

            report_text = report_text[
                :maximum_characters
            ]

            report_text += (
                "\n\n"
                "[Report text truncated because "
                "the document is unusually large.]"
            )

        # ====================================================
        # WEB CONTEXT
        # ====================================================

        web_context = (
            get_blood_report_web_context()
        )

        if not web_context:

            web_context = (
                "No supplementary web information "
                "was available."
            )

        # ====================================================
        # FINAL PROMPT
        # ====================================================

        prompt = f"""
{BLOOD_REPORT_PROMPT}

============================================================
UPLOADED REPORT
============================================================

{report_text}

============================================================
END UPLOADED REPORT
============================================================


============================================================
SUPPLEMENTARY WEB INFORMATION
============================================================

{web_context}

============================================================
END WEB INFORMATION
============================================================

Now analyze the uploaded report.

REMEMBER:

The uploaded report is the source of truth.

Do not replace any report value with web information.

Do not diagnose beyond what the report supports.

Do not prescribe medication.

Return ONLY the patient-facing blood report summary.
"""

        # ====================================================
        # LLM
        # ====================================================

        print(
            "\nGenerating report-grounded summary..."
        )

        response = report_llm.invoke(
            [
                HumanMessage(
                    content=prompt
                )
            ]
        )

        answer = str(
            response.content
        ).strip()

        if not answer:

            return (
                "REPORT_ANALYSIS_ERROR: "
                "The blood report could not be analyzed."
            )

        print(
            "\nBLOOD REPORT ANALYSIS COMPLETED"
        )

        print(
            "=" * 70
        )

        return answer

    except ValueError as error:

        print(
            "BLOOD REPORT VALIDATION ERROR:",
            str(error)
        )

        return (
            "REPORT_ANALYSIS_ERROR: "
            + str(error)
        )

    except Exception as error:

        print(
            "BLOOD REPORT ERROR:",
            repr(error)
        )

        return (
            "REPORT_ANALYSIS_ERROR: "
            "Unable to analyze the blood report."
        )