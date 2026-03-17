# Legal Contract Review Agent

AI-powered Japanese legal contract review agent system built with LangGraph, RAG, MCP, and Tool Calling.

[中文文档](./README_CN.md) | [日本語ドキュメント](./README_JA.md)

## Demo

![Demo Screenshot](./docs/demo-screenshot.png)

## Architecture

```
┌─────────────┐    ┌──────────────────────────────────────────┐
│  React UI   │───▶│  FastAPI Backend                         │
└─────────────┘    │                                          │
                   │  LangGraph Agent Workflow:                │
┌─────────────┐    │  parse_contract → analyze_risks          │
│ Claude       │    │  → generate_report                       │
│ Desktop     │───▶│                                          │
│ (MCP Client)│    │  Tools: analyze_clause_risk (RAG inside) │
└─────────────┘    │         generate_suggestion (LLM inside) │
                   │                                          │
                   │  RAG: ChromaDB + OpenAI Embeddings       │
                   └──────────────────────────────────────────┘
```

## Tech Stack

- **LLM**: OpenAI GPT-4o
- **Agent Framework**: LangGraph (StateGraph)
- **RAG**: ChromaDB + text-embedding-3-small
- **MCP**: FastMCP (Python)
- **Backend**: FastAPI
- **Frontend**: React + Vite + TypeScript
- **Deployment**: Docker Compose
- **Text Splitting**: langchain-text-splitters for document chunking

## Quick Start

### Prerequisites

- Docker & Docker Compose
- OpenAI API Key

### Setup & Run

```bash
cd legal-contract-agent

# Create .env from template and add your OpenAI API Key
cp .env.example .env
# Edit .env: OPENAI_API_KEY=sk-your-key-here

# Build and start all services
docker compose up --build
```

Open http://localhost:5173 — paste a Japanese contract and click "契約書を審査する".

To stop:

```bash
docker compose down        # Stop containers
docker compose down -v     # Stop and remove data volumes
```

### Run Without Docker (Alternative)

```bash
# Install Python dependencies
pip install .

# Install frontend dependencies
cd frontend && npm install && cd ..

# Terminal 1: Start backend
uvicorn backend.main:app --reload

# Terminal 2: Start frontend
cd frontend && npm run dev
```

### MCP Server (for Claude Desktop)

```bash
python -m backend.mcp.server
```

Add to Claude Desktop config:

```json
{
  "mcpServers": {
    "legal-review": {
      "command": "python",
      "args": ["-m", "backend.mcp.server"],
      "cwd": "/path/to/legal-contract-agent"
    }
  }
}
```

## Key Design Decisions

- **LangGraph over simple chain**: Supports conditional branching, state management, and is extensible for multi-agent collaboration
- **RAG**: Grounds agent responses in reliable legal knowledge rather than relying solely on LLM memory
- **MCP**: Standardized AI tool protocol enabling any client (Claude Desktop, etc.) to invoke contract review capabilities
- **Tool Calling**: Agent autonomously decides when to invoke which tool, demonstrating autonomous decision-making
- **TXT Chunking**: Long `.txt` documents are split by `RecursiveCharacterTextSplitter` (chunk_size=200, overlap=40) and stored alongside JSON knowledge. Both are retrieved uniformly by `store.search()`.
- **Contracts are query-only**: User contract text is never stored in the vector database — only the curated knowledge base is indexed.

## RAG Evaluation

The project includes a built-in eval module to measure the retrieval quality of the RAG pipeline.

### What it evaluates

The `analyze_clause_risk` tool relies on `ChromaDB` search to retrieve relevant legal knowledge for each contract clause. The eval module measures how well this retrieval performs.

### Metrics

| Metric | Description |
|--------|-------------|
| **Recall@K** | Fraction of relevant documents found in the top-K results |
| **MRR** | Mean Reciprocal Rank — average of 1/rank of the first relevant result |

### Dataset

5 hand-labeled evaluation samples in `backend/data/eval_dataset.json`, covering typical contract risk scenarios:

| ID | Scenario |
|----|----------|
| eval_001 | Unlimited liability clause |
| eval_002 | Excessive non-compete period (5 years) |
| eval_003 | Unilateral termination right |
| eval_004 | IP / copyright assignment |
| eval_005 | NDA with no time limit |

Each sample contains the query text and the expected relevant document IDs from `legal_knowledge.json`.

### Run the eval

```bash
# Start backend first
docker compose up --build backend

# Run evaluation with default k=3
curl http://localhost:8000/api/eval/rag

# Run with custom k
curl "http://localhost:8000/api/eval/rag?k=5"
```

### Example response

```json
{
  "k": 3,
  "num_samples": 5,
  "mean_recall_at_k": 0.72,
  "mrr": 0.85,
  "per_sample": [
    {
      "id": "eval_001",
      "description": "損害賠償無制限条項",
      "recall_at_k": 0.667,
      "reciprocal_rank": 1.0,
      "retrieved_ids": ["civil_code_415", "risk_liability_unlimited", "civil_code_416"],
      "relevant_ids": ["civil_code_415", "civil_code_416", "risk_liability_unlimited"]
    }
  ]
}
```

