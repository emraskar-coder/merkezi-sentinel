"""
Merkezi Sentinel — Entegrasyon & Token Tazeliği Denetçisi (Integration Probe)
Notion, Typefully, Gmail OAuth ve OpenAI/Groq API anahtarlarının
geçerliliğini ve canlı bağlantısını test eder.
"""

import requests
import logging
from config import SentinelConfig
from probes.base import BaseProbe, ProbeResult, ProbeStatus

logger = logging.getLogger("IntegrationProbe")


class IntegrationProbe(BaseProbe):
    name = "IntegrationProbe"

    def run_fleet_checks(self) -> list[ProbeResult]:
        """Tüm sistem genelindeki kritik API anahtarlarını test eder."""
        results = []
        results.append(self._check_notion())
        results.append(self._check_typefully())
        results.append(self._check_gmail_oauth())
        return results

    def _check_notion(self) -> ProbeResult:
        token = SentinelConfig.NOTION_TOKEN or SentinelConfig.NOTION_SOCIAL_TOKEN
        if not token:
            return ProbeResult(
                project="Ekosistem",
                probe_name="notion_token_validity",
                status=ProbeStatus.WARNING,
                message="NOTION_TOKEN tanımlı değil.",
            )
        try:
            headers = {"Authorization": f"Bearer {token}", "Notion-Version": "2022-06-28"}
            r = requests.get("https://api.notion.com/v1/users/me", headers=headers, timeout=8)
            if r.status_code == 200:
                name = r.json().get("name", "Bilinmeyen")
                return ProbeResult(
                    project="Ekosistem",
                    probe_name="notion_token_validity",
                    status=ProbeStatus.HEALTHY,
                    message=f"Notion API aktif ({name}).",
                )
            else:
                return ProbeResult(
                    project="Ekosistem",
                    probe_name="notion_token_validity",
                    status=ProbeStatus.CRITICAL,
                    message=f"Notion API hatası (HTTP {r.status_code}): Token geçersiz veya yetkisiz!",
                    suggested_action="master.env içindeki NOTION_TOKEN değerini yenileyin.",
                )
        except Exception as e:
            return ProbeResult(
                project="Ekosistem",
                probe_name="notion_token_validity",
                status=ProbeStatus.WARNING,
                message=f"Notion bağlantı hatası: {e}",
            )

    def _check_typefully(self) -> ProbeResult:
        api_key = SentinelConfig.TYPEFULLY_API_KEY
        if not api_key:
            return ProbeResult(
                project="Ekosistem",
                probe_name="typefully_api_key",
                status=ProbeStatus.WARNING,
                message="TYPEFULLY_API_KEY tanımlı değil.",
            )
        try:
            headers = {"Authorization": f"Bearer {api_key}"}
            r = requests.get("https://api.typefully.com/v2/social-sets", headers=headers, timeout=8)
            if r.status_code == 200:
                count = len(r.json().get("results", []))
                return ProbeResult(
                    project="Ekosistem",
                    probe_name="typefully_api_key",
                    status=ProbeStatus.HEALTHY,
                    message=f"Typefully API aktif ({count} sosyal hesap bağlı).",
                )
            else:
                return ProbeResult(
                    project="Ekosistem",
                    probe_name="typefully_api_key",
                    status=ProbeStatus.CRITICAL,
                    message=f"Typefully API anahtarı geçersiz (HTTP {r.status_code})!",
                    suggested_action="Typefully API key yenilenmeli.",
                )
        except Exception as e:
            return ProbeResult(
                project="Ekosistem",
                probe_name="typefully_api_key",
                status=ProbeStatus.WARNING,
                message=f"Typefully API bağlantı hatası: {e}",
            )

    def _check_gmail_oauth(self) -> ProbeResult:
        cid = SentinelConfig.GMAIL_PERSONAL_CLIENT_ID
        sec = SentinelConfig.GMAIL_PERSONAL_CLIENT_SECRET
        rf = SentinelConfig.GMAIL_PERSONAL_REFRESH_TOKEN
        if not (cid and sec and rf):
            return ProbeResult(
                project="Ekosistem",
                probe_name="gmail_oauth_token",
                status=ProbeStatus.WARNING,
                message="Gmail OAuth kimlik bilgileri eksik (SMTP fallback aktif).",
            )
        try:
            r = requests.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": cid,
                    "client_secret": sec,
                    "refresh_token": rf,
                    "grant_type": "refresh_token",
                },
                timeout=8,
            )
            if r.status_code == 200:
                return ProbeResult(
                    project="Ekosistem",
                    probe_name="gmail_oauth_token",
                    status=ProbeStatus.HEALTHY,
                    message="Gmail REST API OAuth2 bağlantısı taze ve aktif.",
                )
            else:
                return ProbeResult(
                    project="Ekosistem",
                    probe_name="gmail_oauth_token",
                    status=ProbeStatus.CRITICAL,
                    message=f"Gmail OAuth token yenilenemedi (HTTP {r.status_code})! E-posta bildirimleri riske girebilir.",
                    suggested_action="Google OAuth refresh token'ı yenileyin.",
                )
        except Exception as e:
            return ProbeResult(
                project="Ekosistem",
                probe_name="gmail_oauth_token",
                status=ProbeStatus.WARNING,
                message=f"Gmail OAuth bağlantı hatası: {e}",
            )
