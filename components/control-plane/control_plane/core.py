import json, sqlite3, hashlib, datetime, threading
from pathlib import Path
from functools import wraps


def serialized(method):
    """Serialize access to this process-local SQLite connection."""
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)
    return wrapper

SCHEMA = '''
CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, name TEXT NOT NULL, source_url TEXT, status TEXT NOT NULL DEFAULT 'DISCOVERED');
CREATE TABLE IF NOT EXISTS connectors (id TEXT PRIMARY KEY, provider TEXT NOT NULL, mode TEXT NOT NULL CHECK(mode='read_only'), enabled INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS policies (id TEXT PRIMARY KEY, action TEXT NOT NULL, effect TEXT NOT NULL CHECK(effect IN ('allow','deny','approval')));
CREATE TABLE IF NOT EXISTS audit (seq INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL, target TEXT NOT NULL, outcome TEXT NOT NULL, prev_hash TEXT NOT NULL, entry_hash TEXT NOT NULL);
'''

class ControlPlane:
    def __init__(self, path):
        self._lock = threading.RLock()
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript(SCHEMA)
        self.db.commit()
    @serialized
    def close(self): self.db.close()
    @serialized
    def audit(self, actor, action, target, outcome):
        prev = self.db.execute('SELECT entry_hash FROM audit ORDER BY seq DESC LIMIT 1').fetchone()
        prev_hash = prev[0] if prev else 'GENESIS'
        ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        payload = json.dumps([ts,actor,action,target,outcome,prev_hash],separators=(',',':'))
        digest = hashlib.sha256(payload.encode()).hexdigest()
        self.db.execute('INSERT INTO audit(ts,actor,action,target,outcome,prev_hash,entry_hash) VALUES(?,?,?,?,?,?,?)',(ts,actor,action,target,outcome,prev_hash,digest))
        self.db.commit()
        return digest
    @serialized
    def register_project(self, id, name, source_url=None):
        self.db.execute('INSERT INTO projects(id,name,source_url) VALUES(?,?,?)',(id,name,source_url))
        self.db.commit(); self.audit('local','register_project',id,'success')
    @serialized
    def register_connector(self, id, provider):
        self.db.execute('INSERT INTO connectors(id,provider,mode,enabled) VALUES(?,?,?,0)',(id,provider,'read_only'))
        self.db.commit(); self.audit('local','register_connector',id,'disabled')
    @serialized
    def set_policy(self, id, action, effect):
        self.db.execute('INSERT INTO policies(id,action,effect) VALUES(?,?,?)',(id,action,effect))
        self.db.commit(); self.audit('local','set_policy',id,effect)
    @serialized
    def authorize(self, action):
        if action.startswith(('write','delete','deploy','publish','update','create')): return 'deny'
        row=self.db.execute('SELECT effect FROM policies WHERE action=?',(action,)).fetchone()
        return row[0] if row else 'deny'
    @serialized
    def inventory(self):
        return {table:[dict(zip([x[0] for x in self.db.execute('SELECT * FROM '+table).description],row)) for row in self.db.execute('SELECT * FROM '+table)] for table in ('projects','connectors','policies')}
    @serialized
    def verify_audit(self):
        prev='GENESIS'
        for ts,actor,action,target,outcome,prev_hash,entry_hash in self.db.execute('SELECT ts,actor,action,target,outcome,prev_hash,entry_hash FROM audit ORDER BY seq'):
            payload=json.dumps([ts,actor,action,target,outcome,prev_hash],separators=(',',':'))
            if prev_hash!=prev or hashlib.sha256(payload.encode()).hexdigest()!=entry_hash:return False
            prev=entry_hash
        return True

    # Project-scoped compatibility layer for the original 13-test API.
    @serialized
    def _ensure_scoped_schema(self):
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS scoped_connectors (
          id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
          kind TEXT NOT NULL, config TEXT NOT NULL DEFAULT '{}',
          enabled INTEGER NOT NULL DEFAULT 0 CHECK(enabled=0));
        CREATE TABLE IF NOT EXISTS scoped_policies (
          id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
          action TEXT NOT NULL, decision TEXT NOT NULL
          CHECK(decision IN ('deny','approval_required','allow')));
        ''')

    @serialized
    def add_project(self, item, actor):
        if set(item)-{'id','name','source_url'} or not all(k in item for k in ('id','name')):
            raise ValueError('invalid project')
        self.register_project(item['id'],item['name'],item.get('source_url'))

    @serialized
    def add_connector(self, item, actor):
        self._ensure_scoped_schema()
        if set(item)-{'id','project_id','kind','config','enabled'} or not all(k in item for k in ('id','project_id','kind')):
            raise ValueError('invalid connector')
        if item.get('enabled',False) is not False: raise ValueError('connectors must remain disabled')
        config=item.get('config',{})
        if not isinstance(config,dict) or config: raise ValueError('connector configuration and secrets not accepted')
        self.db.execute('INSERT INTO scoped_connectors(id,project_id,kind) VALUES(?,?,?)',
                        (item['id'],item['project_id'],item['kind']))
        self.db.commit()
        self.audit(actor,'add_connector',item['id'],'disabled')

    @serialized
    def add_policy(self, item, actor):
        self._ensure_scoped_schema()
        if set(item)!={'id','project_id','action','decision'}: raise ValueError('invalid policy')
        if item['decision'] not in ('allow','deny','approval_required'): raise ValueError('invalid decision')
        self.db.execute('INSERT INTO scoped_policies(id,project_id,action,decision) VALUES(?,?,?,?)',
                        (item['id'],item['project_id'],item['action'],item['decision']))
        self.db.commit()
        self.audit(actor,'add_policy',item['id'],item['decision'])

    @serialized
    def decide(self, project_id, action, actor):
        self._ensure_scoped_schema()
        row=self.db.execute('SELECT decision FROM scoped_policies WHERE project_id=? AND action=?',
                            (project_id,action)).fetchone()
        decision=row[0] if row else 'deny'
        # Even an explicit allow cannot authorize mutations in the read-only MVP.
        if action.startswith(('write','delete','deploy','publish','update','create')) and decision=='allow':
            return 'deny'
        return decision

    @serialized
    def list_items(self, table, project_id=None):
        self._ensure_scoped_schema()
        allowed={'projects':'projects','connectors':'scoped_connectors','policies':'scoped_policies','audit':'audit'}
        if table not in allowed: raise ValueError('invalid table')
        source=allowed[table]
        if project_id is not None and table in ('connectors','policies'):
            cursor=self.db.execute('SELECT * FROM '+source+' WHERE project_id=?',(project_id,))
        elif project_id is not None and table=='projects':
            cursor=self.db.execute('SELECT * FROM projects WHERE id=?',(project_id,))
        else:
            cursor=self.db.execute('SELECT * FROM '+source)
        keys=[d[0] for d in cursor.description]
        return [dict(zip(keys,row)) for row in cursor.fetchall()]
