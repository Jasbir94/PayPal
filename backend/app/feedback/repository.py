"""SQL persistence for snapshots, feedback labels, actions, and audit events."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
import os
import re
from contextlib import contextmanager
from threading import RLock
from uuid import uuid4
from sqlalchemy import (Column, Float, Index, Integer, MetaData, String, Table, Text,
    UniqueConstraint, create_engine, text)
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool
from backend.app.database.db import create_database_engine, normalize_database_url

_METADATA = MetaData()
_TABLES = {
    name: 'app_shield_' + name for name in (
        'prediction_snapshots', 'user_actions', 'fraud_labels', 'audit_events',
        'review_queue', 'shadow_predictions')
}
_SNAPSHOTS = Table(_TABLES['prediction_snapshots'], _METADATA,
    Column('attempt_id', String(80), primary_key=True),
    Column('prediction_timestamp', String(64), nullable=False),
    Column('snapshot_json', Text, nullable=False),
    Column('snapshot_hash', String(64), nullable=False))
_ACTIONS = Table(_TABLES['user_actions'], _METADATA,
    Column('action_id', String(36), primary_key=True),
    Column('attempt_id', String(80), nullable=False),
    Column('action', String(80), nullable=False),
    Column('created_at', String(64), nullable=False),
    Column('detail_json', Text, nullable=False))
_LABELS = Table(_TABLES['fraud_labels'], _METADATA,
    Column('label_id', String(36), primary_key=True),
    Column('attempt_id', String(80), nullable=False),
    Column('label', String(64), nullable=False),
    Column('source', String(64), nullable=False),
    Column('confidence', Float, nullable=False),
    Column('label_timestamp', String(64), nullable=False),
    Column('received_at', String(64), nullable=False),
    Column('note', Text))
_AUDIT = Table(_TABLES['audit_events'], _METADATA,
    Column('sequence', Integer, primary_key=True, autoincrement=True),
    Column('event_id', String(36), nullable=False, unique=True),
    Column('attempt_id', String(80), nullable=False),
    Column('event_type', String(80), nullable=False),
    Column('timestamp', String(64), nullable=False),
    Column('model_version', String(255)),
    Column('payload_json', Text, nullable=False),
    Column('previous_hash', String(64), nullable=False),
    Column('event_hash', String(64), nullable=False, unique=True))
_REVIEWS = Table(_TABLES['review_queue'], _METADATA,
    Column('attempt_id', String(80), primary_key=True),
    Column('status', String(32), nullable=False),
    Column('reason', Text, nullable=False),
    Column('created_at', String(64), nullable=False),
    Column('reviewed_at', String(64)),
    Column('outcome', String(64)),
    Column('note', Text))
_SHADOW = Table(_TABLES['shadow_predictions'], _METADATA,
    Column('shadow_id', String(36), primary_key=True),
    Column('attempt_id', String(80), nullable=False),
    Column('created_at', String(64), nullable=False),
    Column('model_version', String(255), nullable=False),
    Column('risk', Float, nullable=False),
    Column('calibrated_probability', Float),
    Column('decision', String(64), nullable=False),
    Column('features_json', Text, nullable=False),
    Column('holdout_fingerprint', String(255)))
Index('ix_app_shield_actions_attempt', _ACTIONS.c.attempt_id, _ACTIONS.c.created_at)
Index('ix_app_shield_labels_attempt', _LABELS.c.attempt_id, _LABELS.c.received_at)
Index('ix_app_shield_audit_attempt', _AUDIT.c.attempt_id, _AUDIT.c.sequence)
Index('ix_app_shield_shadow_created', _SHADOW.c.created_at, _SHADOW.c.model_version)


class _Result:
    def __init__(self, result):
        self.result = result

    @property
    def rowcount(self):
        return self.result.rowcount

    def fetchone(self):
        return self.result.mappings().first()

    def fetchall(self):
        return self.result.mappings().all()


class _Connection:
    def __init__(self, connection):
        self.connection = connection

    def execute(self, query, parameters=()):
        ignore_conflict = query.lstrip().upper().startswith('INSERT OR IGNORE INTO ')
        query = re.sub(r'\bINSERT\s+OR\s+IGNORE\s+INTO\b', 'INSERT INTO', query,
            count=1, flags=re.IGNORECASE)
        for old_name, new_name in _TABLES.items():
            query = re.sub(rf'\b{old_name}\b', new_name, query)
        if isinstance(parameters, dict):
            values = parameters
        else:
            position = 0
            def replace_placeholder(_match):
                nonlocal position
                name = f'p{position}'
                position += 1
                return ':' + name
            query = re.sub(r'\?', replace_placeholder, query)
            values = {f'p{index}': value for index, value in enumerate(parameters or ())}
        if ignore_conflict:
            query = query.rstrip().rstrip(';') + ' ON CONFLICT DO NOTHING'
        return _Result(self.connection.execute(text(query), values))


def _make_engine(path=None) -> tuple[Engine, str | None]:
    database_url = normalize_database_url(os.getenv('DATABASE_URL'))
    configured = path if path is not None else (database_url or os.getenv('APP_SHIELD_FEEDBACK_DB'))
    if configured == ':memory:':
        return create_engine('sqlite://', connect_args={'check_same_thread':False},
            poolclass=StaticPool), ':memory:'
    if configured:
        configured_text = str(configured)
        if '://' in configured_text:
            database_url = configured_text
        else:
            database_url = 'sqlite:///' + os.path.abspath(configured_text).replace('\\', '/')
    elif not database_url:
        return create_engine('sqlite://', connect_args={'check_same_thread':False},
            poolclass=StaticPool), ':memory:'
    return create_database_engine(database_url), None


class SnapshotConflict(ValueError):
    """A prediction-time snapshot already exists and is immutable."""


class FeedbackRepository:
    def __init__(self, path=None):
        self.engine, self.path = _make_engine(path)
        self._lock = RLock()
        self._initialize()

    @contextmanager
    def _database(self):
        with self.engine.begin() as connection:
            yield _Connection(connection)

    def _initialize(self):
        with self._lock:
            _METADATA.create_all(self.engine)

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
