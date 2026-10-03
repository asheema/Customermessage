from __future__ import annotations
import os, uuid
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel, Field
from .db import init_db, save_message, recent_decisions
from .queue import QUEUE
from .channels import whatsapp_messages, instagram_messages, verify_meta_get, verify_signature, normalize_message
from .metrics import prometheus_payload, update_queue_depth

app=FastAPI(title="Customer Message AI Triage API",version="2.0.0")

class Message(BaseModel):
    id:str=Field(...,min_length=1); brand:str="Other"; channel:str="other"; text:str|None=""; sender:str|None=None

@app.on_event("startup")
def startup(): init_db()

@app.get("/health")
def health():
    init_db(); update_queue_depth(QUEUE.size())
    return {"status":"ok","queue_backend":QUEUE.backend,"queue_depth":QUEUE.size(),"postgres_enabled":bool(os.getenv("DATABASE_URL")),
            "whatsapp_webhook":"/webhooks/whatsapp","instagram_webhook":"/webhooks/instagram","email_webhook":"/webhooks/email"}

@app.post("/triage")
def triage(message:Message):
    # Synchronous endpoint retained for demos; production ingestion uses queue + worker.
    from .worker import handle
    data=message.model_dump(); save_message(data); QUEUE.enqueue(data); update_queue_depth(QUEUE.size())
    return {"queued":True,"id":message.id,"queue_depth":QUEUE.size()}

@app.post("/queue")
def enqueue(message:Message):
    data=message.model_dump(); save_message(data); QUEUE.enqueue(data); update_queue_depth(QUEUE.size())
    return {"queued":True,"id":message.id,"queue_depth":QUEUE.size()}

@app.get("/decisions")
def decisions(limit:int=100): return {"items":recent_decisions(min(max(limit,1),500))}

@app.get("/metrics")
def metrics():
    from .metrics import summary
    return summary()

@app.get("/metrics/prometheus")
def prometheus_metrics(): return Response(prometheus_payload(),media_type="text/plain; version=0.0.4")

# ---------- Meta WhatsApp ----------
@app.get("/webhooks/whatsapp",response_class=PlainTextResponse)
def whatsapp_verify(request:Request):
    challenge=verify_meta_get(dict(request.query_params),os.getenv("WHATSAPP_VERIFY_TOKEN",""))
    if challenge is None: raise HTTPException(403,"Webhook verification failed")
    return challenge

@app.post("/webhooks/whatsapp")
async def whatsapp_webhook(request:Request):
    raw=await request.body()
    secret=os.getenv("WHATSAPP_APP_SECRET")
    if not verify_signature(raw,request.headers.get("X-Hub-Signature-256"),secret): raise HTTPException(403,"Invalid signature")
    payload=await request.json(); messages=whatsapp_messages(payload,os.getenv("WHATSAPP_BRAND","vitalis-wellness"))
    for m in messages:
        save_message(m); QUEUE.enqueue(m)
    update_queue_depth(QUEUE.size())
    return {"accepted":len(messages),"queued":len(messages)}

# ---------- Meta Instagram Messaging ----------
@app.get("/webhooks/instagram",response_class=PlainTextResponse)
def instagram_verify(request:Request):
    challenge=verify_meta_get(dict(request.query_params),os.getenv("INSTAGRAM_VERIFY_TOKEN",""))
    if challenge is None: raise HTTPException(403,"Webhook verification failed")
    return challenge

@app.post("/webhooks/instagram")
async def instagram_webhook(request:Request):
    raw=await request.body()
    secret=os.getenv("INSTAGRAM_APP_SECRET")
    if not verify_signature(raw,request.headers.get("X-Hub-Signature-256"),secret): raise HTTPException(403,"Invalid signature")
    payload=await request.json(); messages=instagram_messages(payload,os.getenv("INSTAGRAM_BRAND","hair-studio"))
    for m in messages:
        save_message(m); QUEUE.enqueue(m)
    update_queue_depth(QUEUE.size())
    return {"accepted":len(messages),"queued":len(messages)}

# ---------- Email inbound ----------
@app.post("/webhooks/email")
async def email_webhook(request:Request):
    """Inbound email adapter. Supports JSON webhooks and common form fields from inbound-email providers."""
    content_type=request.headers.get("content-type","")
    if "application/json" in content_type:
        payload=await request.json()
    else:
        form=await request.form(); payload=dict(form)
    text=payload.get("text") or payload.get("body") or payload.get("stripped-text") or payload.get("plain") or ""
    sender=payload.get("from") or payload.get("sender") or payload.get("from_email")
    subject=payload.get("subject") or ""
    if subject: text=f"Subject: {subject}\n{text}"
    mid=payload.get("id") or payload.get("message_id") or payload.get("Message-Id") or f"email-{uuid.uuid4().hex}"
    brand=os.getenv("EMAIL_BRAND","vitalis-wellness")
    m=normalize_message(str(mid),brand,"email",text,str(sender) if sender else None,payload)
    save_message(m); QUEUE.enqueue(m); update_queue_depth(QUEUE.size())
    return {"accepted":1,"queued":1,"id":m["id"]}
