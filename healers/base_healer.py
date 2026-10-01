"""
Merkezi Sentinel — Otonom Onarıcı Taban Sınıfı (Base Healer)
Tespit edilen aksaklıkları otomatik olarak düzeltir (Self-Healing).
"""

from probes.base import ProbeResult


class BaseHealer:
    name: str = "BaseHealer"

    def can_heal(self, result: ProbeResult) -> bool:
        """Bu onarıcının ilgili sorunu çözüp çözemeyeceğini belirler."""
        raise NotImplementedError

    def heal(self, result: ProbeResult) -> tuple[bool, str]:
        """Sorunu otonom olarak çözer.
        Returns: (success: bool, action_summary: str)
        """
        raise NotImplementedError
