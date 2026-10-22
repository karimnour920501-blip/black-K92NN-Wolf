import json
import os
import sqlite3
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from control_plane.core import ControlPlane
from control_plane.server import handler_factory

class ControlPlaneTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.cp=ControlPlane(os.path.join(self.temp.name,'test.sqlite3'))
    def tearDown(self):
        self.cp.close();self.temp.cleanup()
    def test_project_and_isolation(self):
        self.cp.add_project({'id':'a','name':'Alpha'},'tester')
        self.cp.add_project({'id':'b','name':'Beta'},'tester')
        self.cp.add_connector({'id':'g','project_id':'a','kind':'github'},'tester')
        self.assertEqual(len(self.cp.list_items('connectors','a')),1)
        self.assertEqual(len(self.cp.list_items('connectors','b')),0)
    def test_fail_closed_policy(self):
        self.cp.add_project({'id':'a','name':'Alpha'},'tester')
        self.assertEqual(self.cp.decide('a','deploy','tester'),'deny')
        self.cp.add_policy({'id':'p','project_id':'a','action':'deploy','decision':'approval_required'},'tester')
        self.assertEqual(self.cp.decide('a','deploy','tester'),'approval_required')
        self.assertEqual(self.cp.decide('b','deploy','tester'),'deny')
    def test_connector_cannot_store_secrets_or_enable(self):
        self.cp.add_project({'id':'a','name':'Alpha'},'tester')
        for item in ({'id':'x','project_id':'a','kind':'github','config':{'token':'secret'}},{'id':'x','project_id':'a','kind':'github','enabled':True}):
            with self.assertRaises(ValueError):self.cp.add_connector(item,'tester')
    def test_audit_chain_detects_tampering(self):
        self.cp.add_project({'id':'a','name':'Alpha'},'tester')
        self.assertTrue(self.cp.verify_audit())
        self.cp.db.execute("UPDATE audit SET actor='attacker' WHERE seq=1");self.cp.db.commit()
        self.assertFalse(self.cp.verify_audit())
    def test_foreign_key(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.cp.add_connector({'id':'g','project_id':'missing','kind':'github'},'tester')
    def test_http_auth_and_workflow(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),handler_factory(self.cp,'x'*40))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base=f'http://127.0.0.1:{server.server_port}'
        def request(path,body=None,auth=True):
            headers={'Content-Type':'application/json'}
            if auth:headers['Authorization']='Bearer '+'x'*40
            req=Request(base+path, data=json.dumps(body).encode() if body is not None else None,headers=headers)
            try:
                with urlopen(req,timeout=3) as res:return res.status,json.load(res)
            except HTTPError as e:return e.code,json.load(e)
        try:
            self.assertEqual(request('/projects',auth=False)[0],401)
            self.assertEqual(request('/projects',{'id':'a','name':'Alpha'})[0],201)
            self.assertEqual(request('/connectors',{'id':'g','project_id':'a','kind':'github'})[0],201)
            self.assertEqual(request('/evaluate',{'project_id':'a','action':'deploy'})[1]['decision'],'deny')
            self.assertTrue(request('/audit/verify')[1]['valid'])
            self.assertEqual(request('/projects')[1]['items'][0]['id'],'a')
        finally:server.shutdown();server.server_close();thread.join(timeout=3)

    def test_concurrent_writes_keep_audit_chain_valid(self):
        def register_batch(worker):
            for index in range(15):
                project_id=f'p-{worker}-{index}'
                self.cp.add_project({'id':project_id,'name':project_id},f'worker-{worker}')
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(register_batch,range(8)))
        self.assertEqual(len(self.cp.list_items('projects')),120)
        self.assertEqual(len(self.cp.list_items('audit')),120)
        self.assertTrue(self.cp.verify_audit())

if __name__=='__main__':unittest.main()
