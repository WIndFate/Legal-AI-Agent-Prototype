# ContractGuard

在日外国人向けの日本語契約リスク分析サービスです。ユーザーはテキスト、画像、PDF の契約書をアップロードし、従量課金で SSE ストリーミング分析を見ながら、24 時間以内にレポートを取得できます。

[English](./README.md) | [中文文档](./README_CN.md)

## 現在の状況

2026-03-27 時点で、ローカル Docker 上の MVP フローは動作確認済みです。

- `upload -> payment/create -> review/stream -> report -> 契約本文削除`
- テキスト入力とテキスト抽出可能な PDF は支払い前にそのまま見積もりし、画像 / スキャン PDF は一時保存 + 支払い後の正式 OCR を使う二段階 OCR フローになりました
- `pgvector` RAG は PostgreSQL 上で稼働し、10 法令カテゴリ・331 件超の法条（賃貸借・労働・パート・業務委託・売買等）を収録
- フロントエンドの 9 言語 UI は実装済み。ブランド（ContractGuard）、プライバシーポリシー/利用規約ページ、インタラクティブなサンプルレポート展示を含む
- ルート単位の遅延読み込みと分析 SDK の遅延初期化により、初期フロントエンド bundle を軽量化
- `APP_ENV=development` かつ `KOMOJU_SECRET_KEY` 未設定の場合のみ、ローカル開発では自動的に支払い済み扱いになります
- デプロイ設定済み: `fly.toml`（NRT リージョン、HTTPS 強制）+ `vercel.json`（API プロキシ + セキュリティヘッダー）
- 統合テストスイート: 7 つのルーターテストファイル、39 件超のテスト関数で全 API エンドポイントをカバー
- SSE 再接続: 指数バックオフ（最大 3 回）+ イベント重複排除 + 60 秒の無活動タイムアウト
- ホームページを独立コンポーネントに分割（Hero / Flow / Examples / Upload）
- RAG embedding バッチ化により API 呼び出し回数を削減
- 不要コードのクリーンアップ完了（未使用の `analyze_risks_streaming` を削除）
- よく使うクエリパスにデータベースインデックスを追加（email, payment_status, expires_at, analysis_status）
- CSS を部分的に CSS Modules へ移行: layout / home / examples / legal はスコープ付きモジュール + `clsx`、report / review はページ間共有のためグローバル維持

リポジトリ外で未完了の項目:

- KOMOJU、Resend、Sentry、PostHog の本番用認証情報と実結合テスト
- モバイル撮影と実機での手動テスト
- ユーザーフィードバック収集機能（P2）
- OG タグとソーシャルメディア共有最適化（P2）
- report/review ページの CSS モジュール化（ページ間共有のためグローバル維持）

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
- Agent: LangGraph, 条項単位の審査パイプライン
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
- ローカル OCR 依存は Docker build 時に `INSTALL_LOCAL_OCR=true` を明示した場合のみ入ります。デフォルトの backend イメージでは重い依存を自動では入れません。

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
2. token 見積もり、価格、PII 警告を確認します。画像 / スキャン PDF では、この価格が支払い前の「仮見積もり」であることも明示されます。
3. 支払い注文を作成します。
4. ローカル開発では `APP_ENV=development` かつ `KOMOJU_SECRET_KEY` が空なら自動的に支払い済みになります。
5. `/review/:orderId` で SSE ストリーミング分析を確認します。
6. `/report/:orderId` で保存済みレポートを取得します。
7. ストリーミング審査中は内部ツール名ではなく、ユーザー向けの進捗文言を表示します。
8. レポート本文の言語は支払い時に選択した言語で固定され、後からサイト言語を切り替えても本文自体は再翻訳されません。
9. 契約書をアップロードした同じ端末・同じセッションでは、各分析カード内で対応する元条項をその場で展開して比較できます。共有リンクやメールリンクには原文は含まれません。
10. 展開後の条項比較は読みやすさを重視しており、モバイルでは縦積み、大きな画面では元条項と分析内容を横並びで表示します。
11. ホームページには3つの契約シナリオ（賃貸・雇用・アルバイト）のインタラクティブなサンプルレポート展示があり、各条項分析は9言語すべてで表示されます。
12. プライバシーポリシー (`/privacy`) と利用規約 (`/terms`) ページはローカライズされた要約と日本語法律全文を組み合わせています。
13. レポート内の参照法令 (`referenced_law`) はユーザーの選択言語にかかわらず、常に日本語原文のまま表示されます。
14. 保存済みレポートページは、より正式な審査レポートらしい版面に寄せており、ブラウザ印刷 / PDF 保存を考慮したスタイルも入っています。
15. ホームページの「ホーム / サンプル」導線は明示的なアンカー位置へスクロールするようになり、hero の価格文言も固定の見かけ上限を表示しない形に調整されています。

## 実装上の重要点

- ユーザー契約本文はベクトル DB に保存しません。
- 分析完了後、`orders.contract_text` は `NULL` に更新されます。
- 画像 / スキャン PDF は支払い前に短期間だけ元ファイルを保持し、解析完了後または未払い期限切れ後のクリーンアップで削除されます。
- レポートは Redis に 24 時間キャッシュされ、PostgreSQL に期限付きで保存されます。
- `backend/services/costing.py` により、正式 OCR・parse・analyze・suggestion・translation の構造化コストログが出力されます。
- embedding リクエストもコストログを出力し、review 完了時には見積もりモード・入力種別・条項数を含む注文単位のコスト要約ログも出力されます。
- この注文単位のコスト要約は、ログだけでなく `reports.cost_summary` にも保存されるようになりました。
- `GET /api/eval/costs` は `reports.cost_summary` を集計し、実データが不足している間は `backend/data/cost_samples_seed.json` で 10 サンプル基準まで補完します。
- 実行時の価格表は Python の固定値ではなく `backend/data/pricing_policy.json` から読み込むようになりました。現時点の暫定価格は `¥299 / ¥499 / ¥799 / ¥1599` です。
- `/api/eval/costs` は「コスト下限の推奨価格」と「目標粗利込みの推奨価格」を両方返します。既定の `target_margin_rate` は `0.75` です。
- `PARSE_MODEL` と `SUGGESTION_MODEL` は設定可能になり、デフォルトでは `gpt-4o-mini` を使います。正式 OCR と条項ごとのリスク判定は引き続きデフォルトで `gpt-4o` のままです。
- `analyze_risks` は、膨張し続ける全契約の多段 tool-calling 会話ではなく、条項ごとの分析に変更されました。これによりコストとコンテキスト圧迫が大きく下がります。
- `analyze_clause_risk` は、長い法令断片をそのまま返す代わりに、圧縮した RAG 要約を返します。
- `generate_suggestion` はリスクレベルに応じて長さを変え、中リスクは短く、高リスクはより具体的に出力します。
- ローカル Docker 開発を即時実行できるよう、バックエンド起動時に関係テーブルを自動作成します。本番では Alembic migration を明示的に実行してください。
- 本番環境で KOMOJU / Resend の必須設定が不足している場合、または `FRONTEND_URL` が `localhost` のままの場合は起動時に失敗します。
- 支払い、審査、メール、レポート取得の主要経路では、構造化アプリケーションログと PostHog イベントを出力し、外部連携時の切り分けをしやすくしています。
- フロントエンドはルート単位で lazy load され、分析系 SDK も非同期初期化されるため、observability 依存が初期 main chunk を膨らませません。
- フロントエンドには `RevealSection`、`OrderReminderDialog`、`ShareSheet` の共通 UX コンポーネントが追加され、スクロール演出、注文番号保存の促し、専用共有パネルを実装しています。
- `/api/report/{order_id}` は Redis キャッシュ命中時と PostgreSQL fallback 時で同じ payload 形を返すように統一されています。
- `analyze_clause_risk` ツールが内部で直接 RAG 検索を行うため、独立した retrieval node はありません。
- `scripts/smoke_local_flow.sh` は `health -> upload -> payment -> review -> report -> contract deletion` を検証する標準ローカル回帰入口です。
- `scripts/smoke_local_flow.sh` は SSE 終了時に発生しうる `curl` 終了コード `18` を許容し、実際のストリーム内容で成功可否を判定します。
- 元条項テキストはストリーミング完了結果と同一端末セッション内にのみ保持されます。DB レポート、Redis キャッシュ、共有リンク、メールリンクには保存・露出しません。
- `scripts/check_locale_keys.sh` は 9 言語の locale ファイルが `ja.json` と同じキー集合を保っているかを確認します。
- バックエンドは起動時に `backend/data/egov_laws.json` の公式 e-Gov 法令コーパスを読み込みます。10 法令カテゴリ・331 件超の法条を収録。ローカル評価データセットも 20 件のラベル付きサンプルに拡張されています（損害賠償、競業禁止、解約、NDA、賃貸借等をカバー）。
- `scripts/check_rag_eval.sh` は `/api/eval/rag` を現在のローカル基準値（`Recall@5 >= 0.45`、`MRR >= 0.45`）でチェックします。
- `scripts/run_backend_pytests.sh` は Docker 内で backend の dev 依存を入れた上で、完全な `tests/` 回帰テストを実行します。
- 統合テストは全 7 API ルーター（health、upload、payment、review、report、referral、eval）を 39 件超のテスト関数でカバーしています。
- `frontend/src/pages/HomePage.tsx` は現在コンテナページとして振る舞い、hero / flow / upload-payment を個別コンポーネント（`HomeHeroSection`、`HomeFlowSection`、`HomeUploadSection`）に委譲します。事例紹介は `/examples` の独立ページに切り出されています。
- 見積もり生成後、ホームページは自動で支払いパネルまでスクロールし、短時間ハイライトして次の導線を見失いにくくしています。
- `/lookup` 結果照会ページが追加され、注文番号から支払い状態ページ・分析中ページ・完成レポートを再オープンできます。
- 支払い完了時と分析完了時には、注文番号をスクリーンショット保存またはコピーするよう促すダイアログを表示します。
- レポート共有は直接 Web Share API を呼ぶのではなく、宣伝用プレビュー、リンクコピー、注文番号コピー、端末共有への導線を持つ専用共有パネルを先に開きます。
- 結果照会ページとレポートページは、注文番号形式エラー、弱い回線、オフライン、再試行可能な失敗状態をより明確に表示します。
- SSE 再接続は指数バックオフ（ベース 1 秒、最大 3 回）+ イベント重複排除 + 60 秒の無活動タイムアウトを実装しています。
- RAG embedding リクエストは `_get_embeddings_batch_sync()` と `search_batch()` によりバッチ化され、API 呼び出し回数を削減しています。

## 主要ファイル

- [`backend/main.py`](./backend/main.py): 起動処理、ルーター登録、Sentry/PostHog、クリーンアップ
- [`backend/routers/review.py`](./backend/routers/review.py): SSE 審査、レポート保存、プライバシー削除
- [`backend/rag/store.py`](./backend/rag/store.py): pgvector 保存と検索
- [`backend/eval/evaluator.py`](./backend/eval/evaluator.py): RAG 評価指標とデータセット実行
- [`scripts/smoke_local_flow.sh`](./scripts/smoke_local_flow.sh): ローカル end-to-end smoke/regression スクリプト
- [`scripts/check_locale_keys.sh`](./scripts/check_locale_keys.sh): locale キー整合性チェック
- [`scripts/check_rag_eval.sh`](./scripts/check_rag_eval.sh): ローカル RAG 回帰チェック
- [`scripts/run_backend_pytests.sh`](./scripts/run_backend_pytests.sh): Docker ベースの backend pytest 実行スクリプト
- [`frontend/src/main.tsx`](./frontend/src/main.tsx): ルーター、i18n、遅延読み込み、分析初期化
- [`frontend/src/components/home/HomeHeroSection.tsx`](./frontend/src/components/home/HomeHeroSection.tsx): ホームページ hero セクション
- [`frontend/src/components/home/HomeFlowSection.tsx`](./frontend/src/components/home/HomeFlowSection.tsx): ホームページフローステップ
- [`frontend/src/components/home/HomeExamplesSection.tsx`](./frontend/src/components/home/HomeExamplesSection.tsx): ホームページサンプル展示
- [`frontend/src/components/home/HomeUploadSection.tsx`](./frontend/src/components/home/HomeUploadSection.tsx): ホームページアップロード
- [`frontend/src/pages/ExamplesPage.tsx`](./frontend/src/pages/ExamplesPage.tsx): 独立した事例紹介ページ
- [`frontend/src/pages/LookupPage.tsx`](./frontend/src/pages/LookupPage.tsx): 注文番号ベースの結果照会ページ
- [`frontend/src/components/common/OrderReminderDialog.tsx`](./frontend/src/components/common/OrderReminderDialog.tsx): 注文番号保存を促すダイアログ
- [`frontend/src/components/common/ShareSheet.tsx`](./frontend/src/components/common/ShareSheet.tsx): 専用共有パネル
- [`tests/`](./tests/): 全 7 API ルーターの統合テスト + ユニットテスト
- [`SPEC.md`](./SPEC.md): 詳細な進捗、未完了項目、リスク
- [`DESIGN.md`](./DESIGN.md): プロダクト設計とビジネス方針
