from __future__ import annotations
from collections import deque
from threading import Lock
import json, os, time

class LocalQueue:
    def __init__(self): self._q=deque(); self._lock=Lock()
    def enqueue(self,item):
        with self._lock: self._q.append(item)
    def dequeue(self, timeout=0):
        with self._lock: return self._q.popleft() if self._q else None
    def size(self):
        with self._lock: return len(self._q)
    @property
    def backend(self): return "local"

class RedisQueue:
    """Redis/Render Key Value backed job queue. Render Key Value is Redis-compatible."""
    def __init__(self,url:str,key:str="triage:queue"):
        import redis
        self.client=redis.from_url(url,decode_responses=True)
        self.key=key
    def enqueue(self,item): self.client.rpush(self.key,json.dumps(item,ensure_ascii=False))
    def dequeue(self,timeout=5):
        item=self.client.blpop(self.key,timeout=timeout)
        return json.loads(item[1]) if item else None
    def size(self): return int(self.client.llen(self.key))
    @property
    def backend(self): return "redis"

def build_queue():
    url=os.getenv("REDIS_URL")
    if url:
        try:
            q=RedisQueue(url); q.client.ping(); return q
        except Exception as exc:
            print(f"Redis unavailable, using local queue: {exc}")
    return LocalQueue()

QUEUE=build_queue()
