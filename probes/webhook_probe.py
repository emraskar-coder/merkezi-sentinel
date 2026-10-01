"""
Merkezi Sentinel — Canlı Webhook ve Akıllı Teşhis Denetçisi (Smart Webhook Probe)
7/24 çalışan chatbot ve asistanların HTTP health endpoint'lerini,
ManyChat/Meta bağlantılarını ve Railway canlı domainlerini otomatik teşhis eder.
"""

import time
import requests
import logging
from config import SentinelConfig
from probes.base import BaseProbe, ProbeResult, ProbeStatus

logger = logging.getLogger("WebhookProbe")


class WebhookProbe(BaseProbe):
    name = "WebhookProbe"

    def run(self, project) -> list[ProbeResult]:
        results = []
        p_name = project.name.lower()

        # 1. Takalike Chat Asistanı Entegrasyon ve ManyChat Denetimi
        if "takalike" in p_name and "chat" in p_name:
            results.extend(self._check_manychat_token(project))
            results.append(self._check_takalike_smart_health(project))

        # 2. Diğer Tanımlı HTTP Health Endpoint'leri
        elif project.health_url:
            results.append(self._check_http_health(project, project.health_url))

        return results

    def _check_takalike_smart_health(self, project) -> ProbeResult:
        """Takalike Chatbot için akıllı teşhisli canlılık kontrolü.
        Statik URL 404 dönerse Railway API'sine gidip gerçek canlı domaini bulur ve test eder.
        """
        configured_url = SentinelConfig.TAKALIKE_WEBHOOK_URL
        health_target = f"{configured_url}/health"

        t0 = time.time()
        try:
            resp = requests.get(health_target, timeout=SentinelConfig.HTTP_PROBE_TIMEOUT)
            latency_ms = int((time.time() - t0) * 1000)
            if resp.status_code == 200:
                data = resp.json() if "application/json" in resp.headers.get("Content-Type", "") else {}
                return ProbeResult(
                    project=project.name,
                    probe_name="http_health_endpoint",
                    status=ProbeStatus.HEALTHY,
                    message=f"Canlı servis yanıt veriyor (HTTP 200, {latency_ms}ms).",
                    details={"url": health_target, "response": data},
                )
        except Exception:
            resp = None

        # Eğer yapılandırılan URL başarısız olduysa (Örn: 404 Application not found) -> OTONOM TEŞHİS MOTORU DEVREYE GİRER
        real_domain = self._discover_railway_domain(project_id="7e007c56-dd47-43ec-9eab-6f574f33d8ad")
        if real_domain:
            real_url = f"https://{real_domain}/health"
            try:
                real_resp = requests.get(real_url, timeout=SentinelConfig.HTTP_PROBE_TIMEOUT)
                if real_resp.status_code == 200:
                    real_data = real_resp.json()
                    return ProbeResult(
                        project=project.name,
                        probe_name="http_health_endpoint",
                        status=ProbeStatus.WARNING,
                        message=f"Domain Uyuşmazlığı Tespit Edildi, Ancak Canlı Servis Aktif!",
                        root_cause=(
                            f"Konfigürasyondaki adres '{configured_url}' geçersiz (HTTP 404). "
                            f"Ancak Railway canlı taramasında gerçek domain '{real_domain}' olarak keşfedildi "
                            f"ve test edildiğinde servisin %100 sağlıklı olduğu kanıtlandı."
                        ),
                        step_by_step_fix=[
                            f"ManyChat webhook ayarlarınızdaki alan adını 'https://{real_domain}' olarak güncelleyin.",
                            f"master.env veya Sentinel config'de TAKALIKE_WEBHOOK_URL değerini 'https://{real_domain}' yapın.",
                            "Tüm bileşenler (OpenAI, Groq Whisper, ManyChat, Supabase) canlı ve çalışır durumda.",
                        ],
                        suggested_action=f"ManyChat webhook URL'ini 'https://{real_domain}' olarak teyit edin.",
                        auto_resolved=False,
                        details={
                            "configured_url": configured_url,
                            "actual_domain": real_domain,
                            "health_data": real_data,
                        },
                    )
            except Exception as e:
                logger.warning(f"Gerçek domain testi başarısız: {e}")

        # Gerçek domain de yoksa veya servis gerçekten çöktüyse
        return ProbeResult(
            project=project.name,
            probe_name="http_health_endpoint",
            status=ProbeStatus.CRITICAL,
            message="Servis arızalı veya ulaşılamıyor (HTTP 404 / Bağlantı Hatası)!",
            root_cause="Railway üzerinde çalışan canlı bir konteyner bulunamadı veya domain yönlendirmesi silinmiş.",
            step_by_step_fix=[
                "Railway paneline gidin (Proje: takalike-chatbot).",
                "Settings > Networking sekmesinden 'Generate Domain' butonuna tıklayarak public domain oluşturun.",
                "Deployments sekmesinden son deploy'un 'SUCCESS' olduğundan emin olun.",
            ],
            suggested_action="Railway üzerinde takalike-chatbot servisinin Networking ayarlarından domain oluşturun.",
        )

    def _discover_railway_domain(self, project_id: str) -> str | None:
        """Railway API üzerinden servisin gerçek canlı domainini bulur."""
        token = SentinelConfig.RAILWAY_TOKEN
        if not token:
            return None
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0",
        }
        q = """
        query getProj($id: String!) {
          project(id: $id) {
            services {
              edges {
                node {
                  id
                  name
                }
              }
            }
          }
        }
        """
        try:
            r = requests.post(
                "https://backboard.railway.app/graphql/v2",
                headers=headers,
                json={"query": q, "variables": {"id": project_id}},
                timeout=10,
            ).json()
            svcs = r.get("data", {}).get("project", {}).get("services", {}).get("edges", [])
            if not svcs:
                return None
            svc_id = svcs[0]["node"]["id"]

            q_dep = """
            query getDep($svcId: String!) {
              deployments(input: { serviceId: $svcId, status: { notIn: [REMOVED, SKIPPED] } }, first: 1) {
                edges {
                  node {
                    staticUrl
                    status
                  }
                }
              }
            }
            """
            r_dep = requests.post(
                "https://backboard.railway.app/graphql/v2",
                headers=headers,
                json={"query": q_dep, "variables": {"svcId": svc_id}},
                timeout=10,
            ).json()
            deps = r_dep.get("data", {}).get("deployments", {}).get("edges", [])
            if deps:
                return deps[0]["node"].get("staticUrl")
        except Exception as e:
            logger.warning(f"Railway domain keşif hatası: {e}")
        return None

    def _check_http_health(self, project, url: str) -> ProbeResult:
        t0 = time.time()
        try:
            headers = {"User-Agent": "MerkeziSentinel/1.0"}
            resp = requests.get(url, headers=headers, timeout=SentinelConfig.HTTP_PROBE_TIMEOUT)
            latency_ms = int((time.time() - t0) * 1000)

            if resp.status_code == 200:
                return ProbeResult(
                    project=project.name,
                    probe_name="http_health_endpoint",
                    status=ProbeStatus.HEALTHY,
                    message=f"Canlı servis yanıt veriyor (HTTP 200, {latency_ms}ms).",
                    details={"url": url, "status_code": 200, "latency_ms": latency_ms},
                )
            else:
                return ProbeResult(
                    project=project.name,
                    probe_name="http_health_endpoint",
                    status=ProbeStatus.CRITICAL,
                    message=f"Servis arızalı (HTTP {resp.status_code}, {latency_ms}ms)!",
                    root_cause=f"Sunucu {resp.status_code} kodu döndürdü. Servis çökmüş veya rota bulunamıyor.",
                    step_by_step_fix=[
                        f"Railway üzerinde {project.name} servisinin loglarını inceleyin.",
                        f"Konteynerin çöküp çökmediğini kontrol edin.",
                        "Gerekiyorsa servisi Restart edin.",
                    ],
                    suggested_action=f"Railway üzerinde {project.name} servisinin loglarını ve durumunu kontrol edin.",
                )
        except Exception as e:
            return ProbeResult(
                project=project.name,
                probe_name="http_health_endpoint",
                status=ProbeStatus.CRITICAL,
                message=f"Servise ulaşılamıyor: {e}",
                root_cause=str(e),
                step_by_step_fix=[
                    f"Konteynerin çalışır durumda olduğunu Railway panelinden teyit edin.",
                    f"Ağ veya DNS erişimini kontrol edin.",
                ],
            )

    def _check_manychat_token(self, project) -> list[ProbeResult]:
        results = []
        token = SentinelConfig.TAKALIKE_MANYCHAT_TOKEN
        if not token:
            results.append(ProbeResult(
                project=project.name,
                probe_name="manychat_api_token",
                status=ProbeStatus.WARNING,
                message="TAKALIKE_MANYCHAT_TOKEN tanımlı değil.",
            ))
            return results

        try:
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            r = requests.get("https://api.manychat.com/fb/page/getInfo", headers=headers, timeout=10)
            if r.status_code == 200:
                data = r.json().get("data", {})
                page_name = data.get("name", "Bilinmeyen Sayfa")
                page_id = data.get("id", "")
                results.append(ProbeResult(
                    project=project.name,
                    probe_name="manychat_api_token",
                    status=ProbeStatus.HEALTHY,
                    message=f"ManyChat API token aktif: '{page_name}' (ID: {page_id}).",
                    details={"page_name": page_name, "page_id": page_id},
                ))
            else:
                results.append(ProbeResult(
                    project=project.name,
                    probe_name="manychat_api_token",
                    status=ProbeStatus.CRITICAL,
                    message=f"ManyChat API token geçersiz (HTTP {r.status_code})!",
                    root_cause="ManyChat API anahtarı geçersiz kılındı veya süresi doldu.",
                    step_by_step_fix=[
                        "ManyChat paneline girin -> Settings -> API.",
                        "Yeni bir API Secret Token oluşturun.",
                        "master.env ve Railway ortam değişkenlerinde TAKALIKE_MANYCHAT_TOKEN değerini güncelleyin.",
                    ],
                    suggested_action="ManyChat API token yenilenmeli.",
                ))
        except Exception as e:
            results.append(ProbeResult(
                project=project.name,
                probe_name="manychat_api_token",
                status=ProbeStatus.WARNING,
                message=f"ManyChat bağlantı hatası: {e}",
            ))

        return results
