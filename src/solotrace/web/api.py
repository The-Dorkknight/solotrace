# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""The editor's /api/... requests as one function, shared by the local server (server.py) and the
in-browser version (the page runs this same Python with Pyodide in a Web Worker, see static/worker.js).

``handle(session, method, path, query, body)`` returns ``(status, data, content_type, download_name)``.

WORK IN PROGRESS: many features may be broken.
"""
from __future__ import annotations

import base64
import json
from typing import Optional, Tuple

from .. import title as app_title
from .session import Session

Reply = Tuple[int, bytes, str, Optional[str]]


def _json(obj, code: int = 200) -> Reply:
    return code, json.dumps(obj).encode("utf-8"), "application/json", None


def _text(code: int, msg: str) -> Reply:
    return code, msg.encode("utf-8"), "text/plain", None


def handle(se: Session, method: str, path: str, query: Optional[dict] = None, body: Optional[dict] = None) -> Reply:
    q = query or {}
    body = body if isinstance(body, dict) else {}
    with se.lock:
        if method == "GET":
            return _get(se, path, q)
        if method == "POST":
            return _post(se, path, body)
    return _text(405, "method not allowed")


def _get(se: Session, p: str, q: dict) -> Reply:
    if p == "/api/state":
        from .. import demos
        if se.sync_mode:
            se.finish_fill_now()          # the in-browser version has no threads: do the full fill here
        return _json({"state": se.state(), "accepted": se.accepted(), "title": app_title(),
                      "path": se.path, "recent": se.recent_files(), "demos": list(demos.DEMOS),
                      "browser_only": se.sync_mode})
    if p == "/api/library":
        return _json({"tree": se.library_tree(q.get("q", "")), "mode": se.parts_mode, "quick": se.quick_list()})
    if p == "/api/part":
        return _json(se.part_preview(q.get("pid", "")))
    if p == "/api/menu":
        items = se.menu(float(q.get("x", 0)), float(q.get("y", 0)))
        return _json({"menu": items, "state": se.state()})
    if p.startswith("/api/export/"):
        kind = p[len("/api/export/"):]
        try:
            name, data, mime = se.export(kind, mirror=q.get("mirror", "1") == "1", layer=q.get("layer", "bottom"))
        except ValueError as exc:
            return _text(404, str(exc))
        return 200, data, mime, name
    return _text(404, "not found")


def _post(se: Session, p: str, body: dict) -> Reply:
    if p == "/api/cmd":
        name = str(body.get("name", ""))
        args = body.get("args") or {}
        try:
            out = se.cmd(name, args if isinstance(args, dict) else {})
        except Exception as exc:          # noqa: BLE001 - the page shows it, the editor lives on
            out = {"error": "%s failed: %s: %s" % (name, type(exc).__name__, exc)}
            se.touch()
        if name in ("hover", "probe_part"):
            return _json({"out": out})
        return _json({"out": out, "state": se.state()})
    if p == "/api/laser/preview":
        job, o, probs = se.laser_job(body.get("values") or {}, str(body.get("layer", "bottom")))
        if job is None:
            return _json({"error": "\n".join(probs)})
        png = se.laser_preview_png(job)
        return _json({"png": base64.b64encode(png).decode("ascii"), "summary": job.summary(),
                      "warnings": job.warnings,
                      "options": "%s, %g mm/min, %g%%, %g mm lines" % (o.mode, o.feed, o.power, o.line_interval)})
    if p == "/api/laser/gcode":
        kind = str(body.get("kind", "board"))
        if kind != "board":
            name, data, mime = se.laser_extra(kind, body.get("values") or {})
            return 200, data, mime, name
        job, o, probs = se.laser_job(body.get("values") or {}, str(body.get("layer", "bottom")))
        if job is None:
            return _json({"error": "\n".join(probs)}, 400)
        suffix = "_plane.gcode" if body.get("layer") == "top" else "_%s.gcode" % o.mode
        return 200, job.gcode.encode("utf-8"), "text/plain", se.file_name(suffix)
    return _text(404, "not found")
