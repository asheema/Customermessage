from __future__ import annotations
import time, os
from .queue import QUEUE
from .main import classify_with_optional_llm
from .db import init_db, save_decision, save_message, mark_message
from .metrics import update_queue_depth

def handle(message: dict):
    started=time.perf_counter()
    mid=message.get("id")
    try:
        init_db()
        save_message(message)
        result=classify_with_optional_llm(message,use_llm=True)
        result_dict=result.__dict__
        route="human" if result.human_review else ("llm" if any("AI-assisted" in x for x in result.reasons) else "automatic")
        latency=(time.perf_counter()-started)*1000
        save_decision(message,result_dict,route,os.getenv("OLLAMA_MODEL","none"),latency)
        return result_dict
    except Exception as exc:
        if mid: mark_message(mid,"failed")
        raise exc

def run_worker():
    init_db()
    print(f"Worker started; queue backend={QUEUE.backend}")
    while True:
        message=QUEUE.dequeue(timeout=5)
        update_queue_depth(QUEUE.size())
        if not message:
            continue
        try:
            handle(message)
            print(f"processed {message.get('id')}")
        except Exception as exc:
            print(f"failed {message.get('id')}: {exc}")
            time.sleep(1)

if __name__=="__main__": run_worker()
