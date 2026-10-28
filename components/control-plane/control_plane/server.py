import argparse
import hmac
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs
from .core import ControlPlane

IDENTIFIER = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}$')
KINDS = {'github','notion','google_drive','research','documents','cybersecurity','sql','templates'}

def handler_factory(cp, token):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass  # Avoid request data in access logs

        def reply(self, status, data):
            raw = json.dumps(data, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Content-Length',str(len(raw)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.end_headers()
            self.wfile.write(raw)

        def authenticated(self):
            provided = self.headers.get('Authorization','')
            valid = hmac.compare_digest(provided.encode(), ('Bearer '+token).encode())
            if not valid:
                self.reply(401, {'error':'unauthorized'})
            return valid

        def do_GET(self):
            if not self.authenticated(): return
            path = urlsplit(self.path).path
            params = parse_qs(urlsplit(self.path).query)
            if path == '/health': return self.reply(200, {'status':'ok'})
            if path == '/audit/verify': return self.reply(200, {'valid':cp.verify_audit()})
            tables = {'/projects':'projects','/connectors':'connectors','/policies':'policies','/audit':'audit'}
            if path in tables:
                return self.reply(200, {'items':cp.list_items(tables[path],params.get('project_id',[None])[0])})
            self.reply(404, {'error':'not_found'})

        def do_POST(self):
            if not self.authenticated(): return
            path = urlsplit(self.path).path
            if self.headers.get('Content-Type','').split(';')[0].strip() != 'application/json':
                return self.reply(415, {'error':'application_json_required'})
            try:
                length = int(self.headers.get('Content-Length','0'))
                if not 0 < length <= 16384: return self.reply(413, {'error':'invalid_body_size'})
                body = json.loads(self.rfile.read(length))
                if not isinstance(body,dict): raise ValueError('expected object')
                actor = 'local-admin'
                if path == '/projects':
                    check_fields(body, ('id','name'), ('id','name'))
                    check_id(body['id'])
                    if not isinstance(body['name'],str) or not 0 < len(body['name']) <= 120: raise ValueError('invalid name')
                    cp.add_project(body,actor)
                elif path == '/connectors':
                    check_fields(body, ('id','project_id','kind'), ('id','project_id','kind','config','enabled'))
                    check_id(body['id']);check_id(body['project_id'])
                    if body['kind'] not in KINDS: raise ValueError('unsupported connector kind')
                    cp.add_connector(body,actor)
                elif path == '/policies':
                    check_fields(body, ('id','project_id','action','decision'), ('id','project_id','action','decision'))
                    check_id(body['id']);check_id(body['project_id']);check_id(body['action'])
                    cp.add_policy(body,actor)
                elif path == '/evaluate':
                    check_fields(body, ('project_id','action'), ('project_id','action'))
                    check_id(body['project_id']);check_id(body['action'])
                    return self.reply(200,{'decision':cp.decide(body['project_id'],body['action'],actor)})
                else: return self.reply(404, {'error':'not_found'})
                self.reply(201,{'created':True})
            except (ValueError,KeyError,TypeError) as e:
                self.reply(400, {'error':'invalid_request','detail':str(e)[:160]})
            except Exception as e:
                if type(e).__name__ == 'IntegrityError': self.reply(409, {'error':'conflict_or_missing_parent'})
                else: self.reply(500, {'error':'internal_error'})
    return Handler

def check_id(value):
    if not isinstance(value,str) or not IDENTIFIER.fullmatch(value): raise ValueError('invalid identifier')

def check_fields(item, required, allowed):
    if set(item)-set(allowed) or set(required)-set(item): raise ValueError('unexpected or missing fields')

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--host',default='127.0.0.1')
    p.add_argument('--port',type=int,default=8765)
    p.add_argument('--db',default='control-plane.sqlite3')
    args=p.parse_args()
    token=os.getenv('CONTROL_PLANE_TOKEN','')
    if len(token) < 32: p.error('CONTROL_PLANE_TOKEN must be at least 32 characters')
    if args.host not in ('127.0.0.1','::1','localhost'): p.error('MVP binds to loopback only; do not expose without TLS and stronger identity controls')
    cp=ControlPlane(args.db)
    http=ThreadingHTTPServer((args.host,args.port),handler_factory(cp,token))
    print(f'Control Plane listening on {args.host}:{args.port}',flush=True)
    try: http.serve_forever()
    finally: http.server_close();cp.close()

if __name__ == '__main__': main()
