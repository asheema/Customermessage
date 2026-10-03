from __future__ import annotations
import json
from pathlib import Path

PATH=Path("feedback.jsonl")
def save_feedback(username, message_id, original_intent, corrected_intent, note=""):
    row={"username":username,"message_id":message_id,"original_intent":original_intent,"corrected_intent":corrected_intent,"note":note}
    with PATH.open("a",encoding="utf-8") as f: f.write(json.dumps(row,ensure_ascii=False)+"\n")
    return row

def all_feedback():
    if not PATH.exists(): return []
    out=[]
    for line in PATH.read_text(encoding="utf-8").splitlines():
        try: out.append(json.loads(line))
        except json.JSONDecodeError: pass
    return out
