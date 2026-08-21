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
        "QUERY:"
    )

    print(
        query
    )

    # ========================================================
    # DDGS
    # ========================================================

    try:

        results = []

        with DDGS() as ddgs:

            search_results = ddgs.text(
                query,
                max_results=num_results,
            )

            for result in search_results:

                title = result.get(
                    "title",
                    "",
                )

                url = result.get(
                    "href",
                    "",
                )

                body = result.get(
                    "body",
                    "",
                )

                if not url:
                    continue

                if not _is_valid_url(
                    url
                ):
                    continue

                results.append(
                    {
                        "title":
                            title,

                        "url":
                            url,

                        "body":
                            body,
                    }
                )

        if results:

            print(
                f"DDGS RESULTS: {len(results)}"
            )

            return results

    except Exception as error:

        print(
            "DDGS SEARCH ERROR:",
            repr(error)
        )

    # ========================================================
    # GOOGLE FALLBACK
    # ========================================================

    try:

        results = _google_search(
            query,
            num_results,
        )

        if results:

            print(
                f"GOOGLE RESULTS: {len(results)}"
            )

            return results

    except Exception as error:

        print(
            "GOOGLE SEARCH ERROR:",
            repr(error)
        )

    # ========================================================
    # NOTHING FOUND
    # ========================================================

    print(
        "NO WEB SEARCH RESULTS"
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

    Prefer reliable medical and healthcare sources.
    """

    search_query = (
        f"{query} "
        f"medical treatment management "
        f"medicine clinical guidance"
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

        content = _fetch_webpage_text(
            url
        )

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
    information relevant to the patient's symptoms.
    """

    search_query = (
        f"{query} home remedies "
        f"self care reputable medical source"
    )

    print(
        "\nHOME REMEDY WEB SEARCH:"
    )

    print(
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

    search_query = (
        f"{query} gentle yoga poses "
        f"beginner safe"
    )

    print(
        "\nYOGA WEB SEARCH:"
    )

    print(
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