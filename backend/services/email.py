import logging

import httpx

from backend.config import get_settings

logger = logging.getLogger(__name__)


async def send_report_email(email: str, order_id: str, language: str) -> bool:
    """Send report link via Resend API."""
    settings = get_settings()

    if not settings.RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not set, skipping email send")
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

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
                json={
                    "from": "Contract Checker <noreply@contract-checker.com>",
                    "to": [email],
                    "subject": subject,
                    "html": (
                        f'<p><a href="{report_url}">{subject}</a></p>'
                        f'<p>This link expires in 24 hours.</p>'
                        f'<hr><p style="font-size:12px;color:#666;">'
                        f'本サービスは法律相談ではありません。具体的な法的判断は弁護士にご相談ください。</p>'
                    ),
                },
            )
            response.raise_for_status()
            logger.info(f"Report email sent to {email} for order {order_id}")
            return True
    except Exception as e:
        logger.error(f"Failed to send email to {email}: {e}")
        return False
