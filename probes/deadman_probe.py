"""
Merkezi Sentinel — Sessiz Ölüm Bekçisi (Dead Man's Snitch / Cadence Checker)
Belirli periyotlarla (örneğin her gün sabah 08:00) çalışması gereken görevlerin
hata fırlatmadan sessizce atlayıp atlamadığını (Silent Death) denetler.
"""

import logging
from datetime import datetime, timezone, timedelta
from probes.base import BaseProbe, ProbeResult, ProbeStatus

logger = logging.getLogger("DeadmanProbe")


class DeadmanProbe(BaseProbe):
    name = "DeadmanProbe"

    def __init__(self, state_manager):
        self.state = state_manager

    def run(self, project) -> list[ProbeResult]:
        results = []
        if project.project_type != "CRON_PIPELINE":
            return results

        p_name = project.name
        proj_state = self.state.get_project_state(p_name)
        last_heartbeat_utc = proj_state.get("last_heartbeat_utc")

        # Teslimat (deliverable) kaydını da kontrol et
        deliverables = self.state.get_all_states().get("deliverables", {})
        last_deliv_utc = deliverables.get(p_name, {}).get("last_deliverable_utc")

        # En yeni sinyali seç
        latest_signal_str = last_heartbeat_utc or last_deliv_utc

        now = datetime.now(timezone.utc)

        # Cron programına göre beklenen maksimum aralık belirle
        schedule = (project.cron_schedule or "").lower()
        if "1-5" in schedule or "every day" in schedule or "* * *" in schedule:
            max_allowed_hours = 30  # Günlük işler için 30 saat (24h + 6h pay)
        elif "1" in schedule or "weekly" in schedule:
            max_allowed_hours = 8 * 24  # Haftalık işler için 8 gün
        else:
            max_allowed_hours = 36  # Varsayılan

        if latest_signal_str:
            try:
                latest_dt = datetime.fromisoformat(latest_signal_str.replace("Z", "+00:00"))
                elapsed_hours = (now - latest_dt).total_seconds() / 3600.0

                if elapsed_hours > max_allowed_hours:
                    results.append(ProbeResult(
                        project=p_name,
                        probe_name="deadman_cadence",
                        status=ProbeStatus.CRITICAL,
                        message=f"Sessiz Ölüm Tespiti! Servisten {elapsed_hours:.1f} saattir hiçbir sinyal veya çıktı alınamadı (Beklenen azami: {max_allowed_hours} saat).",
                        details={"last_signal": latest_signal_str, "elapsed_hours": elapsed_hours},
                        suggested_action=f"Railway üzerinde {p_name} servisini veya yerel cron zamanlayıcısını tetikleyin.",
                    ))
                else:
                    results.append(ProbeResult(
                        project=p_name,
                        probe_name="deadman_cadence",
                        status=ProbeStatus.HEALTHY,
                        message=f"Ritim sağlıklı: Son sinyal {elapsed_hours:.1f} saat önce alındı.",
                        details={"last_signal": latest_signal_str},
                    ))
            except Exception as e:
                logger.warning(f"Deadman date parsing error for {p_name}: {e}")
        else:
            # Henüz hiç sinyal kaydedilmemiş yeni servis
            results.append(ProbeResult(
                project=p_name,
                probe_name="deadman_cadence",
                status=ProbeStatus.HEALTHY,
                message="Yeni keşfedilen servis; ilk çalışma bekleniyor.",
            ))

        return results
