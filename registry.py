"""
Merkezi Sentinel — Otomatik Proje Keşfi (Auto-Discovery Registry)
Tüm Projeler/ dizinini tarar; mevcut ve gelecekte eklenecek tüm projeleri
hiçbir manuel yapılandırma gerektirmeden otomatik olarak sınıflandırır ve kaydeder.
"""

import os
import json
import logging
import requests
from pathlib import Path
from dataclasses import dataclass, field
from config import SentinelConfig

logger = logging.getLogger("SentinelRegistry")


@dataclass
class ProjectMetadata:
    name: str
    dir_path: Path
    title: str = ""
    category: str = "Genel"
    project_type: str = "UNKNOWN"  # CRON_PIPELINE, WEB_SERVICE, LOCAL_TOOL, SHARED_LIB
    status: str = "active"  # active, paused, archived
    cron_schedule: str | None = None
    start_command: str | None = None
    has_railway: bool = False
    has_filo: bool = False
    health_url: str | None = None
    custom_config: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "title": self.title,
            "category": self.category,
            "project_type": self.project_type,
            "status": self.status,
            "cron_schedule": self.cron_schedule,
            "start_command": self.start_command,
            "has_railway": self.has_railway,
            "has_filo": self.has_filo,
            "health_url": self.health_url,
        }


class ProjectRegistry:
    def __init__(self, projects_dir: Path | None = None):
        self.projects_dir = projects_dir or SentinelConfig.DIR_PROJECTS
        self._projects: dict[str, ProjectMetadata] = {}

    def scan(self) -> dict[str, ProjectMetadata]:
        """Tüm projeler dizinini tarar ve Proje nesnelerini üretir."""
        self._projects.clear()

        # 1. Eğer yerel Projeler dizini varsa ve taranabiliyorsa tara ve manifesti güncelle
        is_local_fleet = self.projects_dir.is_dir() and len([e for e in os.scandir(self.projects_dir) if e.is_dir() and not e.name.startswith(".")]) > 2

        if is_local_fleet:
            for entry in os.scandir(self.projects_dir):
                if not entry.is_dir() or entry.name.startswith("."):
                    continue

                folder_name = entry.name
                dir_path = Path(entry.path)

                meta = self._inspect_project(folder_name, dir_path)
                self._projects[folder_name] = meta

            # Güncel manifesti kaydet (Cloud deployment için hazır tut)
            try:
                manifest_path = Path(__file__).resolve().parent / "fleet_manifest.json"
                with open(manifest_path, "w", encoding="utf-8") as f:
                    json.dump({k: v.to_dict() for k, v in self._projects.items()}, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.warning(f"Manifest kaydedilemedi: {e}")

            # 3. Railway API üzerinden dinamik servis keşfi ve zenginleştirme yap
            self._discover_railway_cloud_services()

            logger.info(f"Registry yerel taraması tamamlandı: {len(self._projects)} proje keşfedildi.")
            return self._projects

        # 2. Yerel dizin yoksa veya Railway bulut ortamındaysak: fleet_manifest.json'dan yükle
        manifest_path = Path(__file__).resolve().parent / "fleet_manifest.json"
        if manifest_path.is_file():
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest_data = json.load(f)
                    for k, v in manifest_data.items():
                        self._projects[k] = ProjectMetadata(
                            name=v.get("name", k),
                            dir_path=Path(v.get("dir_path", "")),
                            title=v.get("title", ""),
                            category=v.get("category", "Genel"),
                            project_type=v.get("project_type", "UNKNOWN"),
                            status=v.get("status", "active"),
                            cron_schedule=v.get("cron_schedule"),
                            start_command=v.get("start_command"),
                            has_railway=v.get("has_railway", False),
                            has_filo=v.get("has_filo", False),
                            health_url=v.get("health_url"),
                            custom_config=v.get("custom_config", {})
                        )
                logger.info(f"Registry bulut/manifest yüklemesi tamamlandı: {len(self._projects)} proje yüklendi.")
            except Exception as e:
                logger.error(f"Manifest okuma hatası: {e}")

        # Bulut ortamında Railway servislerini dinamik olarak tara ve yeni servisleri ekle
        self._discover_railway_cloud_services()
        return self._projects

    def _discover_railway_cloud_services(self):
        """Railway GraphQL API üzerinden kullanıcının projelerindeki yeni/mevcut servisleri dinamik keşfeder."""
        rw_token = SentinelConfig.RAILWAY_TOKEN
        if not rw_token:
            return

        headers = {
            "Authorization": f"Bearer {rw_token}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0",
        }
        # Bilinen veya aktif Railway proje ID'leri
        pids = ["f81380ac-964f-47e6-8923-94a37b9922d4", "7e007c56-dd47-43ec-9eab-6f574f33d8ad"]
        q = """
        query GetProj($id: String!) {
          project(id: $id) {
            id
            name
            services {
              edges {
                node {
                  id
                  name
                  serviceInstances {
                    edges {
                      node {
                        cronSchedule
                        startCommand
                        domains {
                          serviceDomains {
                            domain
                          }
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        }
        """
        for pid in pids:
            try:
                r = requests.post(
                    "https://backboard.railway.com/graphql/v2",
                    headers=headers,
                    json={"query": q, "variables": {"id": pid}},
                    timeout=8
                )
                if r.status_code == 200:
                    services = r.json().get("data", {}).get("project", {}).get("services", {}).get("edges", [])
                    for s in services:
                        s_node = s.get("node", {})
                        s_name = s_node.get("name")
                        if not s_name or s_name == "merkezi-sentinel":
                            continue

                        inst_edges = s_node.get("serviceInstances", {}).get("edges", [])
                        cron = None
                        start_cmd = None
                        domain = None
                        if inst_edges:
                            inst_node = inst_edges[0].get("node", {})
                            cron = inst_node.get("cronSchedule")
                            start_cmd = inst_node.get("startCommand")
                            s_domains = inst_node.get("domains", {}).get("serviceDomains", [])
                            if s_domains:
                                domain = s_domains[0].get("domain")

                        p_type = "CRON_PIPELINE" if cron else ("WEB_SERVICE" if domain else "UNKNOWN")
                        h_url = f"https://{domain}/health" if domain else None

                        # Var olan projeyi zenginleştir veya yeni eklenen projeyi kaydet
                        matched_key = None
                        for k in self._projects.keys():
                            if k.lower().replace("_", "-") == s_name.lower().replace("_", "-") or s_name.lower() in k.lower():
                                matched_key = k
                                break

                        if matched_key:
                            proj = self._projects[matched_key]
                            proj.has_railway = True
                            if cron and not proj.cron_schedule:
                                proj.cron_schedule = cron
                            if domain and not proj.health_url:
                                proj.health_url = h_url
                            if p_type != "UNKNOWN":
                                proj.project_type = p_type
                        else:
                            # Tamamen yeni eklenmiş bir Railway servisi! Otomatik dahil et!
                            self._projects[s_name] = ProjectMetadata(
                                name=s_name,
                                dir_path=Path(""),
                                title=s_name.replace("-", " ").title(),
                                category="Railway Servisleri",
                                project_type=p_type,
                                status="active",
                                cron_schedule=cron,
                                start_command=start_cmd,
                                has_railway=True,
                                health_url=h_url,
                            )
                            logger.info(f"✨ Railway üzerinden yeni servis otomatik keşfedildi: {s_name}")
            except Exception as e:
                logger.warning(f"Railway dinamik servis keşif hatası ({pid}): {e}")

    def _inspect_project(self, name: str, path: Path) -> ProjectMetadata:
        title = name.replace("_", " ")
        category = "Diğer"
        project_type = "LOCAL_TOOL"
        status = "active"
        cron_schedule = None
        start_command = None
        has_railway = False
        has_filo = False
        health_url = None
        custom_config = {}

        if name.startswith("_"):
            return ProjectMetadata(
                name=name,
                dir_path=path,
                title=title,
                category="Ortak Altyapı",
                project_type="SHARED_LIB",
                status="active",
            )

        # 1. filo.json incelemesi
        filo_path = path / "filo.json"
        if filo_path.is_file():
            has_filo = True
            try:
                with open(filo_path, "r", encoding="utf-8") as f:
                    filo_data = json.load(f)
                    title = filo_data.get("ad", title)
                    category = filo_data.get("kategori", category)
                    if filo_data.get("durum") == "pasif" or not filo_data.get("dahil_et", True):
                        status = "paused"
            except Exception:
                pass

        # 2. railway.json incelemesi
        railway_path = path / "railway.json"
        if railway_path.is_file():
            has_railway = True
            try:
                with open(railway_path, "r", encoding="utf-8") as f:
                    rw_data = json.load(f)
                    deploy = rw_data.get("deploy", {})
                    cron_schedule = deploy.get("cronSchedule")
                    start_command = deploy.get("startCommand")
                    if cron_schedule:
                        project_type = "CRON_PIPELINE"
                    elif start_command and any(w in start_command.lower() for w in ["uvicorn", "gunicorn", "flask", "serve", "http", "app.listen"]):
                        project_type = "WEB_SERVICE"
            except Exception:
                pass

        # 3. Procfile incelemesi (Railway/Heroku)
        procfile_path = path / "Procfile"
        if procfile_path.is_file():
            try:
                content = procfile_path.read_text(encoding="utf-8").lower()
                if "web:" in content or "uvicorn" in content:
                    project_type = "WEB_SERVICE"
            except Exception:
                pass

        # 4. Kod tarama (özel kalıplar)
        main_py = path / "main.py"
        if main_py.is_file():
            try:
                # İlk 3000 byte'ı incele
                with open(main_py, "r", encoding="utf-8", errors="ignore") as f:
                    sample = f.read(3000)
                    if "FastAPI(" in sample or "Flask(" in sample:
                        project_type = "WEB_SERVICE"
                    elif "schedule.every(" in sample or "CRON mode" in sample or "weekday" in sample:
                        if project_type != "WEB_SERVICE":
                            project_type = "CRON_PIPELINE"
            except Exception:
                pass

        # 5. Opsiyonel sentinel.json (özelleştirilmiş sözleşme)
        sentinel_json = path / "sentinel.json"
        if sentinel_json.is_file():
            try:
                with open(sentinel_json, "r", encoding="utf-8") as f:
                    custom_config = json.load(f)
                    health_url = custom_config.get("health_url", health_url)
                    project_type = custom_config.get("type", project_type)
                    status = custom_config.get("status", status)
            except Exception:
                pass

        # Özel bilinen servisler için akıllı eşleme (varsayılanlar)
        if "takalike" in name.lower() and "chat" in name.lower():
            project_type = "WEB_SERVICE"
            health_url = SentinelConfig.TAKALIKE_WEBHOOK_URL + "/health"
        elif "linkedin" in name.lower() and "text" in name.lower():
            project_type = "CRON_PIPELINE"
        elif "eposta" in name.lower() and "asistan" in name.lower():
            project_type = "CRON_PIPELINE"

        return ProjectMetadata(
            name=name,
            dir_path=path,
            title=title,
            category=category,
            project_type=project_type,
            status=status,
            cron_schedule=cron_schedule,
            start_command=start_command,
            has_railway=has_railway,
            has_filo=has_filo,
            health_url=health_url,
            custom_config=custom_config,
        )

    def get_projects(self) -> dict[str, ProjectMetadata]:
        if not self._projects:
            self.scan()
        return self._projects
