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

Docker メモ:

- 起動中サービスの中でコマンドを実行する場合は、`docker compose run` ではなく `docker compose exec` を優先してください。
- `docker compose run` は一時的な `*-run-*` コンテナを残し、`docker compose down` 時に network 解放を妨げることがあります。

エンドポイント:

- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8000`
- Health: `http://localhost:8000/api/health`

ローカル回帰スクリプト:

```bash
docker compose up -d backend postgres redis
./scripts/smoke_local_flow.sh
./scripts/check_locale_keys.sh
./scripts/check_rag_eval.sh
./scripts/run_backend_pytests.sh
```

## ローカル確認フロー

1. フロントエンドでテキスト、画像、または PDF 契約書をアップロードします。
2. token 見積もり、価格、PII 警告を確認します。
3. 支払い注文を作成します。
4. ローカル開発では `APP_ENV=development` かつ `KOMOJU_SECRET_KEY` が空なら自動的に支払い済みになります。
5. `/review/:orderId` で SSE ストリーミング分析を確認します。
6. `/report/:orderId` で保存済みレポートを取得します。
7. ストリーミング審査中は内部ツール名ではなく、ユーザー向けの進捗文言を表示します。
8. レポート本文の言語は支払い時に選択した言語で固定され、後からサイト言語を切り替えても本文自体は再翻訳されません。
9. 契約書をアップロードした同じ端末・同じセッションでは、レビュー画面とレポート画面に原文契約のセッション限定コピーを表示し、比較しやすくしています。共有リンクやメールリンクには原文は含まれません。

## 実装上の重要点

- ユーザー契約本文はベクトル DB に保存しません。
- 分析完了後、`orders.contract_text` は `NULL` に更新されます。
- レポートは Redis に 24 時間キャッシュされ、PostgreSQL に期限付きで保存されます。
- ローカル Docker 開発を即時実行できるよう、バックエンド起動時に関係テーブルを自動作成します。本番では Alembic migration を明示的に実行してください。
- 本番環境で KOMOJU / Resend の必須設定が不足している場合、または `FRONTEND_URL` が `localhost` のままの場合は起動時に失敗します。
- 支払い、審査、メール、レポート取得の主要経路では、構造化アプリケーションログと PostHog イベントを出力し、外部連携時の切り分けをしやすくしています。
- `/api/report/{order_id}` は Redis キャッシュ命中時と PostgreSQL fallback 時で同じ payload 形を返すように統一されています。
- `analyze_clause_risk` ツールが内部で直接 RAG 検索を行うため、独立した retrieval node はありません。
- `scripts/smoke_local_flow.sh` は `health -> upload -> payment -> review -> report -> contract deletion` を検証する標準ローカル回帰入口です。
- `scripts/smoke_local_flow.sh` は SSE 終了時に発生しうる `curl` 終了コード `18` を許容し、実際のストリーム内容で成功可否を判定します。
- `scripts/check_locale_keys.sh` は 9 言語の locale ファイルが `ja.json` と同じキー集合を保っているかを確認します。
- `scripts/check_rag_eval.sh` は `/api/eval/rag` を現在のローカル基準値（`Recall@3 >= 0.5`、`MRR >= 0.6`）でチェックします。
- `scripts/run_backend_pytests.sh` は Docker 内で backend の dev 依存を入れて回帰テストを実行します。

## 主要ファイル

- [`backend/main.py`](./backend/main.py): 起動処理、ルーター登録、Sentry/PostHog、クリーンアップ
- [`backend/routers/review.py`](./backend/routers/review.py): SSE 審査、レポート保存、プライバシー削除
- [`backend/rag/store.py`](./backend/rag/store.py): pgvector 保存と検索
- [`backend/eval/evaluator.py`](./backend/eval/evaluator.py): RAG 評価指標とデータセット実行
- [`scripts/smoke_local_flow.sh`](./scripts/smoke_local_flow.sh): ローカル end-to-end smoke/regression スクリプト
- [`scripts/check_locale_keys.sh`](./scripts/check_locale_keys.sh): locale キー整合性チェック
- [`scripts/check_rag_eval.sh`](./scripts/check_rag_eval.sh): ローカル RAG 回帰チェック
- [`scripts/run_backend_pytests.sh`](./scripts/run_backend_pytests.sh): Docker ベースの backend pytest 実行スクリプト
- [`frontend/src/main.tsx`](./frontend/src/main.tsx): ルーター、i18n、分析初期化
- [`SPEC.md`](./SPEC.md): 詳細な進捗、未完了項目、リスク
- [`DESIGN.md`](./DESIGN.md): プロダクト設計とビジネス方針
