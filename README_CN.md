# 法律合同审查 AI Agent

基于 LangGraph、RAG、MCP 和 Tool Calling 构建的日文法律合同智能审查系统。

[English](./README.md) | [日本語ドキュメント](./README_JA.md)

## 运行效果

![运行截图](./docs/demo-screenshot.png)

## 系统架构

```
┌─────────────┐    ┌──────────────────────────────────────────┐
│  React UI   │───▶│  FastAPI 后端                             │
└─────────────┘    │                                          │
                   │  LangGraph Agent 工作流:                   │
┌─────────────┐    │  解析合同 → 风险分析 → 生成报告              │
│ Claude       │    │                                          │
│ Desktop     │───▶│  工具: analyze_clause_risk（内置RAG）      │
│ (MCP 客户端) │    │        generate_suggestion（内置LLM）     │
└─────────────┘    │                                          │
                   │                                          │
                   │  RAG: ChromaDB + OpenAI Embeddings       │
                   └──────────────────────────────────────────┘
```

## 技术栈

- **LLM**: OpenAI GPT-4o
- **Agent 框架**: LangGraph (StateGraph)
- **RAG**: ChromaDB + text-embedding-3-small
- **MCP**: FastMCP (Python)
- **后端**: FastAPI
- **前端**: React + Vite + TypeScript
- **部署**: Docker Compose
- **文本分块**: langchain-text-splitters for document chunking

## 快速开始

### 前置条件

- Docker & Docker Compose
- OpenAI API Key

### 启动

```bash
cd legal-contract-agent

# 从模板创建 .env 文件，填入 OpenAI API Key
cp .env.example .env
# 编辑 .env: OPENAI_API_KEY=sk-your-key-here

# 构建并启动所有服务
docker compose up --build
```

打开 http://localhost:5173 — 粘贴日文合同，点击「契約書を審査する」。

停止服务：

```bash
docker compose down        # 停止容器
docker compose down -v     # 停止并删除数据卷
```

### 不使用 Docker 运行（可选）

```bash
# 安装 Python 依赖
pip install .

# 安装前端依赖
cd frontend && npm install && cd ..

# 终端 1：启动后端
uvicorn backend.main:app --reload

# 终端 2：启动前端
cd frontend && npm run dev
```

### MCP Server（用于 Claude Desktop）

```bash
python -m backend.mcp.server
```

添加到 Claude Desktop 配置：

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

## 核心设计思路

- **为什么用 LangGraph 而不是简单的 Chain**：支持条件分支、状态管理，可扩展为多 Agent 协作
- **RAG 的价值**：让 Agent 的回答基于可靠的法律知识库，而非纯靠 LLM 记忆
- **MCP 的意义**：标准化 AI 工具协议，任意客户端（Claude Desktop 等）都能调用合同审查能力
- **Tool Calling**：Agent 自主决定何时调用什么工具，体现自主决策能力
- **TXT 分块加载**：长文本 `.txt` 文档通过 `RecursiveCharacterTextSplitter` 分块（chunk_size=200, overlap=40），与 JSON 知识库存入同一 ChromaDB，统一检索。
- **用户合同不存库**：合同文本仅作为 query，不写入向量库。

## RAG 评估模块

项目内置了一个 eval 模块，用于量化 RAG 检索管道的质量。

### 评估对象

`analyze_clause_risk` 工具依赖 ChromaDB 搜索，为每条合同条款检索相关法律知识。eval 模块衡量这一检索步骤的准确性。

### 评估指标

| 指标 | 说明 |
|------|------|
| **Recall@K** | Top-K 结果中命中相关文档的比例 |
| **MRR** | 平均倒数排名 —— 第一条相关结果排名倒数的均值 |

### 测试集

`backend/data/eval_dataset.json` 包含 5 条手工标注样本，覆盖典型合同风险场景：

| ID | 场景 |
|----|------|
| eval_001 | 损害赔偿无上限条款 |
| eval_002 | 竞业禁止期过长（5年） |
| eval_003 | 一方单方解除权 |
| eval_004 | 知识产权/著作权归属 |
| eval_005 | 保密协议无时间限制 |

每条样本包含查询文本，以及应当被检索到的 `legal_knowledge.json` 文档 ID。

### 运行评估

```bash
# 先启动后端
docker compose up --build backend

# 使用默认 k=3 运行评估
curl http://localhost:8000/api/eval/rag

# 自定义 k 值
curl "http://localhost:8000/api/eval/rag?k=5"
```

### 返回示例

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

