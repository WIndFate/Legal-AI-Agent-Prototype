# ContractGuard

在日外国人向けの日本語契約リスク分析サービスです。ユーザーはテキスト、画像、PDF の契約書をアップロードし、従量課金で復元可能なイベントストリームから分析進捗を確認しつつ、72 時間以内にレポートを取得できます。

[English](./README.md) | [中文文档](./README_CN.md)

## 現在の状況

2026-03-28 時点で、ローカル Docker 上の MVP フローは動作確認済みです。

- `upload -> payment/create -> analysis/start -> orders/{id}/status + events/stream -> report -> 契約本文削除`
- テキスト入力とテキスト抽出可能な PDF は支払い前にそのまま見積もりし、画像 / スキャン PDF は一時保存 + 支払い後の正式 OCR を使う二段階 OCR フローになりました
- 画像とスキャン PDF の見積もりでは、支払い前に OCR 品質ヒント（`low` / `medium` / 支払い後の正式認識案内）を返します
- テキスト入力とテキスト抽出可能な PDF の見積もりでは、支払い前に軽量な条項構造プレビューも返し、契約構造を読み取れたことを示します
- `pgvector` RAG は PostgreSQL 上で稼働し、10 法令カテゴリ・331 件超の法条（賃貸借・労働・パート・業務委託・売買等）を収録
- フロントエンドの 9 言語 UI は実装済み。ブランド（ContractGuard）、プライバシーポリシー/利用規約ページ、独立した事例ギャラリーとレポート見本表示を含みます
- 独立 `/examples` ページは横方向のキュレーション型シナリオ切り替えに刷新され、レポート見本の版面も実際のレポートページにより近づけています
- モバイル UI は、左側メニュー + 中央ロゴ + バッジ型の言語切替を持つよりコンパクトな header に更新され、reveal の即時表示、ケース切替後の自動スクロール、左右余白の最適化、横スクロール防止、iPhone 入力ズーム抑止まで整えました
- ホームページのアップロード導線は `ファイルをアップロード / テキストを貼り付け` の 2 モードに整理され、画像と PDF は 1 つのファイルピッカーで受け付けるようになりました
- review ページは現在「処理中」の体験に専念し、分析完了後は保存済みの `/report/{orderId}` へ直接遷移して結果画面を二重表示しません
- parse 段階でアップロード内容が契約書ではないと判断された場合、分析は即座に停止し、review ページに専用メッセージを表示してホームへ戻せるようになりました
- report ページは高/中/低リスクで条項を絞り込めるようになり、デスクトップでは統計サマリーも 1 行でより密に表示されます
- 共有パネルは最小構成に整理され、内部で紹介コード付きレポート URL を組み立てたうえで、外向けにはリンクコピーと端末共有だけを見せます
- ルート単位の遅延読み込みと分析 SDK の遅延初期化により、初期フロントエンド bundle を軽量化
- `APP_ENV=development` かつ `KOMOJU_SECRET_KEY` 未設定の場合のみ、ローカル開発では自動的に支払い済み扱いになります
- デプロイ設定済み: `fly.toml`（NRT リージョン、HTTPS 強制）+ `vercel.json`（API プロキシ + セキュリティヘッダー）
- 統合テストスイート: 7 つのルーターテストファイルで、現行ランタイムの全 API エンドポイントをカバー
- 分析ページは持続化された分析タスク上に再構築され、バックエンドが `analysis_jobs` / `analysis_events` を保持し、フロントエンドは履歴イベント復元後に新しい更新を購読します
- `docker compose` には postgres・redis・backend API の healthcheck が入り、ローカル起動時に frontend が準備前の backend へ先に当たりにくくなりました
- report / payment / lookup には軽量リトライラッパーを入れ、Docker 起動直後や一時的な弱回線時の取得失敗を吸収します
- ホームページを独立コンポーネントに分割（Hero / Flow / Upload）し、事例紹介は独立 `/examples` ギャラリーページへ移動
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
  Redis: 72時間レポートキャッシュ

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
- Compose の起動順も healthcheck ベースに変更され、`backend` は healthy な `postgres` / `redis` を待ち、`frontend` は healthy な `backend` を待つ構成です。

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
2. 支払い金額と PII 警告を確認します。
3. 支払い注文を作成します。
4. ローカル開発では `APP_ENV=development` かつ `KOMOJU_SECRET_KEY` が空なら自動的に支払い済みになります。
5. `/review/:orderId` では持続化された分析タスクを開始または再開し、履歴イベントを読み込んだ後に新しい進捗更新を受け取ります。
6. parse が「契約書ではない」と判定した場合、review ページはその時点で専用メッセージを表示し、ホームへ戻って再アップロードできます。
7. `/report/:orderId` で保存済みレポートを取得します。
8. ストリーミング審査中は内部ツール名ではなく、ユーザー向けの進捗文言を表示します。
9. 分析が終わると UI はそのまま `/report/:orderId` へ遷移し、保存済みレポートを表示します。
10. report ページでは必要に応じてリスクレベル別に条項を絞り込め、下部からバックエンド生成の正式 PDF をそのままダウンロードできます。
11. レポート本文の言語は支払い時に選択した言語で固定され、後からサイト言語を切り替えても本文自体は再翻訳されません。
12. 72時間のレポート有効期間中は、各分析カード内で対応する元条項の抜粋をその場で展開して比較できます。再オープンしたレポートリンクや共有リンクでも同じ対照を確認できます。
13. 展開後の条項比較は読みやすさを重視しており、モバイルでは縦積み、大きな画面では元条項と分析内容を横並びで表示します。
14. ホームページには3つの契約シナリオ（賃貸・雇用・アルバイト）のインタラクティブなサンプルレポート展示があり、各条項分析は9言語すべてで表示されます。
15. プライバシーポリシー (`/privacy`) と利用規約 (`/terms`) ページはローカライズされた要約と日本語法律全文を組み合わせています。
16. レポート内の参照法令 (`referenced_law`) はユーザーの選択言語にかかわらず、常に日本語原文のまま表示されます。
17. 保存済みレポートページは、より正式な審査レポートらしい版面に寄せており、同じ 72 時間の保存期間内でバックエンド生成の正式 PDF も直接ダウンロードできます。
18. ホームページの「ホーム / サンプル」導線は明示的なアンカー位置へスクロールするようになり、hero の価格文言も固定の見かけ上限を表示しない形に調整されています。
19. プライバシーポリシーや利用規約など別ページへ移動した場合は、自動でページ先頭へ戻るようになりました。
20. report ページ上部の4つの集計カードはそのまま主要フィルターとして機能し、PC / モバイルともに2桁件数でも崩れにくい密度に調整されています。

## 実装上の重要点

- ユーザー契約本文はベクトル DB に保存しません。
- 分析完了後、`orders.contract_text` は `NULL` に更新されます。
- 画像 / スキャン PDF は支払い前に短期間だけ元ファイルを保持し、解析完了後または未払い期限切れ後のクリーンアップで削除されます。
- レポートは Redis に 72 時間キャッシュされ、PostgreSQL に期限付きで保存されます。
- `backend/services/costing.py` により、正式 OCR・parse・analyze・suggestion・translation の構造化コストログが出力されます。
- embedding リクエストもコストログを出力し、review 完了時には見積もりモード・入力種別・条項数を含む注文単位のコスト要約ログも出力されます。
- この注文単位のコスト要約は、ログだけでなく `reports.cost_summary` にも保存されるようになりました。
- 分析が途中で失敗した場合でも、その時点までに発生した AI コスト要約は `analysis_jobs.cost_summary` に保存され、失敗注文も後から監査できます。
- `GET /api/eval/costs` は `reports.cost_summary` を集計し、実データが不足している間は `backend/data/cost_samples_seed.json` で 10 サンプル基準まで補完します。
- 各支払い済み注文では、これとは別に `order_cost_estimates` レコードも保存され、支払い時点の `estimate_snapshot`、分析完了または失敗後の `actual_snapshot`、そして差分用の `comparison_snapshot` が残ります。
- これらのスナップショットには、計画上のモデル構成と実際に使われたモデル構成（`ocr / parse / analyze / suggestion / translation / embedding`）の両方が含まれるため、将来モデルを入れ替えた際の粗利影響を追跡できます。
- `GET /api/eval/costs` は estimate-vs-actual の差分を `estimate_version` とモデルシグネチャ別にも集計するようになり、価格ロジック更新やモデル変更の効果を後から比較できます。
- `GET /api/eval/operations` は seed サンプルを混ぜない読み取り専用の運用 API で、売上・実コスト・実粗利・見積もり偏差・最近の注文一覧に加えて、価格モデル / 支払価格帯 / 入力種別 / 見積もり方式 / 言語 / estimate version / モデルシグネチャ別の集計を返します。
- 実行時の価格設定は Python の固定値ではなく `backend/data/pricing_policy.json` から読み込まれます。現在の運用ポリシーは線形課金で、`1000 tokens あたり ¥75`、最低料金は `¥200` です。
- 注文テーブルでは現在の課金方式を `orders.pricing_model` に保持し、旧 `price_tier` カラムは廃止されました。コンテナ起動時の自動 migration は古い Docker volume もこの形へ安全に前進させます。
- `/api/eval/costs` は「コスト下限の推奨価格」と「目標粗利込みの推奨価格」を両方返します。既定の `target_margin_rate` は `0.75` です。
- `PARSE_MODEL` と `SUGGESTION_MODEL` は設定可能になり、デフォルトでは `gpt-4o-mini` を使います。正式 OCR と条項ごとのリスク判定は引き続きデフォルトで `gpt-4o` のままです。
- `analyze_risks` は、膨張し続ける全契約の多段 tool-calling 会話ではなく、条項ごとの分析に変更されました。これによりコストとコンテキスト圧迫が大きく下がります。
- `analyze_clause_risk` は、長い法令断片をそのまま返す代わりに、圧縮した RAG 要約を返します。
- `generate_suggestion` はリスクレベルに応じて長さを変え、中リスクは短く、高リスクはより具体的に出力します。
- backend コンテナ起動時には、Uvicorn を立ち上げる前に `alembic upgrade head` が自動実行されます。この起動フローは PostgreSQL advisory lock と legacy schema の補正 / stamp を含むため、古い Docker volume も手動 migration なしで安全に前進できます。
- 本番環境で KOMOJU / Resend の必須設定が不足している場合、または `FRONTEND_URL` が `localhost` のままの場合は起動時に失敗します。
- 支払い、審査、メール、レポート取得の主要経路では、構造化アプリケーションログと PostHog イベントを出力し、外部連携時の切り分けをしやすくしています。
- フロントエンドはルート単位で lazy load され、分析系 SDK も非同期初期化されるため、observability 依存が初期 main chunk を膨らませません。
- hash を伴わない画面遷移ではフロントエンドが自動で先頭へスクロールし、前ページのスクロール位置を引き継がないようにしています。
- フロントエンドには `RevealSection`、`OrderReminderDialog`、`ShareSheet` の共通 UX コンポーネントが追加され、スクロール演出、注文番号保存の促し、専用共有パネルを実装しています。共有パネルは内部で紹介コード付き URL を組み立てつつ、表向きはリンクコピーと端末共有だけを見せる最小構成です。
- `frontend/src/lib/fetchWithRetry.ts` で、重要ページの API 取得に対するタイムアウト付き軽量リトライを共通化しています。
- `/api/report/{order_id}` は Redis キャッシュ命中時と PostgreSQL fallback 時で同じ payload 形を返すように統一されています。
- `analyze_clause_risk` ツールが内部で直接 RAG 検索を行うため、独立した retrieval node はありません。
- `scripts/smoke_local_flow.sh` は現在の持続化分析フローに合わせて更新済みで、`health -> upload -> payment -> analysis/start -> orders/{id}/stream -> report -> contract deletion` を通しで確認します。
- 契約書全文は分析後に保持しませんが、72時間レポートには指摘と対応する元条項の抜粋だけを保存します。そのため、再オープンしたレポートリンク、共有リンク、メールリンクでも条項対照を確認できます。
- `scripts/check_locale_keys.sh` は 9 言語の locale ファイルが `ja.json` と同じキー集合を保っているかを確認します。
- バックエンドは起動時に `backend/data/egov_laws.json` の公式 e-Gov 法令コーパスを読み込みます。10 法令カテゴリ・331 件超の法条を収録。ローカル評価データセットも 20 件のラベル付きサンプルに拡張されています（損害賠償、競業禁止、解約、NDA、賃貸借等をカバー）。
- `scripts/check_rag_eval.sh` は `/api/eval/rag` を現在のローカル基準値（`Recall@5 >= 0.45`、`MRR >= 0.45`）でチェックします。
- `scripts/run_backend_pytests.sh` は Docker 内で backend の dev 依存を入れた上で、完全な `tests/` 回帰テストを実行します。
- 統合テストは全 7 API ルーター（health、upload、payment、analysis、report、referral、eval）をカバーしています。
- `frontend/src/pages/HomePage.tsx` は現在コンテナページとして振る舞い、hero / flow / upload-payment を個別コンポーネント（`HomeHeroSection`、`HomeFlowSection`、`HomeUploadSection`）に委譲します。事例紹介は `/examples` の独立ページに切り出されています。
- 見積もり生成後、ホームページは自動で支払いパネルまでスクロールし、短時間ハイライトして次の導線を見失いにくくしています。
- `/lookup` 結果照会ページが追加され、注文番号から支払い状態ページ・分析中ページ・完成レポートを再オープンできます。
- 支払い完了時と分析完了時には、注文番号をスクリーンショット保存またはコピーするよう促すダイアログを表示します。
- レポート共有は直接 Web Share API を呼ぶのではなく、紹介コード付きレポート URL を内部で生成したうえで、リンクコピーと端末共有だけを見せる専用共有パネルを先に開きます。
- 紹介リンクは `?ref=` 付きでホームに戻り、次のユーザーの支払いフォームへ紹介コードを自動入力します。
- 結果照会ページとレポートページは、注文番号形式エラー、弱い回線、オフライン、再試行可能な失敗状態をより明確に表示します。
- 分析フローは、単一の SSE POST リクエストで実行を開始するのではなく、状態スナップショット、再生可能な履歴イベント、増分イベントストリームで駆動されます。
- RAG embedding リクエストは `_get_embeddings_batch_sync()` と `search_batch()` によりバッチ化され、API 呼び出し回数を削減しています。

## 主要ファイル

- [`backend/main.py`](./backend/main.py): 起動処理、ルーター登録、Sentry/PostHog、クリーンアップ
- [`backend/routers/analysis.py`](./backend/routers/analysis.py): 分析開始、状態スナップショット、履歴イベント、増分イベントストリーム
- [`backend/services/analysis_executor.py`](./backend/services/analysis_executor.py): プロセス内の持続化分析実行器とイベント永続化
- [`backend/rag/store.py`](./backend/rag/store.py): pgvector 保存と検索
- [`backend/eval/evaluator.py`](./backend/eval/evaluator.py): RAG 評価指標とデータセット実行
- [`scripts/smoke_local_flow.sh`](./scripts/smoke_local_flow.sh): ローカル end-to-end smoke/regression スクリプト
- [`scripts/check_locale_keys.sh`](./scripts/check_locale_keys.sh): locale キー整合性チェック
- [`scripts/check_rag_eval.sh`](./scripts/check_rag_eval.sh): ローカル RAG 回帰チェック
- [`scripts/run_backend_pytests.sh`](./scripts/run_backend_pytests.sh): Docker ベースの backend pytest 実行スクリプト
- [`frontend/src/main.tsx`](./frontend/src/main.tsx): ルーター、i18n、遅延読み込み、分析初期化
- [`frontend/src/lib/fetchWithRetry.ts`](./frontend/src/lib/fetchWithRetry.ts): 主要 API 取得向けのタイムアウト + リトライラッパー
- [`frontend/src/components/home/HomeHeroSection.tsx`](./frontend/src/components/home/HomeHeroSection.tsx): ホームページ hero セクション
- [`frontend/src/components/home/HomeFlowSection.tsx`](./frontend/src/components/home/HomeFlowSection.tsx): ホームページフローステップ
- [`frontend/src/components/home/HomeExamplesSection.tsx`](./frontend/src/components/home/HomeExamplesSection.tsx): ホームページサンプル展示
- [`frontend/src/components/home/HomeUploadSection.tsx`](./frontend/src/components/home/HomeUploadSection.tsx): ホームページアップロード
- [`frontend/src/pages/ExamplesPage.tsx`](./frontend/src/pages/ExamplesPage.tsx): 独立した事例ギャラリー / レポート見本ページ
- [`frontend/src/pages/LookupPage.tsx`](./frontend/src/pages/LookupPage.tsx): 注文番号ベースの結果照会ページ
- [`frontend/src/components/common/OrderReminderDialog.tsx`](./frontend/src/components/common/OrderReminderDialog.tsx): 注文番号保存を促すダイアログ
- [`frontend/src/components/common/ShareSheet.tsx`](./frontend/src/components/common/ShareSheet.tsx): 専用共有パネル
- [`tests/`](./tests/): 全 7 API ルーターの統合テスト + ユニットテスト
- [`SPEC.md`](./SPEC.md): 詳細な進捗、未完了項目、リスク
- [`DESIGN.md`](./DESIGN.md): プロダクト設計とビジネス方針
