#!/usr/bin/env python3
"""
email_sender.py -- Turnover Titans

Real SMTP send capability for the turnover-titans@northfraim.com inbox.
This is the piece secretary_email_bridge.py explicitly didn't have:
that module reads and drafts, this one sends -- kept as a separate
function you call deliberately, not wired into any automatic path.
lead_watcher.py's own design is "nothing sends itself" on purpose; this
module doesn't change that, it just makes a real send possible when a
human (or an explicitly-invoked script) decides to.

Credentials come from environment variables, same as secretary_email_bridge.py:
  IONOS_TT_EMAIL     e.g. turnover-titans@northfraim.com
  IONOS_TT_PASSWORD  the mailbox password

IONOS SMTP server: smtp.ionos.com, port 587, STARTTLS -- confirmed with
a real login test before this was written.
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr

SMTP_HOST = "smtp.ionos.com"
SMTP_PORT = 587


class EmailSendError(RuntimeError):
    pass


def send_email(to_addr: str, subject: str, body: str, from_name: str = "Turnover Titans",
                email_addr: str = None, password: str = None) -> None:
    """Real SMTP send via STARTTLS. Raises EmailSendError on any real
    failure -- never silently swallows a send failure, since a draft
    that was supposed to go out and didn't is worse than a loud error."""
    email_addr = email_addr or os.environ.get("IONOS_TT_EMAIL")
    password = password or os.environ.get("IONOS_TT_PASSWORD")
    if not email_addr or not password:
        raise EmailSendError("IONOS_TT_EMAIL and IONOS_TT_PASSWORD must be set in the environment.")
    if not to_addr or "@" not in to_addr:
        raise EmailSendError(f"Refusing to send: '{to_addr}' doesn't look like a real email address.")

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = formataddr((from_name, email_addr))
    msg["To"] = to_addr

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as s:
            s.ehlo()
            s.starttls()
            s.ehlo()
            s.login(email_addr, password)
            s.sendmail(email_addr, [to_addr], msg.as_string())
    except (smtplib.SMTPException, OSError) as e:
        raise EmailSendError(f"Real SMTP send failed: {e}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 4:
        print("Usage: python3 email_sender.py <to_addr> <subject> <body>")
        sys.exit(1)
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
    send_email(sys.argv[1], sys.argv[2], sys.argv[3])
    print(f"Sent to {sys.argv[1]}")
