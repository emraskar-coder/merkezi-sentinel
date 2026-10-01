"""
Merkezi Sentinel — Evrensel Kalp Atışı ve Teslimat SDK'sı (Universal Heartbeat SDK)
Tüm projeler (mevcut ve gelecekteki) tek satırla kalp atışı atabilir ve çıktı bildirebilir.
Asla ev sahibi projeyi kilitlemez veya çökertmez (zero-risk non-blocking).

Kullanım:
    from heartbeat import ping, report_deliverable, report_error

    # Görev başlangıcında veya periyodik:
    ping("LinkedIn_Text_Paylasim", status="running", message="İçerik üretimi başladı")

    # Çıktı üretildiğinde (Örn: Typefully taslağı, email, video vb.):
    report_deliverable("LinkedIn_Text_Paylasim", "typefully_draft", "11020892", details={"status": "draft"})

    # Beklenmeyen bir hata yakalandığında:
    report_error("Takalike_Chat_Asistani", "Meta Webhook 500 error", details={"trace": ...})
"""

import os
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("SentinelSDK")

# Sentinel storage dosyasını otomatik tespit et
_CURRENT_DIR = Path(__file__).resolve().parent
_WORKSPACE_DIR = _CURRENT_DIR.parent.parent.parent
_STATE_FILE = _CURRENT_DIR.parent / "storage" / "sentinel_state.json"


def _safe_update_state(modifier_fn):
    """State dosyasını güvenle kilit ve istisna yakalama ile günceller."""
    try:
        data = {}
        _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        if _STATE_FILE.is_file():
            try:
                with open(_STATE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}

        modifier_fn(data)

        with open(_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.debug(f"Sentinel SDK state yazma hatası (yoksayıldı): {e}")


def ping(project: str, status: str = "ok", message: str = "", metadata: dict | None = None) -> bool:
    """Projeden canlılık sinyali gönderir."""
    now_iso = datetime.now(timezone.utc).isoformat()

    def update(data):
        projects = data.setdefault("projects", {})
        projects[project] = {
            "last_heartbeat_utc": now_iso,
            "status": status,
            "message": message,
            "metadata": metadata or {},
        }

    _safe_update_state(update)
    return True


def report_deliverable(project: str, deliverable_type: str, identifier: str = "", details: dict | None = None) -> bool:
    """Projenin beklenen bir iş çıktısını tamamladığını kaydeder."""
    now_iso = datetime.now(timezone.utc).isoformat()

    def update(data):
        delivs = data.setdefault("deliverables", {})
        delivs[project] = {
            "last_deliverable_utc": now_iso,
            "type": deliverable_type,
            "identifier": identifier,
            "details": details or {},
        }

    _safe_update_state(update)
    return True


def report_error(project: str, error_message: str, details: dict | None = None) -> bool:
    """Projede oluşan bir arızayı doğrudan Sentinel hafızasına yazar."""
    now_iso = datetime.now(timezone.utc).isoformat()

    def update(data):
        projects = data.setdefault("projects", {})
        projects[project] = {
            "last_heartbeat_utc": now_iso,
            "status": "error",
            "message": error_message,
            "metadata": details or {},
        }

    _safe_update_state(update)
    return True
