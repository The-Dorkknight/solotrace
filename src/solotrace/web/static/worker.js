// Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
// Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
// SoloTrace in the browser - WORK IN PROGRESS: MANY FEATURES MAY BE BROKEN
//
// Runs the SoloTrace Python editor (the same code the local server runs) inside the browser with
// Pyodide, in this Web Worker so the page stays responsive. The page sends {id, method, path,
// query, body}; the worker answers with what the local server would have sent. Settings,
// favourites, your own parts and the autosave live in the browser's IndexedDB (IDBFS), so they
// survive a reload. Nothing is sent anywhere: once Pyodide and the SoloTrace code have downloaded
// the editor works offline.
"use strict";

let py = null, api = null, session = null, ready = null, syncTimer = null;
const CFG = "/home/pyodide/.solotrace";

function persist(delay) {
  clearTimeout(syncTimer);
  syncTimer = setTimeout(() => { try { py.FS.syncfs(false, () => {}); } catch (e) { /* storage blocked */ } }, delay);
}

async function boot(opts) {
  self.postMessage({ type: "loading", text: "Downloading Python (Pyodide, about 12 MB the first time)..." });
  importScripts(opts.pyodide + "pyodide.js");
  py = await loadPyodide({ indexURL: opts.pyodide });
  self.postMessage({ type: "loading", text: "Starting SoloTrace..." });
  py.FS.mkdirTree(CFG);
  let stored = true;
  try {
    py.FS.mount(py.FS.filesystems.IDBFS, {}, CFG);
    await new Promise((res) => py.FS.syncfs(true, (err) => { if (err) stored = false; res(); }));
  } catch (e) { stored = false; }
  const zip = await (await fetch(opts.code)).arrayBuffer();
  py.unpackArchive(zip, "zip", { extractDir: "/home/pyodide/src" });
  py.globals.set("js_progress", (label, msg, frac) => self.postMessage({ type: "progress", label, msg, frac }));
  py.runPython(`
import sys
sys.path.insert(0, "/home/pyodide/src")
from solotrace.web.session import Session
from solotrace.web import api as _api
import json as _json
_session = Session(sync_mode=True)
_session.progress_hook = lambda label, msg, frac: js_progress(label, msg, frac)

def _handle(method, path, query, body):
    q = _json.loads(query) if query else {}
    b = _json.loads(body) if body else None
    code, data, ctype, name = _api.handle(_session, method, path, q, b)
    return code, bytes(data), ctype, name or ""
`);
  api = py.globals.get("_handle");
  self.postMessage({ type: "ready", stored });
}

self.onmessage = async (ev) => {
  const m = ev.data;
  if (m.type === "boot") {
    ready = boot(m).catch((e) => self.postMessage({ type: "failed", text: String(e && e.message || e) }));
    return;
  }
  await ready;
  if (m.type !== "req") return;
  let reply;
  try {
    const r = api(m.method, m.path, JSON.stringify(m.query || {}), m.body == null ? "" : JSON.stringify(m.body));
    const [code, data, ctype, name] = r.toJs();
    r.destroy();
    const bytes = data instanceof Uint8Array ? data : new Uint8Array(data);
    reply = { type: "res", id: m.id, status: code, ctype, name, data: bytes };
    self.postMessage(reply, [bytes.buffer]);
  } catch (e) {
    const t = new TextEncoder().encode(JSON.stringify({ out: { error: "The editor failed: " + (e && e.message || e) } }));
    self.postMessage({ type: "res", id: m.id, status: 500, ctype: "application/json", name: "", data: t }, [t.buffer]);
  }
  if (m.method === "POST" || m.path === "/api/state") persist(1500);
};
