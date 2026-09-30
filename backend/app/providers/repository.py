"""CandidateRepository: SQLite (default) and optional SAP HANA Cloud, plus an append-only audit log."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from app.config import Settings, get_settings

COLLECTIONS = ("candidates", "runs", "evidence_submissions", "review_tasks", "jd_rewrites", "sensitive")


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


class CandidateRepository(ABC):
    """Document-style storage so the SQLite and HANA implementations share one schema."""

    kind = "abstract"

    @abstractmethod
    def put(self, collection: str, doc_id: str, doc: dict, owner_id: str | None = None) -> None: ...

    @abstractmethod
    def get(self, collection: str, doc_id: str) -> dict | None: ...

    @abstractmethod
    def list(self, collection: str, owner_id: str | None = None) -> list[dict]: ...

    @abstractmethod
    def delete(self, collection: str, doc_id: str) -> None: ...

    @abstractmethod
    def delete_owner(self, owner_id: str) -> int:
        """Delete every document owned by a candidate. Audit events are kept (they hold no PII)."""

    @abstractmethod
    def _append_audit_row(self, row: dict) -> None: ...

    @abstractmethod
    def _last_audit_hash(self) -> str: ...

    @abstractmethod
    def audit_events(self, run_id: str | None = None, candidate_id: str | None = None) -> list[dict]: ...

    _audit_lock = threading.Lock()

    def append_audit(self, *, event_type: str, actor: str, run_id: str | None, candidate_id: str | None,
                     summary: str, details: dict | None = None) -> dict:
        """Immutable, hash-chained audit event. Details must never contain raw PII."""
        with self._audit_lock:
            prev = self._last_audit_hash()
            row = {
                "event_id": f"evt-{uuid.uuid4().hex[:12]}",
                "ts": utcnow(),
                "event_type": event_type,
                "actor": actor,
                "run_id": run_id,
                "candidate_id": candidate_id,
                "summary": summary,
                "details": details or {},
                "prev_hash": prev,
            }
            row["hash"] = hashlib.sha256((prev + _canonical({k: v for k, v in row.items() if k != "prev_hash"})).encode()).hexdigest()
            self._append_audit_row(row)
            return row

    def verify_audit_chain(self) -> dict:
        events = self.audit_events()
        prev = "GENESIS"
        for e in events:
            body = {k: e[k] for k in ("event_id", "ts", "event_type", "actor", "run_id", "candidate_id", "summary", "details")}
            expected = hashlib.sha256((prev + _canonical(body)).encode()).hexdigest()
            if e["prev_hash"] != prev or e["hash"] != expected:
                return {"valid": False, "events": len(events), "broken_at": e["event_id"]}
            prev = e["hash"]
        return {"valid": True, "events": len(events), "head": prev}


class SQLiteRepository(CandidateRepository):
    kind = "sqlite"

    def __init__(self, path: str):
        self.path = path
        self._local = threading.local()
        conn = self._conn()
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS documents (
                collection TEXT NOT NULL, doc_id TEXT NOT NULL, owner_id TEXT, body TEXT NOT NULL,
                updated_at TEXT NOT NULL, PRIMARY KEY (collection, doc_id));
            CREATE INDEX IF NOT EXISTS ix_documents_owner ON documents(owner_id);
            CREATE TABLE IF NOT EXISTS audit_events (
                seq INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT UNIQUE NOT NULL, ts TEXT NOT NULL,
                event_type TEXT NOT NULL, actor TEXT NOT NULL, run_id TEXT, candidate_id TEXT,
                summary TEXT NOT NULL, details TEXT NOT NULL, prev_hash TEXT NOT NULL, hash TEXT NOT NULL);
            CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit_events
                BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END;
            CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit_events
                BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END;
            """
        )
        conn.commit()

    def _conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self.path, check_same_thread=False, timeout=30)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn = conn
        return conn

    def put(self, collection, doc_id, doc, owner_id=None):
        conn = self._conn()
        conn.execute(
            "INSERT INTO documents(collection, doc_id, owner_id, body, updated_at) VALUES (?,?,?,?,?) "
            "ON CONFLICT(collection, doc_id) DO UPDATE SET body=excluded.body, owner_id=excluded.owner_id, updated_at=excluded.updated_at",
            (collection, doc_id, owner_id, _canonical(doc), utcnow()),
        )
        conn.commit()

    def get(self, collection, doc_id):
        row = self._conn().execute("SELECT body FROM documents WHERE collection=? AND doc_id=?", (collection, doc_id)).fetchone()
        return json.loads(row["body"]) if row else None

    def list(self, collection, owner_id=None):
        if owner_id:
            rows = self._conn().execute("SELECT body FROM documents WHERE collection=? AND owner_id=? ORDER BY updated_at", (collection, owner_id))
        else:
            rows = self._conn().execute("SELECT body FROM documents WHERE collection=? ORDER BY updated_at", (collection,))
        return [json.loads(r["body"]) for r in rows]

    def delete(self, collection, doc_id):
        conn = self._conn()
        conn.execute("DELETE FROM documents WHERE collection=? AND doc_id=?", (collection, doc_id))
        conn.commit()

    def delete_owner(self, owner_id):
        conn = self._conn()
        cur = conn.execute("DELETE FROM documents WHERE owner_id=?", (owner_id,))
        conn.commit()
        return cur.rowcount

    def _append_audit_row(self, row):
        conn = self._conn()
        conn.execute(
            "INSERT INTO audit_events(event_id, ts, event_type, actor, run_id, candidate_id, summary, details, prev_hash, hash) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (row["event_id"], row["ts"], row["event_type"], row["actor"], row["run_id"], row["candidate_id"],
             row["summary"], _canonical(row["details"]), row["prev_hash"], row["hash"]),
        )
        conn.commit()

    def _last_audit_hash(self):
        row = self._conn().execute("SELECT hash FROM audit_events ORDER BY seq DESC LIMIT 1").fetchone()
        return row["hash"] if row else "GENESIS"

    def audit_events(self, run_id=None, candidate_id=None):
        sql, args = "SELECT * FROM audit_events", []
        clauses = []
        if run_id:
            clauses.append("run_id=?"); args.append(run_id)
        if candidate_id:
            clauses.append("candidate_id=?"); args.append(candidate_id)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        rows = self._conn().execute(sql + " ORDER BY seq", args).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d.pop("seq", None)
            d["details"] = json.loads(d["details"])
            out.append(d)
        return out


class HANARepository(CandidateRepository):
    """SAP HANA Cloud adapter (hdbcli). Activated with REPOSITORY=hana plus HANA_* credentials.

    Uses the same document schema. Immutability of the audit table is enforced by granting the
    application user INSERT/SELECT only on AUDIT_EVENTS (see deploy/hana/schema.sql).
    """

    kind = "hana"

    def __init__(self, s: Settings):
        from hdbcli import dbapi  # optional dependency: pip install hdbcli

        self.schema = s.hana_schema
        self.conn = dbapi.connect(address=s.hana_host, port=s.hana_port, user=s.hana_user, password=s.hana_password,
                                  encrypt=True, sslValidateCertificate=True)
        self._lock = threading.Lock()

    def _exec(self, sql: str, args: tuple = ()):
        with self._lock:
            cur = self.conn.cursor()
            cur.execute(sql, args)
            try:
                rows = cur.fetchall()
            except Exception:  # noqa: BLE001 - hdbcli raises on fetch for DML
                rows = []
            self.conn.commit()
            return rows, cur.rowcount

    def put(self, collection, doc_id, doc, owner_id=None):
        self._exec(f'UPSERT "{self.schema}"."DOCUMENTS" VALUES (?,?,?,?,?) WITH PRIMARY KEY',
                   (collection, doc_id, owner_id, _canonical(doc), utcnow()))

    def get(self, collection, doc_id):
        rows, _ = self._exec(f'SELECT BODY FROM "{self.schema}"."DOCUMENTS" WHERE COLLECTION=? AND DOC_ID=?', (collection, doc_id))
        return json.loads(rows[0][0]) if rows else None

    def list(self, collection, owner_id=None):
        if owner_id:
            rows, _ = self._exec(f'SELECT BODY FROM "{self.schema}"."DOCUMENTS" WHERE COLLECTION=? AND OWNER_ID=? ORDER BY UPDATED_AT', (collection, owner_id))
        else:
            rows, _ = self._exec(f'SELECT BODY FROM "{self.schema}"."DOCUMENTS" WHERE COLLECTION=? ORDER BY UPDATED_AT', (collection,))
        return [json.loads(r[0]) for r in rows]

    def delete(self, collection, doc_id):
        self._exec(f'DELETE FROM "{self.schema}"."DOCUMENTS" WHERE COLLECTION=? AND DOC_ID=?', (collection, doc_id))

    def delete_owner(self, owner_id):
        _, n = self._exec(f'DELETE FROM "{self.schema}"."DOCUMENTS" WHERE OWNER_ID=?', (owner_id,))
        return n

    def _append_audit_row(self, row):
        self._exec(f'INSERT INTO "{self.schema}"."AUDIT_EVENTS" (EVENT_ID, TS, EVENT_TYPE, ACTOR, RUN_ID, CANDIDATE_ID, SUMMARY, DETAILS, PREV_HASH, HASH) '
                   "VALUES (?,?,?,?,?,?,?,?,?,?)",
                   (row["event_id"], row["ts"], row["event_type"], row["actor"], row["run_id"], row["candidate_id"],
                    row["summary"], _canonical(row["details"]), row["prev_hash"], row["hash"]))

    def _last_audit_hash(self):
        rows, _ = self._exec(f'SELECT TOP 1 HASH FROM "{self.schema}"."AUDIT_EVENTS" ORDER BY SEQ DESC')
        return rows[0][0] if rows else "GENESIS"

    def audit_events(self, run_id=None, candidate_id=None):
        sql = f'SELECT EVENT_ID, TS, EVENT_TYPE, ACTOR, RUN_ID, CANDIDATE_ID, SUMMARY, DETAILS, PREV_HASH, HASH FROM "{self.schema}"."AUDIT_EVENTS"'
        clauses, args = [], []
        if run_id:
            clauses.append("RUN_ID=?"); args.append(run_id)
        if candidate_id:
            clauses.append("CANDIDATE_ID=?"); args.append(candidate_id)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        rows, _ = self._exec(sql + " ORDER BY SEQ", tuple(args))
        keys = ["event_id", "ts", "event_type", "actor", "run_id", "candidate_id", "summary", "details", "prev_hash", "hash"]
        return [dict(zip(keys, r)) | {"details": json.loads(r[7])} for r in rows]


_repo: CandidateRepository | None = None
_repo_note: str = ""


def get_repository() -> CandidateRepository:
    global _repo, _repo_note
    if _repo is None:
        s = get_settings()
        if s.repository == "hana" and s.hana_configured():
            try:
                _repo = HANARepository(s)
                _repo_note = "Connected to SAP HANA Cloud"
            except Exception as exc:  # noqa: BLE001 - fall back to local persistence, never break the demo
                _repo_note = f"SAP HANA Cloud connection failed ({type(exc).__name__}); using SQLite"
        if _repo is None:
            _repo = SQLiteRepository(s.sqlite_path)
            _repo_note = _repo_note or "Local SQLite"
    return _repo


def repository_note() -> str:
    get_repository()
    return _repo_note


def reset_repository(repo: CandidateRepository | None = None) -> None:
    global _repo
    _repo = repo
