from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
import hashlib, hmac, os


def normalize_message(message_id:str, brand:str, channel:str, text:str|None, sender:str|None=None, raw:dict[str,Any]|None=None):
    return {"id":message_id,"brand":brand or "Other","channel":channel,"text":text,"sender":sender,
            "received_at":datetime.now(timezone.utc).isoformat(),"raw_payload":raw or {}}

def whatsapp_messages(payload:dict[str,Any], brand:str="vitalis-wellness"):
    out=[]
    for entry in payload.get("entry",[]):
        for change in entry.get("changes",[]):
            value=change.get("value",{})
            for msg in value.get("messages",[]):
                if msg.get("type")!="text": continue
                mid=msg.get("id")
                out.append(normalize_message(mid,brand,"whatsapp",msg.get("text",{}).get("body"),msg.get("from"),payload))
    return out

def instagram_messages(payload:dict[str,Any], brand:str="hair-studio"):
    out=[]
    for entry in payload.get("entry",[]):
        for messaging in entry.get("messaging",[]):
            msg=messaging.get("message",{})
            if "text" not in msg: continue
            mid=msg.get("mid") or f"ig-{messaging.get('timestamp','')}-{messaging.get('sender',{}).get('id','')}"
            out.append(normalize_message(mid,brand,"instagram",msg.get("text"),str(messaging.get("sender",{}).get("id","")),payload))
    return out

def verify_meta_get(params:dict[str,str], expected_token:str):
    if params.get("hub.mode")=="subscribe" and params.get("hub.verify_token")==expected_token:
        return params.get("hub.challenge")
    return None

def verify_signature(raw:bytes, signature:str|None, secret:str|None)->bool:
    # In production, require the provider app secret. Unsigned delivery is only
    # allowed when explicitly enabled for local testing.
    if not secret:
        return os.getenv("ALLOW_UNSIGNED_WEBHOOKS", "false").lower() == "true"
    if not signature: return False
    provided=signature.removeprefix("sha256=")
    expected=hmac.new(secret.encode(),raw,hashlib.sha256).hexdigest()
    return hmac.compare_digest(provided,expected)
