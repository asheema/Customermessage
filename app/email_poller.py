from __future__ import annotations
import imaplib, email, os, time
from email.header import decode_header
from .channels import normalize_message
from .db import save_message
from .queue import QUEUE

def text_from_message(msg):
    if msg.is_multipart():
        parts=[]
        for p in msg.walk():
            if p.get_content_type()=="text/plain" and p.get_content_disposition()!="attachment":
                parts.append(p.get_payload(decode=True).decode(p.get_content_charset() or "utf-8",errors="replace"))
        return "\n".join(parts)
    return msg.get_payload(decode=True).decode(msg.get_content_charset() or "utf-8",errors="replace") if msg.get_payload(decode=True) else ""

def run():
    host=os.environ["IMAP_HOST"]; user=os.environ["IMAP_USER"]; password=os.environ["IMAP_PASSWORD"]
    folder=os.getenv("IMAP_FOLDER","INBOX"); poll=int(os.getenv("EMAIL_POLL_SECONDS","30"))
    while True:
        try:
            with imaplib.IMAP4_SSL(host) as box:
                box.login(user,password); box.select(folder)
                _, data=box.search(None,"UNSEEN")
                for num in data[0].split():
                    _, raw=box.fetch(num,"(RFC822)"); msg=email.message_from_bytes(raw[0][1])
                    mid=msg.get("Message-ID") or f"imap-{num.decode()}"
                    subject=str(msg.get("Subject", "")); body=text_from_message(msg)
                    text=f"Subject: {subject}\n{body}" if subject else body
                    m=normalize_message(mid,os.getenv("EMAIL_BRAND","vitalis-wellness"),"email",text,msg.get("From"),{"source":"imap"})
                    save_message(m); QUEUE.enqueue(m); box.store(num,"+FLAGS","\\Seen")
        except Exception as exc:
            print(f"IMAP poller error: {exc}")
        time.sleep(poll)

if __name__=="__main__": run()
