"""
Merkezi Sentinel — Taslak ve İletim Onarıcısı (Draft & Dispatch Healer)
Typefully'de rafta unutulmuş, daha önce SMTP engeli yüzünden maili gitmemiş
yetim taslakları tespit edip kullanıcıya tek-tık onay e-postası iletir (Self-Healing).
"""

import os
import requests
import logging
from config import SentinelConfig
from probes.base import ProbeResult, ProbeStatus
from healers.base_healer import BaseHealer
from alerts.gmail_sender import send_sentinel_alert

logger = logging.getLogger("DraftHealer")


class DraftHealer(BaseHealer):
    name = "DraftHealer"

    def can_heal(self, result: ProbeResult) -> bool:
        return (
            result.probe_name.startswith("orphan_draft_")
            and bool(result.details.get("draft_id"))
            and not result.auto_resolved
        )

    def heal(self, result: ProbeResult) -> tuple[bool, str]:
        draft_id = result.details.get("draft_id")
        social_set = result.details.get("social_set", "LinkedIn")
        url = result.details.get("url") or f"https://typefully.com/?d={draft_id}"

        # Typefully'den post metnini çek
        draft_text = "Takalike / LinkedIn Gönderisi"
        api_key = SentinelConfig.TYPEFULLY_API_KEY
        if api_key and draft_id:
            try:
                # Sosyal set ID'yi bul
                ss_id = result.probe_name.replace("orphan_draft_", "")
                r = requests.get(
                    f"https://api.typefully.com/v2/social-sets/{ss_id}/drafts",
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=10,
                )
                if r.status_code == 200:
                    for d in r.json().get("results", []):
                        if str(d.get("id")) == str(draft_id):
                            posts = d.get("platforms", {}).get("linkedin", {}).get("posts", [])
                            if posts:
                                draft_text = posts[0].get("text", draft_text)
                            break
            except Exception as e:
                logger.warning(f"Draft text fetch error: {e}")

        # Şık onay e-postası inşa et
        subject = f"[Otonom Kurtarma - Onay Bekliyor] {social_set} LinkedIn Taslağı (ID: {draft_id})"
        html_content = f"""
        <div style="font-family: -apple-system, sans-serif; background: #0f172a; color: #f8fafc; padding: 24px; border-radius: 12px; max-width: 600px; margin: 0 auto; border: 1px solid #334155;">
            <div style="font-size: 18px; font-weight: 800; color: #38bdf8; margin-bottom: 8px;">🛡️ Merkezi Sentinel — Otonom Kurtarma</div>
            <div style="font-size: 13px; color: #94a3b8; margin-bottom: 18px;">
                Bu içerik Typefully üzerinde hazırdı ancak önceki SMTP port engeli nedeniyle onay maili size ulaşamamıştı. Sentinel bunu rafta tespit etti ve doğrudan onayınıza sundu.
            </div>

            <div style="background: #1e293b; border-left: 4px solid #3b82f6; padding: 16px; border-radius: 6px; font-size: 14px; line-height: 1.6; color: #e2e8f0; margin-bottom: 20px; white-space: pre-wrap;">
{draft_text}
            </div>

            <div style="display: flex; gap: 12px; margin-top: 20px;">
                <a href="{url}" style="background: #2563eb; color: #ffffff; text-decoration: none; padding: 12px 24px; border-radius: 8px; font-weight: 700; font-size: 14px; display: inline-block;">
                    🚀 Typefully'de Aç ve Yayınla
                </a>
            </div>
            <div style="font-size: 11px; color: #64748b; margin-top: 20px;">
                Merkezi Sentinel Otonom İyileştirme Motoru (Self-Healing)
            </div>
        </div>
        """

        plain_text = f"Sentinel Otonom Kurtarma: {social_set} taslağı onay bekliyor.\nTaslağı Aç: {url}\n\nİçerik:\n{draft_text}"

        try:
            ok = send_sentinel_alert(subject, html_content, plain_text)
            if ok:
                result.status = ProbeStatus.HEALTHY
                result.auto_resolved = True
                result.message = f"[OTONOM KURTARILDI] {social_set} için onay e-postası doğrudan gelen kutunuza iletildi (ID: {draft_id})."
                result.step_by_step_fix = [
                    "Sentinel taslağı Typefully'de buldu ve onay e-postasını gelen kutunuza otomatik fırlattı.",
                    "Gelen e-postadaki 'Typefully'de Aç ve Yayınla' butonuna tıklayarak tek tıkla yayını başlatabilirsiniz.",
                    "Sizin sistemi aramanıza veya konsol açmanıza gerek kalmadı!",
                ]
                return True, f"Onay e-postası başarıyla iletildi (ID: {draft_id})"
        except Exception as e:
            return False, f"E-posta gönderim hatası: {e}"

        return False, "Gönderilemedi"
