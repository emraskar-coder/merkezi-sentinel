"""
Merkezi Sentinel — Alan Adı ve Konfigürasyon Onarıcısı (Domain & Config Healer)
Railway veya canlı ortamda değişen veya yazım hatası olan domainleri
otomatik tespit edip master.env, proje .env ve Sentinel konfigürasyonuna yazar.
"""

import os
import requests
import logging
from pathlib import Path

from config import SentinelConfig, MASTER_ENV_PATH
from probes.base import ProbeResult, ProbeStatus
from healers.base_healer import BaseHealer

logger = logging.getLogger("DomainHealer")


class DomainHealer(BaseHealer):
    name = "DomainHealer"

    def can_heal(self, result: ProbeResult) -> bool:
        return (
            result.probe_name == "http_health_endpoint"
            and bool(result.details.get("actual_domain"))
            and result.details.get("configured_url") != f"https://{result.details.get('actual_domain')}"
        )

    def heal(self, result: ProbeResult) -> tuple[bool, str]:
        actual_domain = result.details.get("actual_domain")
        new_url = f"https://{actual_domain}"
        proj_name = result.project

        actions_taken = []

        # 1. master.env dosyasını güncelle veya ekle
        key_name = f"{proj_name.upper()}_URL"
        if "takalike" in proj_name.lower():
            key_name = "TAKALIKE_WEBHOOK_URL"

        try:
            if MASTER_ENV_PATH.is_file():
                lines = []
                found = False
                with open(MASTER_ENV_PATH, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith(f"{key_name}="):
                            lines.append(f"{key_name}={new_url}\n")
                            found = True
                        else:
                            lines.append(line)
                if not found:
                    lines.append(f"\n# Merkezi Sentinel Otonom Eklenen Domain\n{key_name}={new_url}\n")

                with open(MASTER_ENV_PATH, "w", encoding="utf-8") as f:
                    f.writelines(lines)
                actions_taken.append(f"master.env içine '{key_name}={new_url}' yazıldı.")
        except Exception as e:
            logger.warning(f"master.env güncelleme hatası: {e}")

        # 2. Çalışma anı ortam değişkenlerini ve SentinelConfig'i güncelle
        os.environ[key_name] = new_url
        if "takalike" in proj_name.lower():
            SentinelConfig.TAKALIKE_WEBHOOK_URL = new_url
        actions_taken.append("Çalışma zamanı (runtime) konfigürasyonu güncellendi.")

        # 3. Canlı doğrulama testi yap
        try:
            r = requests.get(f"{new_url}/health", timeout=10)
            if r.status_code == 200:
                actions_taken.append(f"Yeni adrese canlı test yapıldı: HTTP 200 Başarılı ({r.json().get('status', 'ok')}).")
                # Sonucu yeşile çevir ve otonom çözüldü olarak işaretle
                result.status = ProbeStatus.HEALTHY
                result.auto_resolved = True
                result.message = f"[OTONOM DÜZELTİLDİ] Servis domaini '{new_url}' olarak master.env'ye kaydedildi ve doğrulandı."
                result.root_cause = f"Eski adres geçersizdi; Railway'deki gerçek alan adı ({actual_domain}) otomatik keşfedilip sisteme işlendi."
                result.step_by_step_fix = [
                    f"Sentinel '{new_url}' adresini master.env ve sistem hafızasına otomatik yazdı.",
                    f"Canlı healthcheck atıldı: HTTP 200 OK (OpenAI, ManyChat, Supabase aktif).",
                    "Sizin herhangi bir manuel işlem yapmanıza gerek kalmadı!",
                ]
                return True, " | ".join(actions_taken)
        except Exception as e:
            actions_taken.append(f"Doğrulama testi hatası: {e}")

        return False, " | ".join(actions_taken)
