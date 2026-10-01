"""
Merkezi Sentinel — State & Hafıza Yöneticisi
Son kontrolleri, kalp atışlarını ve alarm tekrarlarını (dedup) yönetir.
"""

import json
import sqlite3
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from config import SentinelConfig

logger = logging.getLogger("SentinelState")


class StateManager:
    def __init__(self, state_file: Path | None = None, db_file: Path | None = None):
        self.state_file = state_file or SentinelConfig.STATE_FILE
        self.db_file = db_file or SentinelConfig.SQLITE_DB
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self._init_sqlite()
        self._data = self._load()

    def _init_sqlite(self):
        """Hafif SQLite veritabanı (tarihsel log ve telemetri için)."""
        try:
            with sqlite3.connect(self.db_file) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS probe_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project TEXT NOT NULL,
                        probe_type TEXT NOT NULL,
                        status TEXT NOT NULL,
                        message TEXT,
                        timestamp TEXT NOT NULL
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS deliverables (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project TEXT NOT NULL,
                        deliverable_type TEXT NOT NULL,
                        identifier TEXT,
                        details TEXT,
                        timestamp TEXT NOT NULL
                    )
                """)
        except Exception as e:
            logger.warning(f"SQLite başlatma hatası: {e}")

    def _load(self) -> dict:
        if self.state_file.is_file():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "projects": {},
            "deliverables": {},
            "recent_alerts": {},
            "last_scan_utc": None,
        }

    def save(self):
        try:
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"State dosyası kaydedilemedi: {e}")

    # ── Kalp Atışı (Heartbeat) Kaydı ──────────────────────────
    def record_heartbeat(self, project: str, status: str = "ok", message: str = "", metadata: dict | None = None):
        now_iso = datetime.now(timezone.utc).isoformat()
        if "projects" not in self._data:
            self._data["projects"] = {}
        self._data["projects"][project] = {
            "last_heartbeat_utc": now_iso,
            "status": status,
            "message": message,
            "metadata": metadata or {},
        }
        self.save()

        # SQLite log
        try:
            with sqlite3.connect(self.db_file) as conn:
                conn.execute(
                    "INSERT INTO probe_history (project, probe_type, status, message, timestamp) VALUES (?, ?, ?, ?, ?)",
                    (project, "heartbeat", status, message, now_iso),
                )
        except Exception:
            pass

    # ── Çıktı / Teslimat (Deliverable) Kaydı ───────────────────
    def record_deliverable(self, project: str, deliverable_type: str, identifier: str, details: dict | None = None):
        now_iso = datetime.now(timezone.utc).isoformat()
        if "deliverables" not in self._data:
            self._data["deliverables"] = {}
        self._data["deliverables"][project] = {
            "last_deliverable_utc": now_iso,
            "type": deliverable_type,
            "identifier": identifier,
            "details": details or {},
        }
        self.save()

        try:
            with sqlite3.connect(self.db_file) as conn:
                conn.execute(
                    "INSERT INTO deliverables (project, deliverable_type, identifier, details, timestamp) VALUES (?, ?, ?, ?, ?)",
                    (project, deliverable_type, identifier, json.dumps(details or {}), now_iso),
                )
        except Exception:
            pass

    # ── Tekrar Alarm Freni (Alert Cooldown) ────────────────────
    def should_alert(self, alert_key: str, cooldown_hours: float = 3.0) -> bool:
        """Aynı alarmın tekrar tekrar spam olarak gitmesini engeller."""
        now = datetime.now(timezone.utc)
        recent = self._data.setdefault("recent_alerts", {})
        last_str = recent.get(alert_key)
        if not last_str:
            return True
        try:
            last_dt = datetime.fromisoformat(last_str)
            if (now - last_dt) > timedelta(hours=cooldown_hours):
                return True
            return False
        except Exception:
            return True

    def mark_alerted(self, alert_key: str):
        self._data.setdefault("recent_alerts", {})[alert_key] = datetime.now(timezone.utc).isoformat()
        self.save()

    def get_project_state(self, project: str) -> dict:
        return self._data.get("projects", {}).get(project, {})

    def get_all_states(self) -> dict:
        return self._data
