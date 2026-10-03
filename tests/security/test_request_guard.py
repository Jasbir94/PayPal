import asyncio
import json
from backend.app.security.request_guard import RequestGuardMiddleware


def run_asgi(app, body=b'', client='127.0.0.1'):
    sent=[]
    async def receive():
        nonlocal body
        result={'type':'http.request','body':body,'more_body':False}
        body=b''
        return result
    async def send(message): sent.append(message)
    scope={'type':'http','path':'/api/v1/test','method':'POST','headers':[],
           'client':(client,1234)}
    asyncio.run(app(scope,receive,send))
    return sent


def test_oversized_request_is_rejected_before_application():
    reached=[]
    async def app(scope,receive,send): reached.append(True)
    sent=run_asgi(RequestGuardMiddleware(app,max_body_bytes=4),b'12345')
    assert sent[0]['status']==413
    assert not reached


def test_rate_limit_returns_429():
    async def app(scope,receive,send):
        await send({'type':'http.response.start','status':204,'headers':[]})
        await send({'type':'http.response.body','body':b''})
    guard=RequestGuardMiddleware(app,rate_limit=1)
    run_asgi(guard)
    sent=run_asgi(guard)
    assert sent[0]['status']==429
    assert json.loads(sent[1]['body'])['detail']
