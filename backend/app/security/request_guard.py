"""ASGI payload-size and per-client request-rate guard for API abuse hygiene."""
from collections import OrderedDict, deque
import json
import time

class RequestGuardMiddleware:
    def __init__(self, app, max_body_bytes=65_536, rate_limit=120, window_seconds=60):
        self.app=app
        self.max_body_bytes=max_body_bytes
        self.rate_limit=rate_limit
        self.window_seconds=window_seconds
        self.requests=OrderedDict()

    async def _reject(self, scope, send, status, detail):
        payload=json.dumps({'detail':detail}).encode('utf-8')
        await send({'type':'http.response.start','status':status,'headers':[
            (b'content-type',b'application/json'),(b'content-length',str(len(payload)).encode())]})
        await send({'type':'http.response.body','body':payload})

    def _allowed(self, client_ip, now):
        recent=self.requests.get(client_ip)
        if recent is None:
            if len(self.requests)>=4096:
                self.requests.popitem(last=False)
            recent=deque()
            self.requests[client_ip]=recent
        else:
            self.requests.move_to_end(client_ip)
        while recent and now-recent[0]>=self.window_seconds:
            recent.popleft()
        if len(recent)>=self.rate_limit:
            return False
        recent.append(now)
        return True

    async def __call__(self, scope, receive, send):
        if scope['type']!='http' or not scope.get('path','').startswith('/api/v1/'):
            return await self.app(scope,receive,send)
        peer=scope.get('client')
        client_ip=peer[0] if peer else 'unknown-client'
        if not self._allowed(client_ip,time.monotonic()):
            return await self._reject(scope,send,429,'Request rate limit exceeded; retry later.')
        headers={key.lower():value for key,value in scope.get('headers',[])}
        try:
            declared=int(headers.get(b'content-length',b'0'))
        except ValueError:
            return await self._reject(scope,send,400,'Invalid Content-Length header.')
        if declared>self.max_body_bytes:
            return await self._reject(scope,send,413,'Request body exceeds the configured limit.')
        events=[]; total=0
        while True:
            event=await receive()
            events.append(event)
            if event['type']=='http.request':
                total+=len(event.get('body',b''))
                if total>self.max_body_bytes:
                    return await self._reject(scope,send,413,'Request body exceeds the configured limit.')
                if not event.get('more_body',False): break
            elif event['type']=='http.disconnect':
                return
        async def replay():
            return events.pop(0) if events else await receive()
        await self.app(scope,replay,send)
