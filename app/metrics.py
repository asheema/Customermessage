from __future__ import annotations
from prometheus_client import Counter, Histogram, Gauge, generate_latest
from threading import Lock

MESSAGES=Counter("triage_messages_total","Messages received",["channel"])
PROCESSED=Counter("triage_processed_total","Messages processed",["route"])
ERRORS=Counter("triage_errors_total","Processing errors",["channel"])
LATENCY=Histogram("triage_processing_seconds","Message processing latency")
QUEUE_DEPTH=Gauge("triage_queue_depth","Current queue depth")
HUMAN=Counter("triage_human_review_total","Messages routed to human review")
_LOCK=Lock(); _stats={"total":0,"automatic":0,"llm":0,"human":0,"errors":0,"latency_ms":[]}

def record(**event):
    channel=event.get("channel","unknown"); route=event.get("route","unknown")
    MESSAGES.labels(channel=channel).inc()
    if route in {"automatic","llm","human"}: PROCESSED.labels(route=route).inc()
    if route=="human": HUMAN.inc()
    if event.get("error"): ERRORS.labels(channel=channel).inc()
    if event.get("latency_ms") is not None: LATENCY.observe(float(event["latency_ms"])/1000)
    with _LOCK:
        if event.get("event")=="triage":
            _stats["total"]+=1
            if route in _stats: _stats[route]+=1
            _stats["latency_ms"].append(float(event.get("latency_ms",0)))
        if event.get("error"): _stats["errors"]+=1

def update_queue_depth(depth:int): QUEUE_DEPTH.set(depth)

def summary():
    with _LOCK:
        avg=sum(_stats["latency_ms"])/len(_stats["latency_ms"]) if _stats["latency_ms"] else 0
        return {"total":_stats["total"],"automatic":_stats["automatic"],"llm":_stats["llm"],"human":_stats["human"],"errors":_stats["errors"],"avg_latency_ms":round(avg,2),"estimated_llm_cost":0.0,"queue_depth":QUEUE_DEPTH._value.get()}

def prometheus_payload(): return generate_latest()
