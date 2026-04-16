# OCR 供应商迁移开发计划 — GPT-4o Vision → Google Cloud Vision

**起草日期**：2026-04-17
**目标版本**：ContractGuard V1 上线前
**关联文档**：`docs/PRE_LAUNCH_AUDIT.md`（本计划同时兑付其中的 P0-2 日预算熔断）
**状态**：⏳ 待实施（Commit 0 本身即为本文件）

---

## 1. Context（为什么要做）

当前 OCR 路径走 GPT-4o Vision，单次合同 OCR 成本 ¥10–¥50（占营收 1–4%），是 `PRE_LAUNCH_AUDIT.md` P0-1 / P0-2 的核心成本滥用攻击面。对个人独立项目而言，"攻击成本上限不可控"是心理负担最大的源头——即使 P0-1 三轮加固已落地（`abuse_guard.py` waste 计数 + OCR cache + IP 截断），GPT-4o Vision 本身的单价决定了被刷 1 万次就是 ¥60,000 损失。

**目标**：把 OCR 单次成本从 ¥10–¥50 压到 ¥0.2（降 50–250 倍），攻击成本上限从"不可控"变为"每天最多 ¥500 封顶"。

**为什么选 Google Cloud Vision (DOCUMENT_TEXT_DETECTION)**：

- 首 1000 页/月**免费** → 个人项目早期实际 OCR 成本 = ¥0
- 超出后 $1.5/1000 页（约 ¥0.225/页），比 Azure Read 多一层"早期免费额度"；比 PaddleOCR 少"2 GB VM 升级（¥6,750/月固定支出）+ 部署复杂度 + 日文手写质量劣势"
- 合同场景准确率约 95%（vs GPT-4o Vision ~97%，差 2 个百分点），但**无幻觉风险**——Vision LLM 可能把无法识别的位置"推理补齐"成看似合理但伪造的文字，对法律文本是劣势，纯 OCR 在这一维度反而更安全
- 保留 512 MB Fly VM 不变

**替代方案已否决**：

| 方案 | 否决原因 |
|---|---|
| 继续 GPT-4o Vision + 强化防护 | 攻击成本上限本质不可控，单价决定被刷风险 |
| Azure Document Intelligence (Read) | 无免费额度，对早期流量不够友好 |
| PaddleOCR 本地推理 | VM 升级到 2 GB 固定支出 ~¥6,750/月 + 日文手写准确率劣势 + 冷启动 5–10 s |

**纵深防御叠加后的攻击成本上限**：

```
Google Vision (OCR)            — 单次 ~¥0.2，被刷也便宜
    +
cost_guard 日预算熔断 (P0-2)   — 全局每日 ¥500 硬顶，超限 503
    +
abuse_guard (现状 + 放宽)      — per-IP OCR waste 10/天软限流
    +
upload_validation / pdf_precheck — 已有的大小 / 页数 / MIME 前置
```

攻击者即使绕过前两层，每日最大损失 ¥500，可接受。

---

## 2. 关键设计决策

1. **Google Vision 认证方式**：Service Account JSON → base64 编码进 Fly secret `GOOGLE_APPLICATION_CREDENTIALS_JSON`，启动时解码写 `/tmp/gcp-sa.json` 并设 `GOOGLE_APPLICATION_CREDENTIALS` 指向它。SA 在 GCP 控制台限定 `roles/cloudvision.user`。
   - 否决 API Key：URL 里带 key 会进日志，泄漏后无法限制到仅 Vision。
   - 否决 volume 挂载：Fly.io 上要走 build-time secret，复杂度不划算。

2. **扫描 PDF 处理**：`pdf2image` + 系统包 `poppler-utils` 每页渲染为图片（DPI=200）后逐页调 Vision，最后拼接文本。仅对"文本层不足"的扫描 PDF 走此路径（`pdf_extractor.pdf_text_layer_is_sufficient` 已过滤绝大多数 PDF）。串行处理，每页渲染完 `del` 释放内存，确保 512 MB VM 稳定。
   - 否决 `asyncBatchAnnotate`：依赖 GCS bucket 输入输出，违背"个人项目简易"。
   - 否决保留 GPT-4o 处理 PDF：PDF 是 OCR 成本大头，保留等于没省钱。

3. **snapshot 字段兼容**：`ocr_model="google-vision-document-text"`，`ocr_input_tokens=pages`（借位语义便于日志可读），`ocr_output_tokens=len(text)`，`ocr_cost_usd=pages * 0.0015`，`ocr_cost_jpy=pages * 0.225`。不改 `backend/services/costing.py`——`extract_usage` 读不到 `usage_metadata` 会 fallback 到 0，`estimate_cost_usd` 对未知 model key 返回 0.0，均不报错；真实成本由 `_build_vision_snapshot` 手填。

4. **`OCR_WASTE_DAILY_LIMIT` 放宽**：3 → 10。成本维度（¥30 → ¥0.2，降 150 倍）理论上能放到 400+，但 abuse_guard 真正防的是带宽 / Redis / Postgres 行数被刷，不是纯 API 费用。10 次/天/IP 能覆盖"真实用户反复试不同合同"（P99 < 5），同时给 `cost_guard` 熔断留下全局兜底。

5. **`cost_guard` 最小实现**：`backend/services/cost_guard.py` 新增；Redis key `cost_guard:daily:{YYYY-MM-DD}`，INCRBYFLOAT + 首次 EXPIRE 86400；fail-closed（Redis 挂 → 503）。仅埋在 OCR 入口（图片分支 + 扫描 PDF 分支）；LLM 分析链路的埋点留给后续迭代，本期先把"最可刷的成本源"卡死。

---

## 3. 修改清单（按独立 commit 分块）

### Commit 0 — 本计划落地（即本文件）

- 新建 `docs/OCR_MIGRATION_PLAN.md`（本文）
- Commit message：`Add OCR migration plan: GPT-4o Vision → Google Cloud Vision`

### Commit 1 — 依赖与 Dockerfile

- `pyproject.toml`：追加 `google-cloud-vision>=3.7.0` 和 `pdf2image>=1.17.0`
- `backend/Dockerfile`：在 `apt-get install` 列表追加 `poppler-utils`（~15 MB）
- **不删** `openai` / `langchain-openai`（后端分析链路 gpt-4o / gpt-4o-mini 仍在用）

### Commit 2 — 配置新增

- `backend/config.py::Settings` 新增：
  - `GOOGLE_APPLICATION_CREDENTIALS_JSON: str = ""`（base64）
  - `GOOGLE_VISION_PROJECT_ID: str = ""`
  - `DAILY_COST_BUDGET_JPY: float = 500.0`
  - `GOOGLE_VISION_COST_PER_PAGE_JPY: float = 0.225`
  - `OCR_WASTE_DAILY_LIMIT` 默认值 3 → 10
- `validate_runtime()`：生产环境必须配 `GOOGLE_APPLICATION_CREDENTIALS_JSON`，否则 `raise ValueError`
- `backend/main.py` lifespan：启动时 base64 解码 JSON 到 `/tmp/gcp-sa.json`，设 `os.environ["GOOGLE_APPLICATION_CREDENTIALS"]`

### Commit 3 — 新增 cost_guard（P0-2 日预算熔断）

- 新建 `backend/services/cost_guard.py`：
  - `check_budget_allowed(redis, estimated_jpy) -> bool`（fail-closed）
  - `record_cost(redis, actual_jpy) -> None`（INCRBYFLOAT + 首次 EXPIRE 86400）
  - `get_today_spent(redis) -> float`（诊断用）
- 新增 `tests/test_cost_guard.py`：fake redis + 边界（未超 / 刚超 / Redis down）

### Commit 4 — Google Vision OCR 服务

- 新建 `backend/services/google_vision_ocr.py`：
  - `extract_text_from_image_with_snapshot(image_bytes, mime_type) -> (text, snapshot)`
  - `extract_text_from_pdf_with_snapshot(pdf_bytes) -> (text, snapshot)` — 内部 `pdf2image.convert_from_bytes(dpi=200)` → 逐页 `document_text_detection` → 拼接
  - `_build_vision_snapshot(pages, text)` — 按设计决策 3 填字段
  - Vision API 异常时直接 raise（交由 upload.py 的 `rollback_ocr_upload` 回滚）
- `backend/services/ocr.py`：改为一行 re-export `from backend.services.google_vision_ocr import *`，避免改动 upload.py 的 import 路径；后续稳定后再删旧文件

### Commit 5 — upload.py 埋点 cost_guard

- `backend/routers/upload.py` 图片 / PDF 扫描分支：
  - `record_ocr_upload` 之后、`extract_text_from_*` 之前追加：
    ```python
    budget_ok = await check_budget_allowed(redis, settings.GOOGLE_VISION_COST_PER_PAGE_JPY * estimated_pages)
    if not budget_ok:
        await rollback_ocr_upload(redis, client_ip)
        raise HTTPException(503, detail="daily_budget_exhausted")
    ```
  - OCR 成功后 `await record_cost(redis, snapshot["ocr_cost_jpy"])`
- 图片分支 `estimated_pages = 1`；PDF 分支在 `precheck_pdf_pages` 返回值里拿真实页数

### Commit 6 — 9 语言 i18n 新错误码

- `frontend/src/i18n/locales/{ja,en,zh-CN,zh-TW,ko,pt-BR,id,vi,ne}.json` 新增 `daily_budget_exhausted`
  - `ja`: "本日の処理枠に達しました。明日再度お試しください。"
  - `zh-CN`: "今日处理配额已达上限，请明天再试。"
  - `en`: "Today's processing quota is exhausted. Please try again tomorrow."
  - 其余 6 语言按现有 i18n 基线语气补齐
- `scripts/check_locale_keys.sh` 必须全绿

### Commit 7 — 测试补全

- 新增 `tests/test_google_vision_ocr.py`：mock `vision.ImageAnnotatorClient.document_text_detection`，覆盖单图、扫描 PDF（mock `pdf2image.convert_from_bytes`）、API 异常路径
- 新增 `tests/test_router_upload_budget.py`：Redis 累计 ¥499 + 预估 ¥2 → 503 `daily_budget_exhausted`；累计 ¥100 + 预估 ¥2 → 200
- `tests/test_security_hardening.py` 既有测试必须继续通过（abuse_guard 逻辑未改）

### Commit 8 — 文档同步

- `docs/PRE_LAUNCH_AUDIT.md`：P0-2 条目顶部加 `✅ Fixed in <sha> (<date>)`；附录 A 表 P0-2 状态 ⏳ → ✅
- `SPEC.md`：OCR 提供商字段改为 "Google Cloud Vision API (DOCUMENT_TEXT_DETECTION)"；环境变量表追加 `GOOGLE_APPLICATION_CREDENTIALS_JSON` / `GOOGLE_VISION_PROJECT_ID` / `DAILY_COST_BUDGET_JPY`
- `README.md` + `README_CN.md` + `README_JA.md`：外部依赖清单同步（仅当该条目已存在时更新；不主动新增段落）
- `CLAUDE.md` + `AGENTS.md`：架构铁律追加 "OCR 供应商是 Google Vision，不要换回 GPT-4o Vision"

---

## 4. 关键文件路径

| 文件 | 动作 |
|---|---|
| `docs/OCR_MIGRATION_PLAN.md` | 新增（Commit 0，本文件） |
| `pyproject.toml` | 修改（Commit 1） |
| `backend/Dockerfile` | 修改（Commit 1） |
| `backend/config.py` | 修改（Commit 2） |
| `backend/main.py` | 修改（Commit 2，lifespan 里解码 SA JSON） |
| `backend/services/cost_guard.py` | 新增（Commit 3） |
| `backend/services/google_vision_ocr.py` | 新增（Commit 4） |
| `backend/services/ocr.py` | 修改为 re-export（Commit 4） |
| `backend/routers/upload.py` | 修改（Commit 5） |
| `frontend/src/i18n/locales/*.json` | 修改 9 份（Commit 6） |
| `tests/test_cost_guard.py` | 新增（Commit 3） |
| `tests/test_google_vision_ocr.py` | 新增（Commit 7） |
| `tests/test_router_upload_budget.py` | 新增（Commit 7） |
| `docs/PRE_LAUNCH_AUDIT.md` | 修改（Commit 8，P0-2 ✅） |
| `SPEC.md` + `README*.md` | 修改（Commit 8） |
| `CLAUDE.md` + `AGENTS.md` | 修改（Commit 8，架构铁律） |

---

## 5. 复用的既有函数（避免重复造轮子）

- `backend/services/pdf_extractor.py::precheck_pdf_pages` — PDF 进入 Vision 前的页数 / 加密校验，**直接复用**
- `backend/services/pdf_extractor.py::extract_text_from_pdf_text_layer` + `pdf_text_layer_is_sufficient` — 文本层优先路径，**直接复用**（只有不足时才走 Vision）
- `backend/services/quote_guard.py::load_ocr_result_cache` / `store_ocr_result_cache` — OCR 结果缓存（按 file hash），**直接复用**
- `backend/services/abuse_guard.py::check_ocr_allowed` / `record_ocr_upload` / `rollback_ocr_upload` — per-IP OCR waste 计数，**直接复用**，只调 `OCR_WASTE_DAILY_LIMIT` 默认值
- `backend/services/upload_validation.py::detect_and_validate_mime` / `check_upload_file_size` — 上传前置校验，**零改动**
- `backend/services/costing.py::log_model_usage` — 通过 `SimpleNamespace` 构造假 response 传入即可兼容（详见 Commit 4）

---

## 6. 验证方案

### 6.1 单元 / 集成测试

```bash
docker compose up --build backend
scripts/run_backend_pytests.sh        # 含新增 test_cost_guard / test_google_vision_ocr / test_router_upload_budget
scripts/check_locale_keys.sh          # 9 语言 daily_budget_exhausted key 完整
scripts/check_rag_eval.sh             # 不受本次改动影响，基线保持
```

### 6.2 端到端冒烟（本地 docker compose）

1. 准备一张清晰的日文合同图片（JPG）和一份扫描版 PDF（≤ 20 页）
2. `curl -F file=@contract.jpg -F input_type=image http://localhost:8000/api/upload` → `contract_text` 非空、`price_jpy > 0`
3. `curl -F file=@scan.pdf -F input_type=pdf http://localhost:8000/api/upload` → 同上
4. `docker compose logs backend` 里可见 `ocr_model=google-vision-document-text` 且 `ocr_cost_jpy > 0`
5. `scripts/smoke_local_flow.sh` 全绿

### 6.3 熔断回归

```bash
# 手动把 Redis key 调到接近阈值
docker compose exec redis redis-cli SET "cost_guard:daily:$(date +%F)" 499
curl -F file=@contract.jpg -F input_type=image http://localhost:8000/api/upload
# 期望：503 + detail="daily_budget_exhausted"

# 清零后恢复
docker compose exec redis redis-cli DEL "cost_guard:daily:$(date +%F)"
```

### 6.4 生产部署验证

1. `fly secrets set GOOGLE_APPLICATION_CREDENTIALS_JSON=$(base64 -w0 gcp-sa.json)`
2. `fly secrets set GOOGLE_VISION_PROJECT_ID=xxx DAILY_COST_BUDGET_JPY=500`
3. `fly deploy`
4. 部署后 `curl https://api.contractguard.jp/api/health` → 200
5. 上传一份真实合同，确认 Sentry 无异常、GCP Vision 控制台可见调用
6. 监控第一周 GCP Vision 用量，确认 ≤ 1000 页/月（免费额度内）

---

## 7. 风险与回滚

- **GCP Service Account 泄漏**：Fly secret 泄漏 → 攻击者可直接刷 GCP 账户。缓解：SA 只给 `cloudvision.user` 角色；GCP Billing 设 ¥5,000/月硬顶警报；定期 rotate。
- **pdf2image 内存爆炸**：扫描 PDF 渲染超过 VM 内存。缓解：`precheck_pdf_pages` 已限 20 页；DPI=200；单页完成立即 `del`；若仍不稳，降 DPI 到 150。
- **Google Vision 准确率不符预期**：某些手写合同识别率显著低于 GPT-4o Vision。缓解：旧 `ocr.py` 的 GPT-4o 实现在 git 历史里保留，极端情况可回滚 Commit 4；后续可提供"文本框编辑"UI 让用户修正（超出本计划范围）。
- **实现卡在某步**：按 Commit 1 → 8 独立可合并可回退，不会一次性阻断主分支。

---

## 8. 变更记录

- 2026-04-17：初版（Commit 0），计划来自于 P0-1 三轮加固 + P0-2 讨论后的供应商切换决策。
