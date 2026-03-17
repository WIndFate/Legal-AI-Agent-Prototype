# 法律契約審査 AI エージェント

LangGraph、RAG、MCP、Tool Calling を活用した日本語法律契約書の AI 審査システム。

[English](./README.md) | [中文文档](./README_CN.md)

## デモ

![デモスクリーンショット](./docs/demo-screenshot.png)

## アーキテクチャ

```
┌─────────────┐    ┌──────────────────────────────────────────┐
│  React UI   │───▶│  FastAPI バックエンド                      │
└─────────────┘    │                                          │
                   │  LangGraph Agent ワークフロー:              │
┌─────────────┐    │  契約解析 → リスク分析 → レポート生成          │
│ Claude       │    │                                          │
│ Desktop     │───▶│  ツール: analyze_clause_risk（RAG内蔵）   │
│ (MCPクライアント)│   │        generate_suggestion（LLM内蔵）   │
└─────────────┘    │                                          │
                   │                                          │
                   │  RAG: ChromaDB + OpenAI Embeddings       │
                   └──────────────────────────────────────────┘
```

## 技術スタック

- **LLM**: OpenAI GPT-4o
- **エージェントフレームワーク**: LangGraph (StateGraph)
- **RAG**: ChromaDB + text-embedding-3-small
- **MCP**: FastMCP (Python)
- **バックエンド**: FastAPI
- **フロントエンド**: React + Vite + TypeScript
- **デプロイ**: Docker Compose

## クイックスタート

### 前提条件

- Docker & Docker Compose
- OpenAI API Key

### 起動方法

```bash
cd legal-contract-agent

# テンプレートから .env ファイルを作成し、OpenAI API Key を設定
cp .env.example .env
# .env を編集: OPENAI_API_KEY=sk-your-key-here

# 全サービスをビルド・起動
docker compose up --build
```

http://localhost:5173 を開き、日本語の契約書を貼り付けて「契約書を審査する」をクリック。

停止方法：

```bash
docker compose down        # コンテナを停止
docker compose down -v     # コンテナ停止 + データボリューム削除
```

### Docker を使わない場合（代替方法）

```bash
# Python 依存関係のインストール
pip install .

# フロントエンド依存関係のインストール
cd frontend && npm install && cd ..

# ターミナル 1：バックエンド起動
uvicorn backend.main:app --reload

# ターミナル 2：フロントエンド起動
cd frontend && npm run dev
```

### MCP Server（Claude Desktop 連携）

```bash
python -m backend.mcp.server
```

Claude Desktop の設定に追加：

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

## プロジェクト構成

```
backend/
├── main.py              # FastAPI エントリーポイント
├── Dockerfile           # バックエンドコンテナイメージ
├── agent/
│   ├── graph.py         # LangGraph ワークフロー定義
│   ├── nodes.py         # エージェントノードロジック
│   ├── state.py         # エージェント状態定義
│   └── tools.py         # LangChain ツール
├── rag/
│   ├── store.py         # ChromaDB ベクトルストア
│   └── loader.py        # ナレッジローダー
├── mcp/
│   └── server.py        # MCP サーバー
└── data/
    └── legal_knowledge.json  # 法律ナレッジベース（20件）

frontend/
├── Dockerfile           # フロントエンドコンテナイメージ
└── src/
    ├── App.tsx           # メイン UI
    └── App.css           # スタイル

docker-compose.yml       # コンテナオーケストレーション
```

## 設計上の主要判断

- **シンプルな Chain ではなく LangGraph を採用した理由**：条件分岐、状態管理をサポートし、マルチエージェント協調への拡張が可能
- **RAG の価値**：エージェントの回答を信頼できる法律知識に基づかせ、LLM の記憶のみに依存しない
- **MCP の意義**：標準化された AI ツールプロトコルにより、任意のクライアント（Claude Desktop 等）から契約審査機能を呼び出し可能
- **Tool Calling**：エージェントがどのツールをいつ呼び出すかを自律的に判断し、自律的意思決定能力を実現

## RAG 評価モジュール

RAG 検索パイプラインの品質を定量化するための eval モジュールを内蔵しています。

### 評価対象

`analyze_clause_risk` ツールは ChromaDB 検索を通じて、各契約条項に関連する法律知識を取得します。eval モジュールはこの検索ステップの精度を計測します。

### 評価指標

| 指標 | 説明 |
|------|------|
| **Recall@K** | 上位 K 件の結果に関連文書が含まれる割合 |
| **MRR** | 平均相互順位 —— 最初の関連結果の順位の逆数の平均 |

### テストデータセット

`backend/data/eval_dataset.json` に手動でラベル付けした 5 件のサンプルを用意。典型的な契約リスクシナリオを網羅：

| ID | シナリオ |
|----|----------|
| eval_001 | 損害賠償上限なし条項 |
| eval_002 | 競業避止期間過長（5年） |
| eval_003 | 一方的解除権 |
| eval_004 | 知的財産権・著作権帰属 |
| eval_005 | 秘密保持期間の定めなし |

各サンプルにはクエリテキストと、`legal_knowledge.json` から取得されるべき関連文書 ID が含まれます。

### 評価の実行方法

```bash
# まずバックエンドを起動
docker compose up --build backend

# デフォルト k=3 で評価実行
curl http://localhost:8000/api/eval/rag

# k を指定して実行
curl "http://localhost:8000/api/eval/rag?k=5"
```

### レスポンス例

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

### ファイル構成

```
backend/
  eval/
    __init__.py          # パッケージ初期化
    evaluator.py         # Recall@K・MRR 計算ロジック
  data/
    eval_dataset.json    # 手動ラベル付きテストセット（5件）
```
