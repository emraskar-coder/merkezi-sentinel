"""
Merkezi Sentinel — Gmail API Doğrudan Bildirim Gönderici
HTTPS Port 443 üzerinden Gmail REST API ile çalışır; Railway ve bulut
ortamlarındaki SMTP port engellerinden asla etkilenmez.
"""

import os
import base64
import smtplib
import logging
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from config import SentinelConfig

logger = logging.getLogger("SentinelAlert")


def send_sentinel_alert(
    subject: str,
    html_content: str,
    plain_fallback: str = "",
    recipient: str | None = None,
    cc: str | None = None,
) -> bool:
    """Sentinel alarm veya durum raporunu doğrudan birincil gelen kutusuna iletir."""
    target_to = recipient or SentinelConfig.ALERT_EMAIL
    target_cc = cc or SentinelConfig.ALERT_CC
    sender = SentinelConfig.SENDER_EMAIL

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Merkezi Sentinel <{sender}>"
    msg["To"] = target_to
    if target_cc:
        msg["Cc"] = target_cc

    msg.attach(MIMEText(plain_fallback or "Merkezi Sentinel Raporu", "plain", "utf-8"))
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    # 1. Öncelik: HTTPS Gmail REST API
    if _send_via_gmail_api(msg, target_to):
        return True

    # 2. Fallback: SMTP
    return _send_via_smtp(msg, target_to)


def _send_via_gmail_api(msg: MIMEMultipart, recipient: str) -> bool:
    cid = SentinelConfig.GMAIL_PERSONAL_CLIENT_ID
    sec = SentinelConfig.GMAIL_PERSONAL_CLIENT_SECRET
    rf = SentinelConfig.GMAIL_PERSONAL_REFRESH_TOKEN

    if not (cid and sec and rf):
        logger.warning("Gmail OAuth bilgileri eksik, API gönderimi atlandı.")
        return False

    try:
        r_token = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": cid,
                "client_secret": sec,
                "refresh_token": rf,
                "grant_type": "refresh_token",
            },
            timeout=10,
        )
        if r_token.status_code != 200:
            logger.warning(f"OAuth token refresh başarısız ({r_token.status_code}): {r_token.text[:150]}")
            return False

        access_token = r_token.json().get("access_token")
        raw_b64 = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")

        r_send = requests.post(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            json={"raw": raw_b64},
            timeout=15,
        )

        if r_send.status_code in (200, 201):
            msg_id = r_send.json().get("id", "")
            logger.info(f"Sentinel alarm maili başarıyla iletildi (Gmail API) -> {recipient} [Msg ID: {msg_id}]")
            return True
        else:
            logger.warning(f"Gmail API gönderim reddedildi ({r_send.status_code}): {r_send.text[:200]}")
            return False

    except Exception as e:
        logger.warning(f"Gmail API gönderim istisnası: {e}")
        return False


def _send_via_smtp(msg: MIMEMultipart, recipient: str) -> bool:
    sender = SentinelConfig.SENDER_EMAIL
    pwd = (SentinelConfig.GMAIL_PERSONAL_APP_PASSWORD or "").replace(" ", "")
    if not sender or not pwd:
        return False

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=12) as s:
            s.login(sender, pwd)
            s.send_message(msg)
        logger.info(f"Sentinel alarm maili başarıyla iletildi (SMTP SSL 465) -> {recipient}")
        return True
    except Exception as e:
        logger.warning(f"SMTP gönderim hatası: {e}")
        return False
