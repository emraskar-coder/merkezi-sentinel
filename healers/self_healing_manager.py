"""
Merkezi Sentinel — Otonom İyileştirme Yöneticisi (Self-Healing Manager)
Tespit edilen aksaklıklar için kayıtlı onarıcıları (healers) tetikler
ve kullanıcı müdahalesine gerek kalmadan sistemi kendi kendine düzeltir.
"""

import logging
from probes.base import ProbeResult, ProbeStatus
from healers.domain_healer import DomainHealer
from healers.draft_healer import DraftHealer

logger = logging.getLogger("SelfHealingManager")


class SelfHealingManager:
    def __init__(self):
        self.healers = [
            DomainHealer(),
            DraftHealer(),
        ]

    def heal_all(self, results: list[ProbeResult]) -> list[str]:
        """Tüm sonuçları tarar ve onarılabilecek olanları otonom çözer.
        Returns: list of healed action summaries.
        """
        healed_reports = []

        for r in results:
            if r.status in (ProbeStatus.CRITICAL, ProbeStatus.WARNING) and not r.auto_resolved:
                for healer in self.healers:
                    if healer.can_heal(r):
                        logger.info(f"🛠️ [Self-Healing] {r.project} için {healer.name} devrede...")
                        try:
                            success, action_summary = healer.heal(r)
                            if success:
                                msg = f"[{healer.name}] {r.project}: {action_summary}"
                                healed_reports.append(msg)
                                logger.info(f"✅ [Self-Healing Başarılı] {msg}")
                                break
                        except Exception as e:
                            logger.error(f"❌ [Self-Healing Hatası] {healer.name} onarımında hata: {e}")

        return healed_reports
