import asyncio
import json

from fastmcp import FastMCP

from backend.agent.graph import run_review
from backend.rag.store import get_store
from backend.rag.loader import load_legal_knowledge

mcp = FastMCP("Legal Contract Review Agent")


@mcp.tool()
async def review_contract(contract_text: str) -> str:
    """Review a Japanese legal contract and return a structured risk analysis report.

    Args:
        contract_text: The full text of the contract to review (in Japanese).
    """
    report = await run_review(contract_text)
    return json.dumps(report, ensure_ascii=False, indent=2)


@mcp.tool()
async def search_legal_reference(query: str) -> str:
    """Search for relevant Japanese legal knowledge and precedents.

    Args:
        query: The search query about a legal topic or contract clause.
    """
    store = get_store()
    results = store.search(query, n_results=5)
    output = []
    for r in results:
        output.append({
            "title": r["metadata"]["title"],
            "category": r["metadata"]["category"],
            "content": r["content"],
        })
    return json.dumps(output, ensure_ascii=False, indent=2)


def main():
    """Start the MCP server."""
    load_legal_knowledge()
    mcp.run()


if __name__ == "__main__":
    main()
