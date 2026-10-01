"""
Merkezi Sentinel — Web Dashboard Sunucusu
Yerel veya sunucuda tek komutla çalışır, paneli sunar ve tek-tık tarama yaptırır.

Kullanım:
    python dashboard_server.py --port 8787
"""

import os
import sys
import json
import logging
import subprocess
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = CURRENT_DIR.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

logger = logging.getLogger("DashboardServer")


class SentinelDashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(CURRENT_DIR), **kwargs)

    def do_POST(self):
        if self.path == "/api/scan":
            logger.info("Tarama tetiklendi (/api/scan)...")
            try:
                # Arka planda runner.py'yi çalıştır
                runner_script = PROJECT_DIR / "runner.py"
                subprocess.Popen([sys.executable, str(runner_script)])
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "scan_started"}).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()


def run_server(port: int = 8787):
    # Önce state dosyasının var olduğundan emin ol
    state_file = CURRENT_DIR / "dashboard_state.json"
    if not state_file.is_file():
        from runner import SentinelRunner
        logger.info("İlk tarama yapılıyor...")
        SentinelRunner().run_full_scan()

    server_address = ("", port)
    httpd = HTTPServer(server_address, SentinelDashboardHandler)
    logger.info(f"🛡️ Sentinel Dashboard aktif: http://localhost:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Sunucu durduruldu.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    port = 8787
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        port = int(sys.argv[1])
    run_server(port)
