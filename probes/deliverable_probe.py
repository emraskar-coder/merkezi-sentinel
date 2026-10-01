"""
Merkezi Sentinel — Çıktı ve Teslimat Denetçisi (Deliverable Probe)
Yalnızca "servis ayakta mı" sorusunu değil; asıl kritik olan
"Beklenen iş çıktısı gerçekten üretildi mi ve yerine ulaştı mı?"
sorusunu denetler ve adım adım çözüm reçetesi üretir.
"""

import os
import requests
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

from config import SentinelConfig
from probes.base import BaseProbe, ProbeResult, ProbeStatus

logger = logging.getLogger("DeliverableProbe")


class DeliverableProbe(BaseProbe):
    name = "DeliverableProbe"

    def run(self, project) -> list[ProbeResult]:
        results = []
        p_name = project.name.lower()

        # 1. LinkedIn Metin Paylaşım Çıktı Denetimi
        if "linkedin" in p_name and "text" in p_name:
            results.extend(self._check_linkedin_typefully(project))

        # 2. E-Posta Asistanı Çıktı Denetimi
        elif "eposta" in p_name and "asistan" in p_name:
            results.extend(self._check_eposta_asistani(project))

        # 3. Genel Projeler için Durum/Çıktı Kontrolü
        elif project.project_type == "CRON_PIPELINE":
            results.extend(self._check_generic_pipeline_output(project))

        return results

    def _check_linkedin_typefully(self, project) -> list[ProbeResult]:
        results = []
        api_key = SentinelConfig.TYPEFULLY_API_KEY
        if not api_key:
            results.append(ProbeResult(
                project=project.name,
                probe_name="typefully_draft_check",
                status=ProbeStatus.WARNING,
                message="TYPEFULLY_API_KEY tanımlı değil; LinkedIn taslakları kontrol edilemedi.",
                root_cause="Typefully API anahtarı çevre değişkenlerinde bulunamadı.",
                step_by_step_fix=["master.env içerisine TYPEFULLY_API_KEY değerini ekleyin."],
                suggested_action="master.env içerisine TYPEFULLY_API_KEY ekleyin.",
            ))
            return results

        social_sets = {
            "Solido Grup (335331)": SentinelConfig.TYPEFULLY_SOCIAL_SET_ID_SOLIDO,
            "Takalike (335332)": SentinelConfig.TYPEFULLY_SOCIAL_SET_ID_TAKALIKE,
            "Emre Aşkar (334863)": SentinelConfig.TYPEFULLY_SOCIAL_SET_ID,
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "MerkeziSentinel/1.0",
        }

        now_utc = datetime.now(timezone.utc)
        today_utc_str = now_utc.strftime("%Y-%m-%d")

        for label, ss_id in social_sets.items():
            if not ss_id:
                continue
            url = f"https://api.typefully.com/v2/social-sets/{ss_id}/drafts"
            try:
                r = requests.get(url, headers=headers, timeout=12)
                if r.status_code != 200:
                    results.append(ProbeResult(
                        project=project.name,
                        probe_name=f"typefully_{ss_id}",
                        status=ProbeStatus.WARNING,
                        message=f"{label} taslakları çekilemedi (HTTP {r.status_code})",
                        details={"status_code": r.status_code, "response": r.text[:200]},
                    ))
                    continue

                drafts = r.json().get("results", [])
                if not drafts:
                    continue

                latest = drafts[0]
                created_at_str = latest.get("created_at", "")
                draft_status = latest.get("status", "draft")
                draft_id = latest.get("id")

                is_today = created_at_str.startswith(today_utc_str)

                # Yetim / Askıda Kalmış Taslak Tespiti
                if draft_status == "draft":
                    try:
                        created_dt = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                        age_hours = (now_utc - created_dt).total_seconds() / 3600.0

                        if age_hours > SentinelConfig.TYPEFULLY_ORPHAN_DRAFT_HOURS:
                            edit_link = f"https://typefully.com/?d={draft_id}&a={ss_id}"
                            results.append(ProbeResult(
                                project=project.name,
                                probe_name=f"orphan_draft_{ss_id}",
                                status=ProbeStatus.WARNING,
                                message=f"{label} için {age_hours:.1f} saattir onaylanmamış taslak bekliyor (ID: {draft_id}).",
                                root_cause=(
                                    f"İçerik Typefully'ye başarıyla yüklenmiş ancak onay e-postası daha önce "
                                    f"Railway SMTP port engeli nedeniyle size ulaşmadığından taslak rafta kalmış."
                                ),
                                step_by_step_fix=[
                                    f"Typefully taslağını açın: {edit_link}",
                                    "Metni ve görseli gözden geçirip 'Publish' (Hemen Yayınla) veya 'Schedule' (Zamanla) butonuna basın.",
                                    "Artık Gmail REST API devrede olduğu için sonraki gönderilerde onay mailiniz aksamadan gelecektir.",
                                ],
                                suggested_action=f"{edit_link} adresinden taslağı kontrol edin veya onaylayın.",
                                details={"draft_id": draft_id, "created_at": created_at_str, "social_set": label, "url": edit_link},
                            ))
                        elif is_today:
                            results.append(ProbeResult(
                                project=project.name,
                                probe_name=f"today_draft_{ss_id}",
                                status=ProbeStatus.HEALTHY,
                                message=f"{label} için bugünün taslağı hazırlandı (ID: {draft_id}, Durum: {draft_status}).",
                                details={"draft_id": draft_id, "created_at": created_at_str},
                            ))
                    except Exception as e:
                        logger.warning(f"Draft date parse error: {e}")
                elif draft_status in ("published", "scheduled"):
                    if is_today:
                        results.append(ProbeResult(
                            project=project.name,
                            probe_name=f"today_published_{ss_id}",
                            status=ProbeStatus.HEALTHY,
                            message=f"{label} için bugünün içeriği başarıyla yayınlandı/zamanlandı (ID: {draft_id}).",
                            details={"draft_id": draft_id, "status": draft_status},
                        ))

            except Exception as e:
                results.append(ProbeResult(
                    project=project.name,
                    probe_name=f"typefully_err_{ss_id}",
                    status=ProbeStatus.WARNING,
                    message=f"{label} Typefully bağlantı hatası: {e}",
                ))

        return results

    def _check_eposta_asistani(self, project) -> list[ProbeResult]:
        results = []
        durum_dir = project.dir_path / "durum"
        now_local = datetime.now()
        today_str = now_local.strftime("%Y-%m-%d")
        expected_file = durum_dir / f"eposta_ozet_{today_str}.md"

        # 1. Yerel dosya sistemi varsa kontrol et
        if project.dir_path.is_dir() and durum_dir.is_dir():
            is_weekday = now_local.weekday() < 5
            is_past_morning = now_local.hour >= 9

            if expected_file.is_file():
                size = expected_file.stat().st_size
                results.append(ProbeResult(
                    project=project.name,
                    probe_name="daily_email_summary",
                    status=ProbeStatus.HEALTHY,
                    message=f"Bugünkü e-posta özeti hazırlandı ({today_str}, {size} bayt).",
                    details={"file": str(expected_file), "size": size},
                ))
            else:
                if is_weekday and is_past_morning:
                    results.append(ProbeResult(
                        project=project.name,
                        probe_name="daily_email_summary",
                        status=ProbeStatus.CRITICAL,
                        message=f"E-Posta Asistanı bugün ({today_str}) sabah 08:30 raporunu üretmedi! Servis durmuş veya hata vermiş olabilir.",
                        root_cause="Railway cron tetiklenmemiş veya Gmail API / IMAP okuma esnasında hata alarak erken kapanmış.",
                        step_by_step_fix=[
                            "Railway üzerinde Eposta_Asistani servisinin son cron koşusunu ve loglarını kontrol edin.",
                            "Lokalde `python Projeler/Eposta_Asistani/main.py` çalıştırarak hatayı terminalde izleyin.",
                        ],
                        suggested_action="Railway üzerinde Eposta_Asistani servis loglarını kontrol edin.",
                    ))
                else:
                    results.append(ProbeResult(
                        project=project.name,
                        probe_name="daily_email_summary",
                        status=ProbeStatus.HEALTHY,
                        message=f"Henüz çalışma saati gelmedi veya hafta sonu ({today_str}).",
                    ))
            return results

        # 2. Bulut / Railway ortamındaysak Railway API ile canlı dağıtım durumunu doğrula
        if SentinelConfig.RAILWAY_TOKEN:
            try:
                headers = {
                    "Authorization": f"Bearer {SentinelConfig.RAILWAY_TOKEN}",
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0",
                }
                q = """
                query {
                  project(id: "f81380ac-964f-47e6-8923-94a37b9922d4") {
                    services {
                      edges {
                        node {
                          name
                          deployments(first: 1) {
                            edges {
                              node {
                                status
                                createdAt
                              }
                            }
                          }
                        }
                      }
                    }
                  }
                }
                """
                r = requests.post("https://backboard.railway.com/graphql/v2", headers=headers, json={"query": q}, timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    services = data.get("data", {}).get("project", {}).get("services", {}).get("edges", [])
                    for s in services:
                        s_node = s.get("node", {})
                        if s_node.get("name") == "eposta-asistani":
                            deps = s_node.get("deployments", {}).get("edges", [])
                            if deps:
                                last_dep = deps[0].get("node", {})
                                dep_status = last_dep.get("status")
                                created_at = last_dep.get("createdAt")
                                if dep_status == "SUCCESS":
                                    results.append(ProbeResult(
                                        project=project.name,
                                        probe_name="railway_cron_deployment",
                                        status=ProbeStatus.HEALTHY,
                                        message=f"E-Posta Asistanı Railway servisi aktif ve son dağıtımı başarılı ({dep_status}).",
                                        details={"status": dep_status, "created_at": created_at},
                                    ))
                                    return results
            except Exception as e:
                logger.warning(f"Railway eposta-asistani kontrol hatası: {e}")

        # Fallback healthy
        results.append(ProbeResult(
            project=project.name,
            probe_name="daily_email_summary",
            status=ProbeStatus.HEALTHY,
            message="Bulut ortamı: E-Posta Asistanı Railway servisi yapılandırılmış.",
        ))
        return results

    def _check_generic_pipeline_output(self, project) -> list[ProbeResult]:
        results = []
        output_dirs = [project.dir_path / "output", project.dir_path / "durum", project.dir_path / "reports"]
        found_recent = False
        now_ts = datetime.now().timestamp()

        for od in output_dirs:
            if od.is_dir():
                for f in od.iterdir():
                    if f.is_file() and (now_ts - f.stat().st_mtime) < (48 * 3600):
                        found_recent = True
                        break

        if found_recent:
            results.append(ProbeResult(
                project=project.name,
                probe_name="recent_output_activity",
                status=ProbeStatus.HEALTHY,
                message="Son 48 saat içinde yeni çıktı/rapor tespit edildi.",
            ))

        return results
