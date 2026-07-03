import asyncio
import logging
import os
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger("lms.email")


def _get_smtp_config():
    host = os.getenv("SMTP_HOST", "")
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME", "")
    password = os.getenv("SMTP_PASSWORD", "")
    from_email = os.getenv("SMTP_FROM_EMAIL", username)
    from_name = os.getenv("SMTP_FROM_NAME", "LMS System")
    return host, port, username, password, from_email, from_name


def is_configured() -> bool:
    host, port, username, password, _, _ = _get_smtp_config()
    return bool(host and username and password)


def _send_smtp_sync(host, port, username, password, from_email, from_name, to, subject, html_body):
    msg = MIMEMultipart("alternative")
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html"))

    context = ssl.create_default_context()
    with smtplib.SMTP(host, port) as server:
        server.ehlo()
        server.starttls(context=context)
        server.ehlo()
        server.login(username, password)
        server.sendmail(from_email, to, msg.as_string())


async def send_email(to: str, subject: str, html_body: str) -> bool:
    host, port, username, password, from_email, from_name = _get_smtp_config()

    if not host or not username or not password:
        logger.warning("SMTP not configured. Email not sent to %s", to)
        return False

    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(
            None, _send_smtp_sync, host, port, username, password,
            from_email, from_name, to, subject, html_body,
        )
        logger.info("Email sent to %s", to)
        return True
    except smtplib.SMTPAuthenticationError:
        logger.error("SMTP auth failed for %s. Check SMTP_USERNAME/PASSWORD.", username)
        return False
    except smtplib.SMTPException as e:
        logger.error("SMTP error sending to %s: %s", to, e)
        return False
    except OSError as e:
        logger.error("Connection error sending to %s: %s", to, e)
        return False


def build_welcome_email(name: str, student_id: str, email: str, password: str, app_url: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:sans-serif;background:#f5f5f5;padding:40px">
<div style="max-width:520px;margin:auto;background:white;border-radius:12px;padding:32px">
<h2 style="margin-top:0">Welcome to LMS</h2>
<p>Hi <strong>{name}</strong>,</p>
<p>Your account has been created. Sign in with the credentials below and change your password.</p>
<table style="width:100%;border-collapse:collapse;margin:20px 0">
<tr><td style="padding:8px;color:#666">Student ID</td>
<td style="padding:8px;font-weight:600">{student_id}</td></tr>
<tr><td style="padding:8px;color:#666">Email</td>
<td style="padding:8px;font-weight:600">{email}</td></tr>
<tr><td style="padding:8px;color:#666">Password</td>
<td style="padding:8px;font-weight:600;font-family:monospace">{password}</td></tr>
</table>
<a href="{app_url}/login" style="display:inline-block;background:#E50914;color:white;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:600">Sign In</a>
<p style="margin-top:24px;font-size:13px;color:#999">You'll be asked to change your password on first login.</p>
</div></body></html>"""


def build_reset_email(name: str, email: str, password: str, app_url: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:sans-serif;background:#f5f5f5;padding:40px">
<div style="max-width:520px;margin:auto;background:white;border-radius:12px;padding:32px">
<h2 style="margin-top:0">Password Reset</h2>
<p>Hi <strong>{name}</strong>,</p>
<p>Your password has been reset. Use the temporary password below.</p>
<table style="width:100%;border-collapse:collapse;margin:20px 0">
<tr><td style="padding:8px;color:#666">Email</td>
<td style="padding:8px;font-weight:600">{email}</td></tr>
<tr><td style="padding:8px;color:#666">New Password</td>
<td style="padding:8px;font-weight:600;font-family:monospace">{password}</td></tr>
</table>
<a href="{app_url}/login" style="display:inline-block;background:#E50914;color:white;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:600">Sign In</a>
<p style="margin-top:24px;font-size:13px;color:#999">You'll be asked to change your password on first login.</p>
</div></body></html>"""
