# 契約チェッカー

在日外国人向けの日本語契約リスク分析サービスです。ユーザーはテキスト、画像、PDF の契約書をアップロードし、従量課金で SSE ストリーミング分析を見ながら、24 時間以内にレポートを取得できます。

[English](./README.md) | [中文文档](./README_CN.md)

## 現在の状況

2026-03-24 時点で、ローカル Docker 上の MVP フローは動作確認済みです。

- `upload -> payment/create -> review/stream -> report -> 契約本文削除`
- `pgvector` RAG は PostgreSQL 上で稼働
- フロントエンドの 9 言語 UI は実装済み
- `APP_ENV=development` かつ `KOMOJU_SECRET_KEY` 未設定の場合のみ、ローカル開発では自動的に支払い済み扱いになります

リポジトリ外で未完了の項目:

- Fly.io / Vercel / Supabase の本番デプロイ
- KOMOJU、Resend、Sentry、PostHog の本番用認証情報
- モバイル撮影と実機での手動テスト

## アーキテクチャ

```text
React/Vite フロントエンド
  -> FastAPI バックエンド
  -> LangGraph パイプライン:
     parse_contract
     -> analyze_risks
     -> generate_report

RAG:
  PostgreSQL pgvector + OpenAI embeddings

永続化:
  PostgreSQL: orders / reports / referrals
  Redis: 24時間レポートキャッシュ

外部連携:
  GPT-4o / GPT-4o-mini
  KOMOJU
  Resend
  PostHog
  Sentry
```

## 技術スタック

- バックエンド: FastAPI, SQLAlchemy async, Alembic, Redis, APScheduler
- Agent: LangGraph, LangChain Tool Calling
- RAG: PostgreSQL `pgvector`, `text-embedding-3-small`
- フロントエンド: React, Vite, TypeScript, React Router, i18next
- インフラ: Docker Compose, Fly.io 設定, Vercel 設定

## クイックスタート

前提:

- Docker Desktop / Docker Engine
- OpenAI API Key

起動:

```bash
cp .env.example .env
# .env に OPENAI_API_KEY を設定
# ローカル Docker 実行では APP_ENV=development のままにする

docker compose up --build
```

エンドポイント:

- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8000`
- Health: `http://localhost:8000/api/health`

ローカル回帰スクリプト:

```bash
docker compose up -d backend postgres redis
./scripts/smoke_local_flow.sh
```

## ローカル確認フロー

1. フロントエンドでテキスト、画像、または PDF 契約書をアップロードします。
2. token 見積もり、価格、PII 警告を確認します。
3. 支払い注文を作成します。
4. ローカル開発では `APP_ENV=development` かつ `KOMOJU_SECRET_KEY` が空なら自動的に支払い済みになります。
5. `/review/:orderId` で SSE ストリーミング分析を確認します。
6. `/report/:orderId` で保存済みレポートを取得します。

## 実装上の重要点

- ユーザー契約本文はベクトル DB に保存しません。
- 分析完了後、`orders.contract_text` は `NULL` に更新されます。
- レポートは Redis に 24 時間キャッシュされ、PostgreSQL に期限付きで保存されます。
- ローカル Docker 開発を即時実行できるよう、バックエンド起動時に関係テーブルを自動作成します。本番では Alembic migration を明示的に実行してください。
- 本番環境で KOMOJU / Resend の必須設定が不足している場合、または `FRONTEND_URL` が `localhost` のままの場合は起動時に失敗します。
- `analyze_clause_risk` ツールが内部で直接 RAG 検索を行うため、独立した retrieval node はありません。
- `scripts/smoke_local_flow.sh` は `health -> upload -> payment -> review -> report -> contract deletion` を検証する標準ローカル回帰入口です。

## 主要ファイル

- [`backend/main.py`](./backend/main.py): 起動処理、ルーター登録、Sentry/PostHog、クリーンアップ
- [`backend/routers/review.py`](./backend/routers/review.py): SSE 審査、レポート保存、プライバシー削除
- [`backend/rag/store.py`](./backend/rag/store.py): pgvector 保存と検索
- [`scripts/smoke_local_flow.sh`](./scripts/smoke_local_flow.sh): ローカル end-to-end smoke/regression スクリプト
- [`frontend/src/main.tsx`](./frontend/src/main.tsx): ルーター、i18n、分析初期化
- [`SPEC.md`](./SPEC.md): 詳細な進捗、未完了項目、リスク
- [`DESIGN.md`](./DESIGN.md): プロダクト設計とビジネス方針
