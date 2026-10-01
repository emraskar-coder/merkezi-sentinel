"""
Merkezi Sentinel — Konfigürasyon Modülü
Tüm ekosistem projelerinin sağlık, canlılık ve çıktı denetim ayarları.
"""

import os
from pathlib import Path

# Kök dizinler
CURRENT_DIR = Path(__file__).resolve().parent
PROJECTS_DIR = CURRENT_DIR.parent
WORKSPACE_DIR = PROJECTS_DIR.parent
MASTER_ENV_PATH = WORKSPACE_DIR / "_knowledge" / "credentials" / "master.env"


def _load_env_fallback():
    """Lokal çalışma anında master.env dosyasını os.environ'a yükler."""
    if MASTER_ENV_PATH.is_file():
        try:
            with open(MASTER_ENV_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip()
                        if k and k not in os.environ:
                            os.environ[k] = v
        except Exception:
            pass


_load_env_fallback()


class SentinelConfig:
    # ── Temel Yollar ──────────────────────────────────────────
    DIR_PROJECTS = PROJECTS_DIR
    DIR_STORAGE = CURRENT_DIR / "storage"
    STATE_FILE = DIR_STORAGE / "sentinel_state.json"
    SQLITE_DB = DIR_STORAGE / "sentinel.db"

    # ── Bildirim Ayarları ────────────────────────────────────
    ALERT_EMAIL = os.environ.get("ALERT_EMAIL", "emraskar@gmail.com")
    ALERT_CC = os.environ.get("ALERT_CC", "e.askar@solidogrup.com")
    SENDER_EMAIL = os.environ.get("GMAIL_PERSONAL_EMAIL", "emraskar@gmail.com")

    # Google / Gmail API OAuth2 (HTTPS 443 — SMTP engeli tanımaz)
    GOOGLE_PERSONAL_TOKEN_JSON = os.environ.get("GOOGLE_PERSONAL_TOKEN_JSON", "")
    GMAIL_PERSONAL_CLIENT_ID = os.environ.get("GMAIL_PERSONAL_CLIENT_ID", "")
    GMAIL_PERSONAL_CLIENT_SECRET = os.environ.get("GMAIL_PERSONAL_CLIENT_SECRET", "")
    GMAIL_PERSONAL_REFRESH_TOKEN = os.environ.get("GMAIL_PERSONAL_REFRESH_TOKEN", "")

    # Gmail SMTP Fallback
    GMAIL_PERSONAL_APP_PASSWORD = os.environ.get("GMAIL_PERSONAL_APP_PASSWORD", "")

    # ── Entegrasyon API Anahtarları ──────────────────────────
    TYPEFULLY_API_KEY = os.environ.get("TYPEFULLY_API_KEY", "")
    TYPEFULLY_SOCIAL_SET_ID = os.environ.get("TYPEFULLY_SOCIAL_SET_ID", "334863")
    TYPEFULLY_SOCIAL_SET_ID_SOLIDO = os.environ.get("TYPEFULLY_SOCIAL_SET_ID_SOLIDO", "335331")
    TYPEFULLY_SOCIAL_SET_ID_TAKALIKE = os.environ.get("TYPEFULLY_SOCIAL_SET_ID_TAKALIKE", "335616")

    TAKALIKE_MANYCHAT_TOKEN = os.environ.get("TAKALIKE_MANYCHAT_TOKEN") or os.environ.get("MANYCHAT_API_TOKEN", "")
    TAKALIKE_WEBHOOK_URL = os.environ.get(
        "TAKALIKE_WEBHOOK_URL",
        "https://takalike-chat-asistani-production.up.railway.app"
    )

    NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
    NOTION_SOCIAL_TOKEN = os.environ.get("NOTION_SOCIAL_TOKEN", "")
    RAILWAY_TOKEN = os.environ.get("RAILWAY_TOKEN", "")

    # ── Eşik Değerleri (Toleranslar) ──────────────────────────
    # Cron sessiz ölüm toleransı: Beklenen saatten N dakika sonra sinyal gelmediyse alarm
    CRON_TOLERANCE_MINUTES = 60
    # Typefully'de bekleyen taslak alarm süresi: N saatten uzun süredir onaysız/unutulmuş taslaklar
    TYPEFULLY_ORPHAN_DRAFT_HOURS = 12
    # Webhook probe zaman aşımı (saniye)
    HTTP_PROBE_TIMEOUT = 10
