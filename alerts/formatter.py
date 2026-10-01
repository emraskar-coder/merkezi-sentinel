"""
Merkezi Sentinel — Rapor ve Alarm Biçimlendirici (Formatter)
Terminal konsolu ve HTML e-postalar için modern, okunabilir çıktılar üretir.
"""

from datetime import datetime
from probes.base import ProbeResult, ProbeStatus


def build_html_report(results: list[ProbeResult], fleet_count: int) -> tuple[str, str, str]:
    """HTML e-posta gövdesi, düz metin ve konu başlığı üretir.
    Returns: (subject, html_body, plain_text)
    """
    criticals = [r for r in results if r.status == ProbeStatus.CRITICAL]
    warnings = [r for r in results if r.status == ProbeStatus.WARNING]
    healthies = [r for r in results if r.status == ProbeStatus.HEALTHY]

    now_str = datetime.now().strftime("%d.%m.%Y %H:%M")

    # Konu Başlığı
    if criticals:
        subject = f"🚨 [KRİTİK ALARM] Sentinel: {len(criticals)} Serviste Aksama Tespit Edildi ({now_str})"
    elif warnings:
        subject = f"⚠️ [UYARI] Sentinel: {len(warnings)} Serviste Dikkat Edilecek Durum ({now_str})"
    else:
        subject = f"✅ [SAĞLIKLI] Sentinel: Tüm Filo Stabil ({fleet_count} Proje) — {now_str}"

    # HTML Parçaları
    alert_cards_html = ""
    for r in criticals + warnings:
        is_crit = r.status == ProbeStatus.CRITICAL
        badge_bg = "#ef4444" if is_crit else "#f59e0b"
        badge_txt = "KRİTİK ARIZA" if is_crit else "UYARI"
        border_color = "#f87171" if is_crit else "#fbbf24"
        bg_card = "#1e293b"

        root_cause_html = ""
        if r.root_cause:
            root_cause_html = f"""
            <div style="margin-top: 8px; font-size: 12.5px; color: #cbd5e1; background: rgba(0,0,0,0.25); padding: 8px 12px; border-radius: 6px;">
                <span style="color: #fca5a5; font-weight: 600;">🔍 Kök Neden:</span> {r.root_cause}
            </div>
            """

        steps_html = ""
        if r.step_by_step_fix:
            items = "".join(f"<li style='margin-bottom: 4px;'>{s}</li>" for s in r.step_by_step_fix)
            steps_html = f"""
            <div style="margin-top: 10px; padding: 10px 14px; background: rgba(59, 130, 246, 0.12); border-left: 3px solid #3b82f6; border-radius: 4px; font-size: 13px; color: #93c5fd;">
                <div style="font-weight: 700; margin-bottom: 6px; color: #60a5fa;">🛠️ Çözüm Adımları:</div>
                <ol style="margin: 0; padding-left: 18px; color: #e2e8f0; line-height: 1.5;">{items}</ol>
            </div>
            """

        alert_cards_html += f"""
        <div style="background: {bg_card}; border: 1px solid {border_color}; border-radius: 8px; padding: 16px 20px; margin-bottom: 14px; color: #f8fafc;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <span style="font-weight: 700; font-size: 15px; color: #ffffff;">{r.project}</span>
                <span style="background: {badge_bg}; color: #ffffff; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;">{badge_txt}</span>
            </div>
            <div style="font-size: 13.5px; color: #f1f5f9; font-weight: 600; line-height: 1.5;">{r.message}</div>
            {root_cause_html}
            {steps_html}
        </div>
        """

    healthy_rows = ""
    for r in healthies[:12]:
        healthy_rows += f"""
        <tr style="border-bottom: 1px solid #334155;">
            <td style="padding: 8px 10px; font-weight: 600; color: #f1f5f9;">{r.project}</td>
            <td style="padding: 8px 10px; color: #10b981; font-weight: 600;">Aktif / Sağlıklı</td>
            <td style="padding: 8px 10px; color: #94a3b8; font-size: 12px;">{r.message}</td>
        </tr>
        """

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0f172a; margin: 0; padding: 20px; }}
            .container {{ max-width: 680px; margin: 0 auto; background: #1e293b; border-radius: 12px; border: 1px solid #334155; overflow: hidden; }}
            .header {{ background: linear-gradient(135deg, #1e1b4b 0%, #0f172a 100%); padding: 24px; text-align: left; border-bottom: 1px solid #334155; }}
            .stats-bar {{ display: flex; background: #0f172a; padding: 12px 20px; border-bottom: 1px solid #334155; }}
            .stat-item {{ flex: 1; text-align: center; }}
            .stat-num {{ font-size: 18px; font-weight: 700; }}
            .stat-lbl {{ font-size: 11px; color: #94a3b8; text-transform: uppercase; }}
            .content {{ padding: 24px; }}
        </style>
    </head>
    <body style="background-color: #0f172a; color: #e2e8f0;">
        <div class="container" style="max-width: 680px; margin: 0 auto; background: #1e293b; border-radius: 12px; border: 1px solid #334155;">
            <div class="header" style="padding: 24px; border-bottom: 1px solid #334155; background: #1e1b4b;">
                <div style="font-size: 20px; font-weight: 800; color: #ffffff; letter-spacing: -0.5px;">🛡️ Merkezi Sentinel</div>
                <div style="font-size: 13px; color: #94a3b8; margin-top: 4px;">Otonom Proje Sağlık ve Canlılık Raporu • {now_str}</div>
            </div>

            <table width="100%" cellpadding="0" cellspacing="0" style="background: #0f172a; border-bottom: 1px solid #334155; text-align: center; padding: 10px 0;">
                <tr>
                    <td style="padding: 10px;">
                        <div style="font-size: 18px; font-weight: 700; color: #38bdf8;">{fleet_count}</div>
                        <div style="font-size: 11px; color: #94a3b8;">TOPLAM PROJE</div>
                    </td>
                    <td style="padding: 10px;">
                        <div style="font-size: 18px; font-weight: 700; color: #ef4444;">{len(criticals)}</div>
                        <div style="font-size: 11px; color: #94a3b8;">KRİTİK ARIZA</div>
                    </td>
                    <td style="padding: 10px;">
                        <div style="font-size: 18px; font-weight: 700; color: #f59e0b;">{len(warnings)}</div>
                        <div style="font-size: 11px; color: #94a3b8;">UYARI</div>
                    </td>
                    <td style="padding: 10px;">
                        <div style="font-size: 18px; font-weight: 700; color: #10b981;">{len(healthies)}</div>
                        <div style="font-size: 11px; color: #94a3b8;">SAĞLIKLI</div>
                    </td>
                </tr>
            </table>

            <div class="content" style="padding: 24px;">
                {f'<h3 style="color: #ffffff; font-size: 16px; margin-top: 0; margin-bottom: 14px;">🚨 Dikkat Gerektiren Servisler</h3>{alert_cards_html}' if (criticals or warnings) else '<div style="background: rgba(16, 185, 129, 0.1); border: 1px solid #10b981; border-radius: 8px; padding: 14px; text-align: center; color: #34d399; font-weight: 600;">✨ Harika! Tüm taranan projeler beklenen şekilde sorunsuz çalışıyor.</div>'}

                <h3 style="color: #ffffff; font-size: 15px; margin-top: 24px; margin-bottom: 10px;">📋 Son Denetlenen Sağlıklı Servisler</h3>
                <table width="100%" cellpadding="0" cellspacing="0" style="font-size: 13px; text-align: left;">
                    {healthy_rows}
                </table>
            </div>

            <div style="padding: 14px 24px; background: #0f172a; border-top: 1px solid #334155; font-size: 11px; color: #64748b; text-align: center;">
                Merkezi Sentinel Otonom Altyapı Koruyucusu • Antigravity Ekosistemi
            </div>
        </div>
    </body>
    </html>
    """

    plain_text = f"Merkezi Sentinel Raporu ({now_str})\n"
    plain_text += f"Toplam Proje: {fleet_count} | Kritik: {len(criticals)} | Uyarı: {len(warnings)} | Sağlıklı: {len(healthies)}\n\n"
    for r in criticals + warnings:
        plain_text += f"[{r.status.value}] {r.project}: {r.message}\n"
        if r.suggested_action:
            plain_text += f"  -> Aksiyon: {r.suggested_action}\n"
        plain_text += "\n"

    return subject, html_body, plain_text


def _safe_print(text: str):
    """Windows cp1254 uyumlu güvenli terminal yazdırma."""
    try:
        print(text)
    except UnicodeEncodeError:
        safe_text = text.encode("ascii", errors="replace").decode("ascii")
        print(safe_text)


def print_cli_summary(results: list[ProbeResult], fleet_count: int):
    """Terminal çıktısı için renkli konsol raporu."""
    criticals = [r for r in results if r.status == ProbeStatus.CRITICAL]
    warnings = [r for r in results if r.status == ProbeStatus.WARNING]
    healthies = [r for r in results if r.status == ProbeStatus.HEALTHY]

    _safe_print("\n" + "=" * 65)
    _safe_print("[SENTINEL] MERKEZI SENTINEL - EKOSISTEM SAGLIK VE CANLILIK RAPORU")
    _safe_print("=" * 65)
    _safe_print(f"Toplam Kesfedilen Proje : {fleet_count}")
    _safe_print(f"Kritik Hata / Aksama    : {len(criticals)}")
    _safe_print(f"Uyari                   : {len(warnings)}")
    _safe_print(f"Saglikli Denetim        : {len(healthies)}")
    _safe_print("-" * 65)

    if criticals:
        _safe_print("\n[!] KRITIK AKSAKLIKLAR:")
        for r in criticals:
            _safe_print(f"  [X] [{r.project}] {r.message}")
            if r.root_cause:
                _safe_print(f"      [Kok Neden] {r.root_cause}")
            if r.step_by_step_fix:
                _safe_print(f"      [Cozum Reçetesi]:")
                for s in r.step_by_step_fix:
                    _safe_print(f"        * {s}")
            elif r.suggested_action:
                _safe_print(f"      -> Aksiyon: {r.suggested_action}")

    if warnings:
        _safe_print("\n[?] UYARILAR:")
        for r in warnings:
            _safe_print(f"  [!] [{r.project}] {r.message}")
            if r.root_cause:
                _safe_print(f"      [Kok Neden] {r.root_cause}")
            if r.step_by_step_fix:
                _safe_print(f"      [Cozum Reçetesi]:")
                for s in r.step_by_step_fix:
                    _safe_print(f"        * {s}")
            elif r.suggested_action:
                _safe_print(f"      -> Aksiyon: {r.suggested_action}")

    if not criticals and not warnings:
        _safe_print("\n[OK] TUM KONTROLLER BASARILI: Hicbir aksaklik veya sessiz olum tespit edilmedi.")

    _safe_print("=" * 65 + "\n")
