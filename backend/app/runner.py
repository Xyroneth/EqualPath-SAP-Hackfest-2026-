"""Runs the LangGraph workflow in background threads so the UI can watch agents progress live."""
from __future__ import annotations

import threading
import traceback
import uuid

from langgraph.types import Command

from app.graph import NODE_META, PLANNED_ORDER, effective_values, get_graph
from app.providers.repository import get_repository, utcnow

_locks: dict[str, threading.Lock] = {}
_threads: dict[str, threading.Thread] = {}


def _config(run_id: str) -> dict:
    return {"configurable": {"thread_id": run_id}}


def _lock(run_id: str) -> threading.Lock:
    return _locks.setdefault(run_id, threading.Lock())


def _set_status(run_id: str, **fields) -> None:
    repo = get_repository()
    doc = repo.get("runs", run_id) or {}
    doc.update(fields, updated_at=utcnow())
    repo.put("runs", run_id, doc, owner_id=doc.get("candidate_id"))


def _execute(run_id: str, payload) -> None:
    graph = get_graph()
    try:
        _set_status(run_id, status="running", error=None)
        for _ in graph.stream(payload, _config(run_id), stream_mode="updates"):
            pass
        state = graph.get_state(_config(run_id))
        if state.next:
            interrupts = [i.value for t in state.tasks for i in t.interrupts]
            _set_status(run_id, status="waiting_for_human", waiting_for=interrupts[0]["checkpoint"] if interrupts else None)
        elif (state.values.get("final_review") or {}).get("decision") == "reject":
            _set_status(run_id, status="rejected", waiting_for=None)
        else:
            _set_status(run_id, status="completed", waiting_for=None)
    except Exception as exc:  # noqa: BLE001 - surface failure to the UI and audit log
        _set_status(run_id, status="failed", error=f"{type(exc).__name__}: {exc}", trace=traceback.format_exc()[-1500:])
    finally:
        _lock(run_id).release()


def _launch(run_id: str, payload, wait: bool) -> None:
    lock = _lock(run_id)
    if not lock.acquire(blocking=False):
        raise RuntimeError("run is already executing")
    _set_status(run_id, status="running")
    t = threading.Thread(target=_execute, args=(run_id, payload), daemon=True)
    _threads[run_id] = t
    t.start()
    if wait:
        t.join()


def start_run(candidate_id: str, job_id: str, actor: str, wait: bool = False) -> str:
    run_id = f"run-{uuid.uuid4().hex[:10]}"
    repo = get_repository()
    repo.put("runs", run_id, {"run_id": run_id, "candidate_id": candidate_id, "job_id": job_id, "created_at": utcnow(),
                              "status": "running", "started_by": actor}, owner_id=candidate_id)
    repo.append_audit(event_type="run_started", actor=actor, run_id=run_id, candidate_id=candidate_id,
                      summary="Career Orchestrator run started", details={"job_id": job_id})
    _launch(run_id, {"run_id": run_id, "candidate_id": candidate_id, "job_id": job_id}, wait)
    return run_id


def resume_run(run_id: str, value: dict, wait: bool = False) -> None:
    _launch(run_id, Command(resume=value), wait)


def wait_for(run_id: str, timeout: float = 60) -> None:
    t = _threads.get(run_id)
    if t:
        t.join(timeout)


def pending_interrupt(run_id: str) -> dict | None:
    state = get_graph().get_state(_config(run_id))
    for t in state.tasks:
        for i in t.interrupts:
            return i.value
    return None


def run_view(run_id: str) -> dict | None:
    doc = get_repository().get("runs", run_id)
    if doc is None:
        return None
    state = get_graph().get_state(_config(run_id))
    values = effective_values(run_id, dict(state.values or {}))
    timeline = values.pop("timeline", [])
    done = {t["node"] for t in timeline}
    interrupt = pending_interrupt(run_id) if state.next else None
    nodes = []
    for n in PLANNED_ORDER + (["await_evidence"] if "await_evidence" in done or (interrupt or {}).get("checkpoint") == "evidence_request" else []):
        agent, kind = NODE_META[n]
        if n in done:
            status = "completed"
        elif n in (state.next or ()):
            status = "running" if doc.get("status") == "running" else ("waiting_for_human" if kind == "human" else "pending")
        else:
            status = "pending"
        nodes.append({"node": n, "agent": agent, "kind": kind, "status": status})
    if doc.get("status") == "running" and not any(n["status"] == "running" for n in nodes):
        for n in nodes:
            if n["status"] == "pending":
                n["status"] = "running"
                break
    return {"run": doc, "values": values, "timeline": timeline, "nodes": nodes, "next": list(state.next or ()),
            "interrupt": interrupt}
