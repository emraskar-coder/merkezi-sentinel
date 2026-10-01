"""
Merkezi Sentinel — Probe Taban Sınıfı ve Zengin Teşhis Modelleri
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class ProbeStatus(str, Enum):
    HEALTHY = "HEALTHY"      # Her şey yolunda (Yeşil)
    WARNING = "WARNING"      # Dikkat gerektiren durum (Sarı)
    CRITICAL = "CRITICAL"    # Kritik arıza / aksama (Kırmızı)
    SKIPPED = "SKIPPED"      # Kapsam dışı veya pasif (Gri)


@dataclass
class ProbeResult:
    project: str
    probe_name: str
    status: ProbeStatus
    message: str
    root_cause: str = ""                       # Kök neden analizi
    step_by_step_fix: list[str] = field(default_factory=list)  # Adım adım somut çözüm reçetesi
    suggested_action: str = ""                 # Hızlı özet eylem
    auto_resolved: bool = False                # Sistemin kendi kendine düzelttiği durumlar
    details: dict = field(default_factory=dict)
    timestamp_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "project": self.project,
            "probe_name": self.probe_name,
            "status": self.status.value,
            "message": self.message,
            "root_cause": self.root_cause,
            "step_by_step_fix": self.step_by_step_fix,
            "suggested_action": self.suggested_action,
            "auto_resolved": self.auto_resolved,
            "details": self.details,
            "timestamp_utc": self.timestamp_utc,
        }


class BaseProbe:
    name: str = "BaseProbe"

    def run(self, project) -> list[ProbeResult]:
        raise NotImplementedError
