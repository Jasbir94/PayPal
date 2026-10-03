"""Append-only SQLite persistence for snapshots, feedback labels, actions and audit events."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from contextlib import contextmanager
from threading import RLock
from uuid import uuid4
from backend.app.config.risk_config import PROJECT_ROOT


class SnapshotConflict(ValueError):
    """A prediction-time snapshot already exists and is immutable."""


class FeedbackRepository:
    def __init__(self, path: str | Path | None = None):
        configured = path or os.getenv('APP_SHIELD_FEEDBACK_DB')
        if str(configured)==':memory:':
            self.path=':memory:'
            self._database_target=f'file:feedback-{uuid4()}?mode=memory&cache=shared'
            self._uri=True
            self._anchor=sqlite3.connect(self._database_target,uri=True,check_same_thread=False)
        else:
            self.path = Path(configured) if configured else PROJECT_ROOT / 'data' / 'processed' / 'day9' / 'feedback.sqlite'
            self._database_target=str(self.path)
            self._uri=False
            self._anchor=None
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._initialize()

    def _connect(self):
        connection = sqlite3.connect(self._database_target, timeout=15,uri=self._uri)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys=ON')
        return connection

    @contextmanager
    def _database(self):
        db=self._connect()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _initialize(self):
        with self._lock, self._database() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS prediction_snapshots (
                    attempt_id TEXT PRIMARY KEY, prediction_timestamp TEXT NOT NULL,
                    snapshot_json TEXT NOT NULL, snapshot_hash TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS user_actions (
                    action_id TEXT PRIMARY KEY, attempt_id TEXT NOT NULL, action TEXT NOT NULL,
                    created_at TEXT NOT NULL, detail_json TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS idx_actions_attempt ON user_actions(attempt_id, created_at);
                CREATE TABLE IF NOT EXISTS fraud_labels (
                    label_id TEXT PRIMARY KEY, attempt_id TEXT NOT NULL, label TEXT NOT NULL,
                    source TEXT NOT NULL, confidence REAL NOT NULL, label_timestamp TEXT NOT NULL,
                    received_at TEXT NOT NULL, note TEXT);
                CREATE INDEX IF NOT EXISTS idx_labels_attempt ON fraud_labels(attempt_id, received_at);
                CREATE TABLE IF NOT EXISTS audit_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT UNIQUE NOT NULL,
                    attempt_id TEXT NOT NULL, event_type TEXT NOT NULL, timestamp TEXT NOT NULL,
                    model_version TEXT, payload_json TEXT NOT NULL, previous_hash TEXT NOT NULL,
                    event_hash TEXT UNIQUE NOT NULL);
                CREATE INDEX IF NOT EXISTS idx_audit_attempt ON audit_events(attempt_id, sequence);
                CREATE TABLE IF NOT EXISTS review_queue (
                    attempt_id TEXT PRIMARY KEY, status TEXT NOT NULL, reason TEXT NOT NULL,
                    created_at TEXT NOT NULL, reviewed_at TEXT, outcome TEXT, note TEXT);
                CREATE TABLE IF NOT EXISTS shadow_predictions (
                    shadow_id TEXT PRIMARY KEY, attempt_id TEXT NOT NULL, created_at TEXT NOT NULL,
                    model_version TEXT NOT NULL, risk REAL NOT NULL, calibrated_probability REAL,
                    decision TEXT NOT NULL, features_json TEXT NOT NULL, holdout_fingerprint TEXT);
                CREATE INDEX IF NOT EXISTS idx_shadow_created ON shadow_predictions(created_at, model_version);
            ''')

    @staticmethod
    def _json(value):
        return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, default=str)

    def append_audit(self, attempt_id: str, event_type: str, payload: dict | None = None,
                     model_version: str | None = None, timestamp: str | None = None) -> dict:
        created = timestamp or datetime.now(timezone.utc).isoformat()
        event_id = str(uuid4())
        payload_json = self._json(payload or {})
        with self._lock, self._database() as db:
            row = db.execute('SELECT event_hash FROM audit_events ORDER BY sequence DESC LIMIT 1').fetchone()
            previous_hash = row['event_hash'] if row else 'GENESIS'
            material = {'event_id': event_id, 'attempt_id': attempt_id, 'event_type': event_type,
                'timestamp': created, 'model_version': model_version, 'payload_json': payload_json,
                'previous_hash': previous_hash}
            event_hash = hashlib.sha256(self._json(material).encode('utf-8')).hexdigest()
            db.execute('INSERT INTO audit_events(event_id,attempt_id,event_type,timestamp,model_version,payload_json,previous_hash,event_hash) VALUES(?,?,?,?,?,?,?,?)',
                (event_id, attempt_id, event_type, created, model_version, payload_json, previous_hash, event_hash))
        return {**material, 'payload': payload or {}, 'event_hash': event_hash}

    def record_snapshot(self, snapshot: dict) -> dict:
        body = self._json(snapshot)
        digest = hashlib.sha256(body.encode('utf-8')).hexdigest()
        attempt_id = str(snapshot['payment_attempt_id'])
        timestamp = str(snapshot['prediction_timestamp'])
        with self._lock, self._database() as db:
            current = db.execute('SELECT snapshot_json,snapshot_hash FROM prediction_snapshots WHERE attempt_id=?', (attempt_id,)).fetchone()
            if current:
                if current['snapshot_hash'] != digest:
                    raise SnapshotConflict(f'Prediction snapshot for {attempt_id} is immutable.')
                return json.loads(current['snapshot_json'])
            db.execute('INSERT INTO prediction_snapshots VALUES(?,?,?,?)', (attempt_id, timestamp, body, digest))
        return snapshot

    def get_snapshot(self, attempt_id: str) -> dict | None:
        with self._lock, self._database() as db:
            row = db.execute('SELECT snapshot_json FROM prediction_snapshots WHERE attempt_id=?', (attempt_id,)).fetchone()
        return json.loads(row['snapshot_json']) if row else None

    def add_action(self, attempt_id: str, action: str, detail: dict | None = None,
                   created_at: str | None = None) -> dict:
        row = {'action_id': str(uuid4()), 'payment_attempt_id': attempt_id, 'action': action,
               'created_at': created_at or datetime.now(timezone.utc).isoformat(), 'detail': detail or {}}
        with self._lock, self._database() as db:
            db.execute('INSERT INTO user_actions VALUES(?,?,?,?,?)',
                (row['action_id'], attempt_id, action, row['created_at'], self._json(row['detail'])))
        self.append_audit(attempt_id, 'USER_ACTION_RECORDED', {'action': action}, timestamp=row['created_at'])
        return row

    def add_label(self, attempt_id: str, label: str, source: str, confidence: float,
                  label_timestamp: str | None = None, note: str | None = None) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        row = {'label_id': str(uuid4()), 'payment_attempt_id': attempt_id, 'fraud_label': label,
               'label_source': source, 'label_confidence': float(confidence),
               'label_timestamp': label_timestamp or now, 'received_at': now, 'note': note}
        with self._lock, self._database() as db:
            db.execute('INSERT INTO fraud_labels VALUES(?,?,?,?,?,?,?,?)',
                (row['label_id'], attempt_id, label, source, float(confidence), row['label_timestamp'], now, note))
        self.append_audit(attempt_id, 'LABEL_RECEIVED', {'fraud_label': label, 'label_source': source,
            'label_confidence': float(confidence), 'label_id': row['label_id']}, timestamp=now)
        return row

    def get_feedback(self, attempt_id: str) -> dict:
        with self._lock, self._database() as db:
            snapshot = db.execute('SELECT snapshot_json,snapshot_hash FROM prediction_snapshots WHERE attempt_id=?', (attempt_id,)).fetchone()
            actions = db.execute('SELECT * FROM user_actions WHERE attempt_id=? ORDER BY created_at,action_id', (attempt_id,)).fetchall()
            labels = db.execute('SELECT * FROM fraud_labels WHERE attempt_id=? ORDER BY received_at,label_id', (attempt_id,)).fetchall()
            events = db.execute('SELECT sequence,event_id,event_type,timestamp,model_version,payload_json,previous_hash,event_hash FROM audit_events WHERE attempt_id=? ORDER BY sequence', (attempt_id,)).fetchall()
        return {'payment_attempt_id': attempt_id,
            'prediction_snapshot': json.loads(snapshot['snapshot_json']) if snapshot else None,
            'prediction_snapshot_sha256': snapshot['snapshot_hash'] if snapshot else None,
            'user_actions': [{'action_id':r['action_id'],'action':r['action'],'created_at':r['created_at'],'detail':json.loads(r['detail_json'])} for r in actions],
            'fraud_labels': [{'label_id':r['label_id'],'label':r['label'],'source':r['source'],'confidence':r['confidence'],'label_timestamp':r['label_timestamp'],'received_at':r['received_at'],'note':r['note']} for r in labels],
            'audit_events': [{'sequence':r['sequence'],'event_id':r['event_id'],'event_type':r['event_type'],'timestamp':r['timestamp'],'model_version':r['model_version'],'payload':json.loads(r['payload_json']),'previous_hash':r['previous_hash'],'event_hash':r['event_hash']} for r in events]}

    def list_snapshots(self, limit: int = 5000) -> list[dict]:
        with self._lock, self._database() as db:
            rows = db.execute('SELECT snapshot_json FROM prediction_snapshots ORDER BY prediction_timestamp DESC LIMIT ?', (int(limit),)).fetchall()
        return [json.loads(r['snapshot_json']) for r in rows]

    def list_labeled_predictions(self) -> list[dict]:
        with self._lock, self._database() as db:
            rows = db.execute('''SELECT s.snapshot_json,l.label,l.source,l.confidence,l.label_timestamp,l.received_at
                FROM prediction_snapshots s JOIN fraud_labels l ON l.label_id=(
                SELECT l2.label_id FROM fraud_labels l2 WHERE l2.attempt_id=s.attempt_id
                ORDER BY l2.received_at DESC,l2.label_id DESC LIMIT 1)''').fetchall()
        return [{'snapshot':json.loads(r['snapshot_json']),'fraud_label':r['label'],'label_source':r['source'],
            'label_confidence':r['confidence'],'label_timestamp':r['label_timestamp'],'label_received_at':r['received_at']} for r in rows]

    def eligible_training_examples(self, now=None, maturity_days: int = 7,
                                   confidence_floor: float = .90) -> list[dict]:
        from backend.app.feedback.label_policy import training_eligibility
        rows = self.list_labeled_predictions()
        result=[]
        for row in rows:
            snapshot=row['snapshot']
            eligible,reason=training_eligibility(row['fraud_label'],row['label_source'],row['label_confidence'],
                snapshot['prediction_timestamp'],now=now,maturity_days=maturity_days)
            if eligible and row['label_confidence']>=confidence_floor:
                result.append({'payment_attempt_id':snapshot['payment_attempt_id'],**snapshot.get('features',{}),
                    'is_fraud':int(row['fraud_label'] in ('CONFIRMED_SCAM','CONFIRMED_MULE')),
                    'label':row['fraud_label'],'label_source':row['label_source'],'label_confidence':row['label_confidence']})
        return result

    def upsert_review(self, attempt_id: str, reason: str, created_at: str | None = None) -> dict:
        now=created_at or datetime.now(timezone.utc).isoformat()
        with self._lock,self._database() as db:
            db.execute('INSERT OR IGNORE INTO review_queue(attempt_id,status,reason,created_at) VALUES(?,?,?,?)',
                (attempt_id,'OPEN',reason,now))
            row=db.execute('SELECT * FROM review_queue WHERE attempt_id=?',(attempt_id,)).fetchone()
        return dict(row)

    def list_reviews(self, status: str | None = None) -> list[dict]:
        with self._lock,self._database() as db:
            rows=db.execute('SELECT * FROM review_queue'+(' WHERE status=?' if status else '')+' ORDER BY created_at DESC',
                (status,) if status else ()).fetchall()
        return [dict(r) for r in rows]

    def complete_review(self, attempt_id: str, outcome: str, note: str | None = None) -> dict | None:
        now=datetime.now(timezone.utc).isoformat()
        with self._lock,self._database() as db:
            changed=db.execute("UPDATE review_queue SET status='CLOSED',reviewed_at=?,outcome=?,note=? WHERE attempt_id=? AND status='OPEN'",
                (now,outcome,note,attempt_id)).rowcount
            row=db.execute('SELECT * FROM review_queue WHERE attempt_id=?',(attempt_id,)).fetchone()
        if changed:
            self.append_audit(attempt_id,'MANUAL_REVIEW_COMPLETED',{'review_outcome':outcome,'note_recorded':bool(note)},timestamp=now)
        return dict(row) if row else None

    def verify_audit_chain(self) -> dict:
        with self._lock,self._database() as db:
            rows=db.execute('SELECT * FROM audit_events ORDER BY sequence').fetchall()
        previous='GENESIS'
        for row in rows:
            material={'event_id':row['event_id'],'attempt_id':row['attempt_id'],'event_type':row['event_type'],
                'timestamp':row['timestamp'],'model_version':row['model_version'],'payload_json':row['payload_json'],
                'previous_hash':row['previous_hash']}
            expected=hashlib.sha256(self._json(material).encode('utf-8')).hexdigest()
            if row['previous_hash']!=previous or row['event_hash']!=expected:
                return {'valid':False,'verified_events':int(row['sequence'])-1,'failed_sequence':int(row['sequence'])}
            previous=row['event_hash']
        return {'valid':True,'verified_events':len(rows),'failed_sequence':None}

    def has_attempt(self, attempt_id: str) -> bool:
        with self._lock,self._database() as db:
            row=db.execute('SELECT 1 FROM prediction_snapshots WHERE attempt_id=? UNION SELECT 1 FROM audit_events WHERE attempt_id=? LIMIT 1',
                (attempt_id,attempt_id)).fetchone()
        return row is not None

    def aggregate_counts(self) -> dict:
        with self._lock,self._database() as db:
            actions=db.execute('SELECT COUNT(*) AS n FROM user_actions').fetchone()['n']
            labels=db.execute('SELECT COUNT(*) AS n FROM fraud_labels').fetchone()['n']
            reviews=db.execute('SELECT COUNT(*) AS n FROM review_queue').fetchone()['n']
            shadow=db.execute('SELECT COUNT(*) AS n FROM shadow_predictions').fetchone()['n']
        return {'user_actions':int(actions),'ground_truth_labels':int(labels),'review_items':int(reviews),
            'shadow_predictions':int(shadow)}

    def add_shadow_prediction(self, attempt_id: str, prediction: dict) -> dict:
        row={'shadow_id':str(uuid4()),'payment_attempt_id':attempt_id,
            'created_at':prediction.get('created_at') or datetime.now(timezone.utc).isoformat(),
            'model_version':str(prediction['model_version']),'risk':float(prediction['risk']),
            'calibrated_probability':prediction.get('calibrated_probability'),
            'decision':str(prediction['decision']),'features':prediction.get('features') or {},
            'holdout_fingerprint':prediction.get('holdout_fingerprint')}
        with self._lock,self._database() as db:
            db.execute('INSERT INTO shadow_predictions VALUES(?,?,?,?,?,?,?,?,?)',
                (row['shadow_id'],attempt_id,row['created_at'],row['model_version'],row['risk'],
                 row['calibrated_probability'],row['decision'],self._json(row['features']),row['holdout_fingerprint']))
        self.append_audit(attempt_id,'SHADOW_PREDICTION_RECORDED',
            {'model_version':row['model_version'],'risk':row['risk'],'decision':row['decision']},timestamp=row['created_at'])
        return row

    def list_shadow_predictions(self, limit: int = 5000) -> list[dict]:
        with self._lock,self._database() as db:
            rows=db.execute('SELECT * FROM shadow_predictions ORDER BY created_at DESC LIMIT ?',
                (int(limit),)).fetchall()
        return [{'shadow_id':r['shadow_id'],'payment_attempt_id':r['attempt_id'],'created_at':r['created_at'],
            'model_version':r['model_version'],'risk':r['risk'],'calibrated_probability':r['calibrated_probability'],
            'decision':r['decision'],'features':json.loads(r['features_json']),
            'holdout_fingerprint':r['holdout_fingerprint']} for r in rows]
