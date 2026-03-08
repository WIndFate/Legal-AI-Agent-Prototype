# CLAUDE.md — Legal AI Agent Prototype

## Project Overview

A Japanese legal contract review AI agent built with LangGraph (agentic loop), ChromaDB (RAG), FastAPI (REST + SSE), React/Vite (frontend), and FastMCP (MCP server).

The agent pipeline: `parse_contract → analyze_risks → generate_report`

- `parse_contract`: LLM splits contract text into individual clauses (JSON)
- `analyze_risks`: LLM agentic loop calls `analyze_clause_risk` (RAG inside) and `generate_suggestion` tools
- `generate_report`: Aggregates results into final structured report

---

## Running the Project

**All services run via Docker. Never try to run Python directly for verification.**

```bash
# Start all services
docker compose up --build

# Restart after code changes
docker compose up --build backend

# View backend logs
docker compose logs -f backend

# Test the API
curl -X POST http://localhost:8000/api/review/stream \
  -H "Content-Type: application/json" \
  -d '{"contract_text": "第1条（目的）..."}'
```

- Backend: `http://localhost:8000`
- Frontend: `http://localhost:5173`
- Health check: `GET http://localhost:8000/api/health`

---

## Key Files

```
backend/
  agent/
    state.py      # AgentState TypedDict
    tools.py      # LangChain tools: analyze_clause_risk (RAG inside), generate_suggestion
    nodes.py      # Node functions: parse_contract, analyze_risks, generate_report
    graph.py      # LangGraph workflow + run_review / run_review_stream
  rag/
    store.py      # ChromaDB singleton (get_store())
    loader.py     # Loads legal knowledge JSON into ChromaDB on startup
  mcp/
    server.py     # FastMCP server exposing review_contract + search_legal_reference
  main.py         # FastAPI app entry point
frontend/
  src/
    App.tsx       # Single-page UI consuming SSE stream
docker-compose.yml
pyproject.toml
```

---

## Architecture Decisions

### RAG is inside the tool, not a separate node
`analyze_clause_risk(clause_text)` calls `get_store().search()` directly inside the tool.
The LLM calls the tool per clause → receives real legal knowledge → makes risk judgment.
Do NOT add a `retrieve_knowledge` node back. Do NOT pre-inject RAG results into prompts.

### Tool calling pattern
- `ALL_TOOLS` contains exactly two tools: `analyze_clause_risk` and `generate_suggestion`.
- Use `get_store().search()` directly in tools. Do NOT add a `search_legal_knowledge` tool back — its functionality is already covered by `analyze_clause_risk` internally.
- `analyze_clause_risk` is responsible for risk judgment: queries RAG and returns relevant legal knowledge to the outer LLM.
- `generate_suggestion` is responsible for producing modification text: internally invokes a dedicated `gpt-4o` LLM and returns the concrete suggestion. The outer LLM must use the return value directly as the `suggestion` field — do NOT have the outer LLM write suggestions itself.

### State fields
`AgentState` has exactly: `contract_text`, `clauses`, `risk_analysis`, `review_report`, `messages`.
Do NOT add `rag_results` or `current_clause_index` back — they were removed as dead fields.

### Streaming
`run_review_stream` uses `astream_events(version="v2")` from LangGraph. The frontend consumes SSE events of types: `node_start`, `token`, `tool_call`, `complete`, `error`.

---

## Environment

Requires `.env` at project root:
```
OPENAI_API_KEY=sk-...
```

ChromaDB data is persisted in Docker volume `chroma_data`. RAG knowledge is loaded from `backend/data/` on startup.

---

## Development Notes

- Python 3.11+, dependencies in `pyproject.toml`
- Backend hot-reload: add `--reload` flag to uvicorn in `backend/Dockerfile` if needed
- MCP server runs as a separate process: `python -m backend.mcp.server`
- Code comments in English; user-facing messages in Japanese
