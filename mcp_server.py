import sys
import contextlib

from fastmcp import FastMCP

# tools.py ke startup logs ko stderr par bhejo
with contextlib.redirect_stdout(sys.stderr):
    from tools import (
        search_medical_guidelines,
        search_medical_web,
        search_home_remedies_web,
        search_yoga_web,
        analyze_blood_report,
    )

mcp = FastMCP("MediGuide Medical MCP Server")


def run_tool(tool, args):
    # Tool execution ke internal print/logs bhi stdout ko corrupt na karein
    with contextlib.redirect_stdout(sys.stderr):
        return str(tool.invoke(args))


@mcp.tool()
def medical_guidelines(query: str) -> str:
    return run_tool(search_medical_guidelines, {"query": query})


@mcp.tool()
def medical_web_search(query: str) -> str:
    return run_tool(search_medical_web, {"query": query})


@mcp.tool()
def home_remedies_search(query: str) -> str:
    return run_tool(search_home_remedies_web, {"query": query})


@mcp.tool()
def yoga_search(query: str) -> str:
    return run_tool(search_yoga_web, {"query": query})


@mcp.tool()
def blood_report_analysis(file_path: str) -> str:
    return run_tool(analyze_blood_report, {"file_path": file_path})


if __name__ == "__main__":
    mcp.run()