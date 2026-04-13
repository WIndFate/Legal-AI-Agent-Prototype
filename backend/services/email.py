import logging

import httpx

from backend.config import get_settings
from backend.services.analytics import capture as posthog_capture
from backend.services.analytics import capture_exception as sentry_capture_exception

logger = logging.getLogger(__name__)


async def send_report_email(email: str, order_id: str, language: str) -> bool:
    """Send report link via Resend API."""
    settings = get_settings()

    if not settings.RESEND_API_KEY:
        logger.warning("Skipping report email: order_id=%s reason=resend_not_configured", order_id)
        posthog_capture(
            email or order_id,
            "report_email_skipped",
            {"order_id": order_id, "reason": "resend_not_configured", "language": language},
        )
        return False

    report_url = f"{settings.FRONTEND_URL}/report/{order_id}"

    # Language-aware subject lines
    subjects = {
        "ja": "契約書リスク分析レポート",
        "en": "Contract Risk Analysis Report",
        "zh-CN": "合同风险分析报告",
        "zh-TW": "合約風險分析報告",
        "ko": "계약서 위험 분석 보고서",
        "vi": "Báo cáo phân tích rủi ro hợp đồng",
        "pt-BR": "Relatório de Análise de Risco do Contrato",
        "id": "Laporan Analisis Risiko Kontrak",
        "ne": "सम्झौता जोखिम विश्लेषण रिपोर्ट",
    }

    subject = subjects.get(language, subjects["ja"])
    expires_text = f"This link expires in {settings.REPORT_TTL_HOURS} hours."
    pdf_notes = {
        "ja": f"レポートページから {settings.REPORT_TTL_HOURS} 時間以内にPDF保存も行えます。",
        "en": f"You can also download a PDF from the report page within {settings.REPORT_TTL_HOURS} hours.",
        "zh-CN": f"你也可以在 {settings.REPORT_TTL_HOURS} 小时内从报告页面下载 PDF。",
        "zh-TW": f"你也可以在 {settings.REPORT_TTL_HOURS} 小時內從報告頁面下載 PDF。",
        "ko": f"{settings.REPORT_TTL_HOURS}시간 내에 보고서 페이지에서 PDF도 다운로드할 수 있습니다.",
        "vi": f"Bạn cũng có thể tải PDF từ trang báo cáo trong vòng {settings.REPORT_TTL_HOURS} giờ.",
        "pt-BR": f"Voce também pode baixar o PDF pela página do relatório em até {settings.REPORT_TTL_HOURS} horas.",
        "id": f"Anda juga dapat mengunduh PDF dari halaman laporan dalam {settings.REPORT_TTL_HOURS} jam.",
        "ne": f"तपाईंले {settings.REPORT_TTL_HOURS} घण्टाभित्र रिपोर्ट पृष्ठबाट PDF पनि डाउनलोड गर्न सक्नुहुन्छ।",
    }
    pdf_note = pdf_notes.get(language, pdf_notes["ja"])

    try:
        logger.info("Sending report email: order_id=%s email=%s language=%s", order_id, email, language)
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
                json={
                    "from": f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM_ADDRESS}>",
                    "to": [email],
                    "reply_to": settings.EMAIL_REPLY_TO,
                    "subject": subject,
                    "html": (
                        f'<p><a href="{report_url}">{subject}</a></p>'
                        f"<p>{expires_text}</p>"
                        f"<p>{pdf_note}</p>"
                        f'<hr><p style="font-size:12px;color:#666;">'
                        f'本サービスは法律相談ではありません。具体的な法的判断は弁護士にご相談ください。</p>'
                    ),
                },
            )
            response.raise_for_status()
            logger.info("Report email sent: order_id=%s email=%s status_code=%s", order_id, email, response.status_code)
            posthog_capture(
                email or order_id,
                "report_email_sent",
                {"order_id": order_id, "language": language},
            )
            return True
    except Exception as e:
        logger.error("Report email failed: order_id=%s email=%s error=%s", order_id, email, e)
        posthog_capture(
            email or order_id,
            "report_email_failed",
            {"order_id": order_id, "language": language, "error": str(e)},
        )
        sentry_capture_exception(
            e,
            tags={"component": "email", "order_id": order_id, "language": language},
        )
        return False
