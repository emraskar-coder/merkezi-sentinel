"""
Merkezi Sentinel — Ana Orkestrasyon ve Çalıştırıcı (Runner)
Tüm ekosistemi tarar, denetim katmanlarını yürütür, alarmları üretir ve paneli besler.

Kullanım:
    python runner.py                 # Tek seferlik denetim ve konsol raporu
    python runner.py --alert         # Denetim yap, arıza varsa doğrudan Gmail ile bildir
    python runner.py --force-mail    # Her şey yeşil olsa bile özet e-postası ilet
    python runner.py --daemon        # Belirli aralıklarla (60 dk) sürekli arka planda çalış
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
import time
import json
import logging
import argparse
from datetime import datetime, timezone
from pathlib import Path

# Yerel modül yolunu ekle
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from config import SentinelConfig
from registry import ProjectRegistry
from storage.state_manager import StateManager
from probes.deliverable_probe import DeliverableProbe
from probes.webhook_probe import WebhookProbe
from probes.deadman_probe import DeadmanProbe
from probes.integration_probe import IntegrationProbe
from probes.base import ProbeResult, ProbeStatus
from alerts.formatter import build_html_report, print_cli_summary
from healers.self_healing_manager import SelfHealingManager
from alerts.gmail_sender import send_sentinel_alert

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("SentinelRunner")


class SentinelRunner:
    def __init__(self):
        self.config = SentinelConfig()
        self.state = StateManager()
        self.registry = ProjectRegistry()
        self.deliverable_probe = DeliverableProbe()
        self.webhook_probe = WebhookProbe()
        self.deadman_probe = DeadmanProbe(self.state)
        self.integration_probe = IntegrationProbe()
        self.healer = SelfHealingManager()

    def run_full_scan(self, send_mail_on_alert: bool = False, force_mail: bool = False) -> list[ProbeResult]:
        """Tüm ekosistem için tam kapsamlı otonom denetim koşar."""
        logger.info("🛡️ Sentinel tam ekosistem denetimi başlatılıyor...")
        all_results: list[ProbeResult] = []

        # 1. Genel Entegrasyon ve API Anahtarları Denetimi
        logger.info("Katman 1: Merkezi API ve Token kontrolleri yapılıyor...")
        fleet_integration_results = self.integration_probe.run_fleet_checks()
        all_results.extend(fleet_integration_results)

        # 2. Otomatik Proje Keşfi
        logger.info("Katman 2: Projeler dizini taranıyor (Auto-Discovery)...")
        projects = self.registry.scan()
        fleet_count = len(projects)

        # 3. Proje Bazlı Denetimler
        logger.info(f"Katman 3: {fleet_count} proje üzerinde çıktı ve canlılık denetimleri yapılıyor...")
        for name, proj in projects.items():
            if proj.status == "paused" or proj.project_type == "SHARED_LIB":
                continue

            # Çıktı / Teslimat Denetimi
            deliv_res = self.deliverable_probe.run(proj)
            all_results.extend(deliv_res)

            # Webhook & Canlılık Denetimi
            webhook_res = self.webhook_probe.run(proj)
            all_results.extend(webhook_res)

            # Sessiz Ölüm / Ritim Denetimi
            deadman_res = self.deadman_probe.run(proj)
            all_results.extend(deadman_res)

        # 4. Otonom İyileştirme (Self-Healing Motoru)
        logger.info("Katman 4: Otonom İyileştirme (Self-Healing) kontrolleri yapılıyor...")
        healed_actions = self.healer.heal_all(all_results)
        if healed_actions:
            logger.info(f"✨ {len(healed_actions)} aksaklık kullanıcıya yük olmadan kendi kendine düzeltildi!")

        # 5. State ve Dashboard Güncellemesi
        self._update_dashboard_state(all_results, projects)

        # 6. Konsol Çıktısı
        print_cli_summary(all_results, fleet_count)

        # 7. Akıllı Alarm ve E-Posta İletimi
        criticals = [r for r in all_results if r.status == ProbeStatus.CRITICAL]
        warnings = [r for r in all_results if r.status == ProbeStatus.WARNING and not r.auto_resolved]

        should_send = force_mail
        if criticals and send_mail_on_alert:
            # Alarm dedup kontrolü (3 saat cooldown)
            for c in criticals:
                alert_key = f"{c.project}:{c.probe_name}"
                if self.state.should_alert(alert_key, cooldown_hours=3.0):
                    should_send = True
                    self.state.mark_alerted(alert_key)

        if should_send:
            subject, html_body, plain_body = build_html_report(all_results, fleet_count)
            logger.info(f"E-Posta gönderiliyor: {subject}")
            success = send_sentinel_alert(
                subject=subject,
                html_content=html_body,
                plain_fallback=plain_body,
            )
            if success:
                logger.info("✅ Alarm/rapor e-postası başarıyla iletildi.")
            else:
                logger.warning("❌ E-Posta gönderimi başarısız oldu.")

        return all_results

    def _update_dashboard_state(self, results: list[ProbeResult], projects: dict):
        """Dashboard'un okuyacağı state.json dosyasını yazar."""
        dashboard_dir = CURRENT_DIR / "dashboard"
        dashboard_dir.mkdir(parents=True, exist_ok=True)
        state_file = dashboard_dir / "dashboard_state.json"

        payload = {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "fleet_total": len(projects),
            "results": [r.to_dict() for r in results],
            "projects": {k: v.to_dict() for k, v in projects.items()},
            "critical_count": sum(1 for r in results if r.status == ProbeStatus.CRITICAL),
            "warning_count": sum(1 for r in results if r.status == ProbeStatus.WARNING),
            "healthy_count": sum(1 for r in results if r.status == ProbeStatus.HEALTHY),
        }

        try:
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Dashboard state kaydedilemedi: {e}")


def main():
    parser = argparse.ArgumentParser(description="Merkezi Sentinel — Ekosistem Canlılık Nöbetçisi")
    parser.add_argument("--alert", action="store_true", help="Sorun tespit edilirse doğrudan Gmail ile alarm gönder")
    parser.add_argument("--force-mail", action="store_true", help="Her durumda durum raporu maili gönder")
    parser.add_argument("--daemon", action="store_true", help="Sürekli döngüde çalış (her saat başı)")
    parser.add_argument("--interval", type=int, default=180, help="Daemon döngü aralığı (dakika, varsayılan 180 - 3 saat)")

    args = parser.parse_args()
    runner = SentinelRunner()

    if args.daemon:
        logger.info(f"Sentinel DAEMON modunda başlatıldı (Aralık: {args.interval} dakika)")
        while True:
            try:
                runner.run_full_scan(send_mail_on_alert=True, force_mail=False)
            except Exception as e:
                logger.error(f"Döngü hatası: {e}")
            time.sleep(args.interval * 60)
    else:
        runner.run_full_scan(send_mail_on_alert=args.alert, force_mail=args.force_mail)


if __name__ == "__main__":
    main()
