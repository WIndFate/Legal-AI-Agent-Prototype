import logging

import httpx

from backend.config import get_settings
from backend.services.analytics import capture as posthog_capture
from backend.services.analytics import capture_exception as sentry_capture_exception

logger = logging.getLogger(__name__)

# Shared Japanese legal disclaimer (required on all outgoing emails)
_DISCLAIMER_HTML = (
    '<hr style="border:none;border-top:1px solid #e0e0e0;margin:24px 0 12px;">'
    '<p style="font-size:12px;color:#888;line-height:1.5;">'
    "本サービスは法律相談ではありません。具体的な法的判断は弁護士にご相談ください。</p>"
)


async def _send_email(
    email: str,
    order_id: str,
    language: str,
    subject: str,
    html_body: str,
    *,
    event_prefix: str,
) -> bool:
    """Low-level email sender via Resend API with shared tracking logic."""
    settings = get_settings()

    if not settings.RESEND_API_KEY:
        logger.warning("Skipping %s: order_id=%s reason=resend_not_configured", event_prefix, order_id)
        posthog_capture(
            email or order_id,
            f"{event_prefix}_skipped",
            {"order_id": order_id, "reason": "resend_not_configured", "language": language},
        )
        return False

    full_html = (
        '<div style="font-family:sans-serif;max-width:560px;margin:0 auto;color:#222;">'
        f"{html_body}"
        f"{_DISCLAIMER_HTML}"
        "</div>"
    )

    try:
        logger.info("Sending %s: order_id=%s email=%s language=%s", event_prefix, order_id, email, language)
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
                json={
                    "from": f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM_ADDRESS}>",
                    "to": [email],
                    "reply_to": settings.EMAIL_REPLY_TO,
                    "subject": subject,
                    "html": full_html,
                },
            )
            response.raise_for_status()
            logger.info("%s sent: order_id=%s email=%s status_code=%s", event_prefix, order_id, email, response.status_code)
            posthog_capture(
                email or order_id,
                f"{event_prefix}_sent",
                {"order_id": order_id, "language": language},
            )
            return True
    except Exception as e:
        logger.error("%s failed: order_id=%s email=%s error=%s", event_prefix, order_id, email, e)
        posthog_capture(
            email or order_id,
            f"{event_prefix}_failed",
            {"order_id": order_id, "language": language, "error": str(e)},
        )
        sentry_capture_exception(
            e,
            tags={"component": "email", "event": event_prefix, "order_id": order_id, "language": language},
        )
        return False


# ---------------------------------------------------------------------------
# Email 1: Payment Confirmation
# ---------------------------------------------------------------------------

_PAYMENT_SUBJECTS = {
    "ja": "お支払い完了 — ContractGuard",
    "en": "Payment Confirmed — ContractGuard",
    "zh-CN": "付款确认 — ContractGuard",
    "zh-TW": "付款確認 — ContractGuard",
    "ko": "결제 완료 — ContractGuard",
    "vi": "Xác nhận thanh toán — ContractGuard",
    "pt-BR": "Pagamento Confirmado — ContractGuard",
    "id": "Pembayaran Dikonfirmasi — ContractGuard",
    "ne": "भुक्तानी पुष्टि — ContractGuard",
}

_PAYMENT_BODIES = {
    "ja": (
        "お支払いが完了しました。契約書のリスク分析を開始しています。",
        "分析の進捗をリアルタイムで確認できます：",
        "進捗を確認する",
        "このメールを保存してください。上のリンクからいつでも進捗を確認できます。",
    ),
    "en": (
        "Your payment has been confirmed. We are now analyzing your contract.",
        "Track your analysis progress in real time:",
        "Track Progress",
        "Save this email — you can return anytime to check progress via the link above.",
    ),
    "zh-CN": (
        "支付成功，合同风险分析已开始。",
        "你可以实时查看分析进度：",
        "查看进度",
        "请保存此邮件，你可以随时通过上方链接查看分析进度。",
    ),
    "zh-TW": (
        "付款成功，合約風險分析已開始。",
        "你可以即時查看分析進度：",
        "查看進度",
        "請保存此郵件，你可以隨時透過上方連結查看分析進度。",
    ),
    "ko": (
        "결제가 완료되었습니다. 계약서 위험 분석이 시작되었습니다.",
        "분석 진행 상황을 실시간으로 확인하세요:",
        "진행 상황 확인",
        "이 이메일을 저장하세요. 위 링크에서 언제든지 진행 상황을 확인할 수 있습니다.",
    ),
    "vi": (
        "Thanh toán đã được xác nhận. Chúng tôi đang phân tích hợp đồng của bạn.",
        "Theo dõi tiến trình phân tích theo thời gian thực:",
        "Theo dõi tiến trình",
        "Hãy lưu email này — bạn có thể quay lại kiểm tra tiến trình bất cứ lúc nào.",
    ),
    "pt-BR": (
        "Pagamento confirmado. A análise de risco do seu contrato foi iniciada.",
        "Acompanhe o progresso da análise em tempo real:",
        "Acompanhar progresso",
        "Salve este e-mail — você pode voltar para verificar o progresso a qualquer momento.",
    ),
    "id": (
        "Pembayaran dikonfirmasi. Analisis risiko kontrak Anda sedang dimulai.",
        "Pantau kemajuan analisis secara real-time:",
        "Pantau kemajuan",
        "Simpan email ini — Anda dapat kembali kapan saja untuk memeriksa kemajuan.",
    ),
    "ne": (
        "भुक्तानी पुष्टि भयो। तपाईंको सम्झौता जोखिम विश्लेषण सुरु भएको छ।",
        "विश्लेषण प्रगति वास्तविक समयमा हेर्नुहोस्:",
        "प्रगति हेर्नुहोस्",
        "यो इमेल बचत गर्नुहोस् — तपाईं जुनसुकै बेला प्रगति जाँच गर्न फर्कन सक्नुहुन्छ।",
    ),
}

_PAYMENT_META_LABELS = {
    "ja": ("注文ID", "お支払い金額"),
    "en": ("Order ID", "Amount"),
    "zh-CN": ("订单号", "支付金额"),
    "zh-TW": ("訂單號", "支付金額"),
    "ko": ("주문 ID", "결제 금액"),
    "vi": ("Mã đơn hàng", "Số tiền thanh toán"),
    "pt-BR": ("ID do pedido", "Valor pago"),
    "id": ("ID pesanan", "Jumlah pembayaran"),
    "ne": ("अर्डर ID", "भुक्तानी रकम"),
}


async def send_payment_confirmation_email(
    email: str,
    order_id: str,
    language: str,
    amount_jpy: int,
) -> bool:
    """Send payment confirmation with review progress link."""
    settings = get_settings()
    review_url = f"{settings.FRONTEND_URL}/review/{order_id}"

    subject = _PAYMENT_SUBJECTS.get(language, _PAYMENT_SUBJECTS["ja"])
    intro, track_label, cta_text, save_note = _PAYMENT_BODIES.get(language, _PAYMENT_BODIES["ja"])
    order_id_label, amount_label = _PAYMENT_META_LABELS.get(language, _PAYMENT_META_LABELS["ja"])

    html_body = (
        f'<p style="font-size:16px;font-weight:600;margin:0 0 16px;">{subject}</p>'
        f"<p>{intro}</p>"
        f'<p style="margin:8px 0;"><strong>{order_id_label}:</strong> <code style="background:#f5f5f5;padding:2px 6px;border-radius:3px;">{order_id}</code></p>'
        f'<p style="margin:8px 0;"><strong>{amount_label}:</strong> ¥{amount_jpy:,}</p>'
        f"<p>{track_label}</p>"
        f'<p style="margin:16px 0;">'
        f'<a href="{review_url}" style="display:inline-block;background:#2563eb;color:#fff;'
        f'padding:10px 24px;border-radius:6px;text-decoration:none;font-weight:600;">'
        f"{cta_text}</a></p>"
        f'<p style="font-size:13px;color:#666;">{save_note}</p>'
    )

    return await _send_email(email, order_id, language, subject, html_body, event_prefix="payment_confirmation_email")


# ---------------------------------------------------------------------------
# Email 2: Report Ready
# ---------------------------------------------------------------------------

_REPORT_SUBJECTS = {
    "ja": "契約書リスク分析レポート — ContractGuard",
    "en": "Contract Risk Analysis Report — ContractGuard",
    "zh-CN": "合同风险分析报告 — ContractGuard",
    "zh-TW": "合約風險分析報告 — ContractGuard",
    "ko": "계약서 위험 분석 보고서 — ContractGuard",
    "vi": "Báo cáo phân tích rủi ro hợp đồng — ContractGuard",
    "pt-BR": "Relatório de Análise de Risco do Contrato — ContractGuard",
    "id": "Laporan Analisis Risiko Kontrak — ContractGuard",
    "ne": "सम्झौता जोखिम विश्लेषण रिपोर्ट — ContractGuard",
}

_REPORT_BODIES = {
    "ja": (
        "契約書のリスク分析が完了しました。",
        "レポートを確認する",
        "レポートページからPDFも保存できます。",
    ),
    "en": (
        "Your contract risk analysis is complete.",
        "View Report",
        "You can also download a PDF from the report page.",
    ),
    "zh-CN": (
        "合同风险分析已完成。",
        "查看报告",
        "你也可以从报告页面下载 PDF。",
    ),
    "zh-TW": (
        "合約風險分析已完成。",
        "查看報告",
        "你也可以從報告頁面下載 PDF。",
    ),
    "ko": (
        "계약서 위험 분석이 완료되었습니다.",
        "보고서 보기",
        "보고서 페이지에서 PDF도 다운로드할 수 있습니다.",
    ),
    "vi": (
        "Phân tích rủi ro hợp đồng của bạn đã hoàn tất.",
        "Xem báo cáo",
        "Bạn cũng có thể tải PDF từ trang báo cáo.",
    ),
    "pt-BR": (
        "A análise de risco do seu contrato foi concluída.",
        "Ver relatório",
        "Você também pode baixar o PDF pela página do relatório.",
    ),
    "id": (
        "Analisis risiko kontrak Anda telah selesai.",
        "Lihat laporan",
        "Anda juga dapat mengunduh PDF dari halaman laporan.",
    ),
    "ne": (
        "तपाईंको सम्झौता जोखिम विश्लेषण पूरा भयो।",
        "रिपोर्ट हेर्नुहोस्",
        "तपाईं रिपोर्ट पृष्ठबाट PDF पनि डाउनलोड गर्न सक्नुहुन्छ।",
    ),
}

_REPORT_EXPIRY_WARNINGS = {
    "ja": "{hours} 時間以内にレポートを確認・保存してください。期限を過ぎるとアクセスできなくなります。",
    "en": "Please view and save your report within {hours} hours. It will no longer be accessible after that.",
    "zh-CN": "请在 {hours} 小时内查看并保存报告，逾期将无法访问。",
    "zh-TW": "請在 {hours} 小時內查看並保存報告，逾期將無法存取。",
    "ko": "{hours}시간 내에 보고서를 확인하고 저장하세요. 이후에는 접근할 수 없습니다.",
    "vi": "Vui lòng xem và lưu báo cáo trong vòng {hours} giờ. Sau đó sẽ không thể truy cập được.",
    "pt-BR": "Visualize e salve seu relatório em até {hours} horas. Após esse prazo, ele não estará mais acessível.",
    "id": "Harap lihat dan simpan laporan Anda dalam {hours} jam. Setelah itu tidak dapat diakses lagi.",
    "ne": "कृपया {hours} घण्टाभित्र रिपोर्ट हेर्नुहोस् र बचत गर्नुहोस्। त्यसपछि पहुँच सम्भव हुनेछैन।",
}

_REPORT_ORDER_ID_LABELS = {
    "ja": "注文ID",
    "en": "Order ID",
    "zh-CN": "订单号",
    "zh-TW": "訂單號",
    "ko": "주문 ID",
    "vi": "Mã đơn hàng",
    "pt-BR": "ID do pedido",
    "id": "ID pesanan",
    "ne": "अर्डर ID",
}


async def send_report_email(email: str, order_id: str, language: str) -> bool:
    """Send report-ready notification with prominent expiration warning."""
    settings = get_settings()
    report_url = f"{settings.FRONTEND_URL}/report/{order_id}"
    ttl = settings.REPORT_TTL_HOURS

    subject = _REPORT_SUBJECTS.get(language, _REPORT_SUBJECTS["ja"])
    intro, cta_text, pdf_note = _REPORT_BODIES.get(language, _REPORT_BODIES["ja"])
    expiry_warning = _REPORT_EXPIRY_WARNINGS.get(language, _REPORT_EXPIRY_WARNINGS["ja"]).format(hours=ttl)
    order_id_label = _REPORT_ORDER_ID_LABELS.get(language, _REPORT_ORDER_ID_LABELS["ja"])

    html_body = (
        f'<p style="font-size:16px;font-weight:600;margin:0 0 16px;">{subject}</p>'
        f"<p>{intro}</p>"
        f'<p style="margin:16px 0;">'
        f'<a href="{report_url}" style="display:inline-block;background:#2563eb;color:#fff;'
        f'padding:10px 24px;border-radius:6px;text-decoration:none;font-weight:600;">'
        f"{cta_text}</a></p>"
        f'<div style="background:#fef3c7;border-left:4px solid #f59e0b;padding:10px 14px;'
        f'border-radius:4px;margin:16px 0;">'
        f'<p style="margin:0;font-weight:600;color:#92400e;">⏱ {expiry_warning}</p>'
        f"</div>"
        f'<p style="font-size:13px;color:#666;">{pdf_note}</p>'
        f'<p style="font-size:13px;color:#666;">{order_id_label}: '
        f'<code style="background:#f5f5f5;padding:2px 6px;border-radius:3px;">{order_id}</code></p>'
    )

    return await _send_email(email, order_id, language, subject, html_body, event_prefix="report_email")
