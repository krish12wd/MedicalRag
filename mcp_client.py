import asyncio
from fastmcp import Client


async def main():
    async with Client("mcp_server.py") as client:

        await client.ping()

        print("MCP server connected!")

        tools = await client.list_tools()

        print("\nAvailable MCP tools:")
        for tool in tools:
            print(f"- {tool.name}")

        print("\n" + "=" * 80)
        print("TESTING MEDICAL GUIDELINES")
        print("=" * 80)

        result = await client.call_tool(
            "medical_guidelines",
            {
                "query": "fever treatment and management"
            },
        )

        print(result.data)

        print("\n" + "=" * 80)
        print("MCP TEST COMPLETE")
        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())