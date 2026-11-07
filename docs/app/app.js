// Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
// Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
// SoloTrace web UI - WORK IN PROGRESS: MANY FEATURES MAY BE BROKEN
//
// The page is a thin client: every click goes to the local server (session.py), which answers
// with the whole picture (the "scene") and the side panel as data. The page only draws, pans,
// zooms and shows ghosts while the mouse moves; nothing about the board is decided here.
"use strict";

const COL = {
  bg: "#16301c", board: "#1b3d24", grid: "#27502f", copper: "#d79a4e", copper_dim: "#8a6a3c",
  hole: "#16301c", outline: "#e8f0e8", outline_dim: "#6f8f77", sel: "#35d0ff", air: "#f2e24a",
  rigid: "#ff6b3d", air_shadow: "#0b1a0f", pinlabel: "#ffe08a", jump: "#6fb7ff", drc: "#ff4040",
  ghost: "#9fe0ff", text: "#ffffff", hover: "#6f8f5a", fill: "#a8783a", fill_dim: "#5c4a2d",
  plane: "#2a4a3a", plane_cu: "#6d7a55", plane_cu_dim: "#4e5a44", via: "#e0c070", trace_prev: "#fff3b0",
  mirrored: "#ff4fd8",
};
const ISLAND_GRID = 0.635;

const $ = (id) => document.getElementById(id);
const canvas = $("board");
const ctx = canvas.getContext("2d");
const back = document.createElement("canvas");      // the still picture; the overlay goes on top
const bctx = back.getContext("2d");

let S = null;                 // the scene from the server
let PANEL = [];               // the side panel as widgets
const V = { scale: 8, ox: 40, oy: 40, mirror: false, showGrid: true };
let cursor = { x: 0, y: 0, sx: 0, sy: 0 };
let hoverNet = null, hoverHit = {};
let DR = null;                // {desc, start, moved} while the left button drags something
let pressPending = false, upWhilePending = null;
let pan = null;
let backKey = "";
let jobTimer = null;
let alertsQueue = [];
let alertOpen = false;
let shiftDown = false;
let libOpen = {};             // group / sub-group open state
let armedPid = null;
let lastHoverReq = 0, hoverInFlight = false, hoverQueued = null;

// ------------------------------------------------------------------ server (or the in-browser editor)
// Two ways to run: the local server (python3 src/main.py) answers fetch() itself; the in-browser
// version (GitHub Pages, window.SOLOTRACE_BROWSER set by its index.html) runs the same Python with
// Pyodide in worker.js, and xfetch() hands each request to that worker instead.
const BROWSER = window.SOLOTRACE_BROWSER || null;
let worker = null, workerReady = null, reqId = 0;
const pending = new Map();
function startWorker() {
  worker = new Worker(BROWSER.worker || "worker.js");
  workerReady = new Promise((resolve, reject) => {
    worker.onmessage = (ev) => {
      const m = ev.data;
      if (m.type === "loading") loadingText(m.text);
      else if (m.type === "ready") { loadingText(null); if (!m.stored) setTimeout(() => setStatus("Your browser is not letting this page store anything, so settings and the autosave last only until you close the tab."), 1500); resolve(); }
      else if (m.type === "failed") { loadingText("SoloTrace could not start in this browser: " + m.text + "\n\nTry a current Chrome, Edge, Firefox or Safari, or download SoloTrace and run it with Python."); reject(new Error(m.text)); }
      else if (m.type === "progress") showJob({ label: m.label, msg: m.msg, frac: m.frac, inline: true });
      else if (m.type === "res") {
        const cb = pending.get(m.id); pending.delete(m.id);
        if (cb) {
          const h = { "Content-Type": m.ctype };
          if (m.name) h["Content-Disposition"] = 'attachment; filename="' + m.name + '"';
          cb(new Response(new Blob([m.data], { type: m.ctype }), { status: m.status, headers: h }));
        }
      }
    };
  });
  worker.postMessage({ type: "boot", pyodide: BROWSER.pyodide, code: BROWSER.code || "solotrace-py.zip" });
}
function loadingText(t) {
  let el = document.getElementById("loading");
  if (t == null) { if (el) el.remove(); return; }
  if (!el) { el = document.createElement("div"); el.id = "loading"; document.body.appendChild(el); }
  el.textContent = t;
}
async function xfetch(url, opts) {
  if (!BROWSER) return fetch(url, opts);
  await workerReady;
  const u = new URL(url, "http://local/");
  const query = {}; u.searchParams.forEach((v, k) => { query[k] = v; });
  const method = (opts && opts.method) || "GET";
  if (u.pathname === "/api/ping" || u.pathname === "/api/quit") return new Response('{"ok":true}', { status: 200 });
  const body = opts && opts.body ? JSON.parse(opts.body) : null;
  return new Promise((resolve) => { const id = ++reqId; pending.set(id, resolve); worker.postMessage({ type: "req", id, method, path: u.pathname, query, body }); });
}
async function post(url, body) {
  const r = await xfetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
  if (!r.ok) throw new Error(url + ": " + r.status);
  return r.json();
}
async function api(name, args) {
  let j;
  try {
    j = await post("/api/cmd", { name, args: args || {} });
  } catch (e) {
    setStatus("The SoloTrace server did not answer (" + e.message + "). Is it still running?");
    return {};
  }
  if (j.state) applyState(j.state);
  handleOut(j.out || {}, name);
  return j.out || {};
}
async function getState() {
  try {
    const j = await (await xfetch("/api/state")).json();
    applyState(j.state);
    return j;
  } catch (e) {
    setStatus("The SoloTrace server did not answer. Is it still running?");
    return null;
  }
}
function applyState(st) {
  S = st.scene;
  PANEL = st.panel || [];
  document.title = S.title;
  setStatus(S.status);
  if (S.want_fit) fit();
  updateChrome();
  renderPanel();
  backKey = "";
  draw();
  for (const a of st.alerts || []) alertsQueue.push(a);
  showNextAlert();
  showJob(st.job);
  if (!S.fill_ready && !st.job) { clearTimeout(fillTimer); fillTimer = setTimeout(getState, 700); }
}
let fillTimer = null;
const INLINE_ERRORS = new Set(["apply_settings", "apply_islands", "apply_backplane", "save_part", "new_board"]);
function handleOut(out, name) {
  if (out.error && !INLINE_ERRORS.has(name)) showText("SoloTrace", out.error, true);
  if (out.dialog) openDialog(out.dialog);
  if (out.text) showText(out.text_title || "SoloTrace", out.text, false, out.download);
  if (out.drc) showDrc(out.drc);
  if (out.focus === "value") { const e = document.querySelector("#panel input[data-focus]"); if (e) { e.focus(); e.select(); } }
  if (name === "arm") armedPid = S && S.armed;
}

// ------------------------------------------------------------------ view maths
function w2s(x, y) { if (V.mirror) x = S.w - x; return [V.ox + x * V.scale, V.oy + (S.h - y) * V.scale]; }
function s2w(sx, sy) { let x = (sx - V.ox) / V.scale; const y = S.h - (sy - V.oy) / V.scale; if (V.mirror) x = S.w - x; return [x, y]; }
function snap(x, y, g) { g = g || S.grid; return [Math.round(x / g) * g, Math.round(y / g) * g]; }
function fit() {
  const cw = Math.max(100, canvas.clientWidth), ch = Math.max(100, canvas.clientHeight);
  V.scale = Math.min((cw - 60) / S.w, (ch - 60) / S.h);
  V.ox = (cw - S.w * V.scale) / 2; V.oy = (ch - S.h * V.scale) / 2;
  backKey = ""; draw();
}
function zoomAt(sx, sy, f) {
  const [wx, wy] = s2w(sx, sy);
  V.scale = Math.min(120, Math.max(1, V.scale * f));
  const mx = V.mirror ? S.w - wx : wx;
  V.ox = sx - mx * V.scale; V.oy = sy - (S.h - wy) * V.scale;
  backKey = ""; draw();
}
function centreOn(x, y) {
  V.scale = Math.max(V.scale, 14);
  const mx = V.mirror ? S.w - x : x;
  V.ox = canvas.clientWidth / 2 - mx * V.scale; V.oy = canvas.clientHeight / 2 - (S.h - y) * V.scale;
  backKey = ""; draw();
}
function snapDir(prev, cur) {
  const g = S.route_grid;
  const dx = cur[0] - prev[0], dy = cur[1] - prev[1];
  if (Math.abs(dx) < 1e-9 && Math.abs(dy) < 1e-9) return prev;
  const k = Math.round(Math.atan2(dy, dx) / (Math.PI / 4));
  const ux = Math.cos(k * Math.PI / 4), uy = Math.sin(k * Math.PI / 4);
  let L = dx * ux + dy * uy;
  if (k % 2 === 0) L = Math.round(L / g) * g; else L = Math.round(L / (g * Math.SQRT2)) * g * Math.SQRT2;
  return [prev[0] + ux * L, prev[1] + uy * L];
}
function islandAt(wx, wy) {
  for (let i = S.islands.length - 1; i >= 0; i--) {
    const isl = S.islands[i];
    if (isl.shape === "round") { if (Math.hypot(wx - isl.x, wy - isl.y) <= Math.min(isl.w, isl.h) / 2) return i; }
    else if (Math.abs(wx - isl.x) <= isl.w / 2 && Math.abs(wy - isl.y) <= isl.h / 2) return i;
  }
  return null;
}

// ------------------------------------------------------------------ drawing
function resize() {
  const r = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  for (const c of [canvas, back]) { c.width = Math.max(1, Math.round(r.width * dpr)); c.height = Math.max(1, Math.round(r.height * dpr)); }
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0); bctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  backKey = ""; if (S) draw();
}
function shape(c, s, fill, extra, dx, dy) {
  extra = extra || 0; dx = dx || 0; dy = dy || 0;
  c.fillStyle = fill; c.strokeStyle = fill;
  if (s.k === "c") {
    const a = w2s(s.a[0] + dx, s.a[1] + dy), b = w2s(s.b[0] + dx, s.b[1] + dy);
    const w = Math.max(1, (2 * s.r + extra) * V.scale);
    if (Math.abs(a[0] - b[0]) < .01 && Math.abs(a[1] - b[1]) < .01) {
      c.beginPath(); c.arc(a[0], a[1], w / 2, 0, Math.PI * 2); c.fill();
    } else {
      c.lineWidth = w; c.lineCap = "round"; c.beginPath(); c.moveTo(a[0], a[1]); c.lineTo(b[0], b[1]); c.stroke();
    }
  } else {
    c.beginPath();
    s.pts.forEach((p, i) => { const q = w2s(p[0] + dx, p[1] + dy); if (i) c.lineTo(q[0], q[1]); else c.moveTo(q[0], q[1]); });
    c.closePath(); c.fill();
    if (extra) { c.lineWidth = extra * V.scale; c.lineJoin = "round"; c.stroke(); }
  }
}
function line(c, a, b, col, w, dash) {
  c.strokeStyle = col; c.lineWidth = w; c.lineCap = "round"; c.setLineDash(dash || []);
  c.beginPath(); c.moveTo(a[0], a[1]); c.lineTo(b[0], b[1]); c.stroke(); c.setLineDash([]);
}
function selHit(tag) {
  const sel = S.sel; if (!tag) return false;
  if (tag[0] === "trace" && sel.trace === tag[1]) return true;
  if (tag[0] === "jpad" && sel.jumper === tag[1]) return true;
  if (tag[0] === "isl" && sel.island === tag[1]) return true;
  if (tag[0] === "via" && sel.via === tag[1]) return true;
  if (tag[0] === "pad" && sel.part === tag[1] && (sel.pin == null || sel.pin === tag[2])) return true;
  return false;
}
function drawBack() {
  const c = bctx, sc = V.scale, cw = canvas.clientWidth, ch = canvas.clientHeight;
  c.fillStyle = COL.bg; c.fillRect(0, 0, cw, ch);
  const [x0, y0] = w2s(0, S.h), [x1, y1] = w2s(S.w, 0);
  const xa = Math.min(x0, x1), xb = Math.max(x0, x1);
  c.fillStyle = "#0f2114"; c.fillRect(xa + 5, y0 + 5, xb - xa, y1 - y0);
  c.fillStyle = S.plane ? COL.plane : COL.board; c.fillRect(xa, y0, xb - xa, y1 - y0);
  c.strokeStyle = "#9bd0a6"; c.lineWidth = 2; c.strokeRect(xa, y0, xb - xa, y1 - y0);
  if (S.plane) {
    const pcol = V.mirror ? COL.plane_cu_dim : COL.plane_cu;
    const r = S.plane.rect, A = w2s(r[0], r[3]), B = w2s(r[2], r[1]);
    c.fillStyle = pcol; c.fillRect(Math.min(A[0], B[0]), A[1], Math.abs(B[0] - A[0]), B[1] - A[1]);
    for (const s of S.plane.cut) shape(c, s, COL.plane);
    for (const s of S.plane.fat) shape(c, s, pcol);
  }
  if (V.showGrid && sc >= 3) {
    const step = sc < 20 ? 2.54 : 1.27;
    c.fillStyle = COL.grid;
    const nx = Math.floor(S.w / step + 1e-6), ny = Math.floor(S.h / step + 1e-6);
    for (let i = 0; i <= nx; i++) {
      const gx = i * step, sx = V.ox + (V.mirror ? S.w - gx : gx) * sc;
      if (sx < -2 || sx > cw + 2) continue;
      for (let j = 0; j <= ny; j++) { const sy = V.oy + (S.h - j * step) * sc; if (sy < -2 || sy > ch + 2) continue; c.fillRect(sx - 1, sy - 1, 2, 2); }
    }
  }
  const dim = !V.mirror;
  if (S.fill) {
    const r = S.fill.rect, A = w2s(r[0], r[3]), B = w2s(r[2], r[1]);
    c.fillStyle = dim ? COL.fill_dim : COL.fill; c.fillRect(Math.min(A[0], B[0]), A[1], Math.abs(B[0] - A[0]), B[1] - A[1]);
    for (const s of S.fill.cut) shape(c, s, COL.board);
    for (const s of S.fill.fat) shape(c, s, dim ? COL.copper_dim : COL.copper);
  }
  const selnet = S.sel.net;
  for (const s of S.copper) if (selHit(s.tag) || (selnet && s.net === selnet)) shape(c, s, COL.sel, 0.5);
  if (hoverNet && !DR) for (const s of S.copper) if (s.net === hoverNet) shape(c, s, COL.hover, 0.35);
  if (sc >= 5) for (const p of S.parts) if (p.pinlabels.length) drawPinLabels(c, p);
  const cu = dim ? COL.copper_dim : COL.copper;
  for (const s of S.copper) shape(c, s, cu);
  for (const pts of S.rigid) for (let i = 0; i + 1 < pts.length; i++) line(c, w2s(...pts[i]), w2s(...pts[i + 1]), COL.rigid, 2, [6, 3]);
  const si_ = S.sel.island;
  if (si_ != null && si_ < S.islands.length) {
    const isl = S.islands[si_], a = w2s(isl.x - isl.w / 2, isl.y - isl.h / 2), e = w2s(isl.x + isl.w / 2, isl.y + isl.h / 2);
    c.strokeStyle = COL.sel; c.lineWidth = 1; c.setLineDash([4, 3]); c.strokeRect(Math.min(a[0], e[0]), Math.min(a[1], e[1]), Math.abs(e[0] - a[0]), Math.abs(e[1] - a[1])); c.setLineDash([]);
    for (const [hx, hy] of [[a[0], a[1]], [a[0], e[1]], [e[0], a[1]], [e[0], e[1]]]) { c.fillStyle = "#fff"; c.fillRect(hx - 5, hy - 5, 10, 10); c.lineWidth = 2; c.strokeRect(hx - 5, hy - 5, 10, 10); }
  }
  if (S.sel.trace != null) {
    const t = S.copper.filter(s => s.tag && s.tag[0] === "trace" && s.tag[1] === S.sel.trace && s.tag[2] === (S.sel.seg || 0));
    for (const s of t) if (s.k === "c") line(c, w2s(...s.a), w2s(...s.b), COL.trace_prev, Math.max(2, s.r * 2 * sc * 0.45));
    for (const s of S.copper) if (s.tag && s.tag[0] === "trace" && s.tag[1] === S.sel.trace && s.k === "c") {
      for (const p of [s.a, s.b]) { const q = w2s(...p); c.strokeStyle = COL.sel; c.lineWidth = 1; c.strokeRect(q[0] - 2.5, q[1] - 2.5, 5, 5); }
    }
  }
  c.fillStyle = COL.hole;
  for (const [x, y, d] of S.drills) { const [sx, sy] = w2s(x, y); c.beginPath(); c.arc(sx, sy, Math.max(1, d / 2 * sc), 0, Math.PI * 2); c.fill(); }
  S.vias.forEach(([x, y], vi) => {
    const [sx, sy] = w2s(x, y), r = Math.max(3, S.via_pad / 2 * sc), col = S.sel.via === vi ? COL.sel : COL.via;
    line(c, [sx - r, sy], [sx + r, sy], col, 1); line(c, [sx, sy - r], [sx, sy + r], col, 1);
    c.strokeStyle = col; c.lineWidth = 1; c.beginPath(); c.arc(sx, sy, r, 0, Math.PI * 2); c.stroke();
  });
  for (const j of S.jumpers) line(c, w2s(j[0], j[1]), w2s(j[2], j[3]), COL.jump, Math.max(1.5, 0.5 * sc), [6, 4]);
  const ocol = V.mirror ? COL.outline_dim : COL.outline;
  for (const p of S.parts) {
    const selp = S.sel.part === p.ref;
    if (p.mirrored) {
      // a mirrored part must stand out: thick dashed pink frame round its body plus a tag
      const [mx0, my0, mx1, my1] = p.court, a = w2s(mx0, my0), e = w2s(mx1, my1);
      c.strokeStyle = COL.mirrored; c.lineWidth = 3; c.setLineDash([8, 4]);
      c.strokeRect(Math.min(a[0], e[0]) - 3, Math.min(a[1], e[1]) - 3, Math.abs(e[0] - a[0]) + 6, Math.abs(e[1] - a[1]) + 6);
      c.setLineDash([]);
      c.fillStyle = "rgba(255, 79, 216, 0.12)"; c.fillRect(Math.min(a[0], e[0]), Math.min(a[1], e[1]), Math.abs(e[0] - a[0]), Math.abs(e[1] - a[1]));
      const [tx] = w2s((mx0 + mx1) / 2, my1), ty = Math.min(a[1], e[1]);
      c.font = "bold " + Math.max(8, Math.min(12, Math.floor(sc))) + "px system-ui, sans-serif"; c.textAlign = "center"; c.textBaseline = "top";
      const tag = p.under ? "MIRRORED (under board)" : "MIRRORED (top side)", tw = c.measureText(tag).width;
      c.fillStyle = COL.mirrored; c.fillRect(tx - tw / 2 - 4, ty + 4, tw + 8, Math.max(8, Math.min(12, Math.floor(sc))) + 5);
      c.fillStyle = "#fff"; c.fillText(tag, tx, ty + 6);
    }
    const pcol = selp ? COL.sel : (p.mirrored ? COL.mirrored : ocol);
    for (const sg of p.segs) line(c, w2s(sg[0], sg[1]), w2s(sg[2], sg[3]), pcol, selp || p.mirrored ? 1.8 : 1);
    if (sc >= 4) {
      const [cx0, cy0, cx1, cy1] = p.court;
      c.font = Math.max(7, Math.min(13, Math.floor(sc * 1.2))) + "px system-ui, sans-serif";
      c.fillStyle = COL.text; c.textAlign = "center";
      if (p.pinlabels.length || Math.min(cx1 - cx0, cy1 - cy0) < 4) { const [tx, ty] = w2s((cx0 + cx1) / 2, cy1); c.textBaseline = "bottom"; c.fillText(p.label, tx, ty - 2); }
      else { const [tx, ty] = w2s((cx0 + cx1) / 2, (cy0 + cy1) / 2); c.textBaseline = "middle"; c.fillText(p.label, tx, ty); }
    }
    if (p.locked) { const a = w2s(p.x, p.y); c.font = "bold 9px system-ui, sans-serif"; c.fillStyle = "#ff9"; c.textAlign = "center"; c.textBaseline = "middle"; c.fillText("L", a[0], a[1] - 10); }
  }
  if (S.show_air !== false) for (const [net, x1, y1, x2, y2, rig] of S.airwires) {
    const a = w2s(x1, y1), e = w2s(x2, y2); let w = selnet === net ? 3 : 2; if (rig) w += 1;
    line(c, a, e, COL.air_shadow, w + 3); line(c, a, e, rig ? COL.rigid : COL.air, w);
  }
  for (const [mx, my] of S.marks) { const [sx, sy] = w2s(mx, my); c.strokeStyle = COL.drc; c.lineWidth = 2; c.beginPath(); c.arc(sx, sy, 10, 0, Math.PI * 2); c.stroke(); }
}
function drawPinLabels(c, p) {
  const sc = V.scale;
  let size = Math.max(7, Math.min(12, Math.floor(sc * 0.9)));
  const room = p.pinlabels[0].room;
  if (room >= 0) {
    const roomPx = room * sc, longest = Math.max(1, ...p.pinlabels.map(l => l.t.length));
    size = Math.max(6, Math.min(size, Math.floor(roomPx / (0.9 * longest))));
    if (roomPx < 3 * 0.9 * 6) return;
  }
  c.font = "bold " + size + "px system-ui, sans-serif";
  for (const l of p.pinlabels) {
    const sp = w2s(l.x, l.y), sl = w2s(l.x + l.vx * l.off, l.y + l.vy * l.off);
    const dx = sl[0] - sp[0], dy = sl[1] - sp[1];
    if (Math.abs(dx) >= Math.abs(dy)) { c.textAlign = dx > 0 ? "left" : "right"; c.textBaseline = "middle"; }
    else { c.textAlign = "center"; c.textBaseline = dy > 0 ? "top" : "bottom"; }
    c.fillStyle = "#10230f"; c.fillText(l.t, sl[0] + 1, sl[1] + 1);
    c.fillStyle = COL.pinlabel; c.fillText(l.t, sl[0], sl[1]);
  }
}
function draw() {
  if (!S) return;
  const key = [S.rev, V.scale, V.ox, V.oy, V.mirror, V.showGrid, hoverNet, !!DR, JSON.stringify(S.sel)].join("|");
  if (key !== backKey) { drawBack(); backKey = key; }
  ctx.clearRect(0, 0, canvas.clientWidth, canvas.clientHeight);
  ctx.drawImage(back, 0, 0, canvas.clientWidth, canvas.clientHeight);
  drawOverlay(ctx);
}
function drawOverlay(c) {
  const sc = V.scale, wx = cursor.x, wy = cursor.y;
  if (DR && DR.moved) {
    const d = DR.desc;
    if (d.ref) {
      const p = S.parts.find(q => q.ref === d.ref); if (!p) return;
      const [nx, ny] = snap(wx + d.dx, wy + d.dy), ddx = nx - p.x, ddy = ny - p.y;
      const gcol = probeHits.length ? COL.drc : COL.ghost;
      for (const s of S.copper) if (s.tag && s.tag[0] === "pad" && s.tag[1] === d.ref) shape(c, s, gcol, 0, ddx, ddy);
      for (const sg of p.segs) line(c, w2s(sg[0] + ddx, sg[1] + ddy), w2s(sg[2] + ddx, sg[3] + ddy), gcol, 1);
      for (const [hx, hy] of probeHits) { const q = w2s(hx, hy); c.strokeStyle = COL.drc; c.lineWidth = 3; c.beginPath(); c.arc(q[0], q[1], 11, 0, Math.PI * 2); c.stroke(); }
    } else if (d.draw_island) {
      const [x1, y1] = snap(wx, wy, ISLAND_GRID), a = w2s(d.draw_island[0], d.draw_island[1]), e = w2s(x1, y1);
      c.strokeStyle = COL.ghost; c.lineWidth = 2; c.setLineDash([6, 3]); c.strokeRect(Math.min(a[0], e[0]), Math.min(a[1], e[1]), Math.abs(e[0] - a[0]), Math.abs(e[1] - a[1])); c.setLineDash([]);
      c.fillStyle = COL.ghost; c.font = "bold 12px system-ui, sans-serif"; c.textAlign = "left"; c.textBaseline = "top";
      c.fillText(Math.max(1, Math.abs(x1 - d.draw_island[0])).toPrecision(3) + " x " + Math.max(1, Math.abs(y1 - d.draw_island[1])).toPrecision(3) + " mm", e[0] + 10, e[1] + 10);
    } else if (d.island != null) {
      const isl = S.islands[d.island]; if (!isl) return;
      let x, y, w, h;
      if (d.resize) { const [ax, ay] = d.resize, [cx, cy] = snap(wx, wy, ISLAND_GRID); w = Math.max(1, Math.abs(cx - ax)); h = Math.max(1, Math.abs(cy - ay)); x = ax + (cx >= ax ? w / 2 : -w / 2); y = ay + (cy >= ay ? h / 2 : -h / 2); }
      else { [x, y] = snap(wx + d.dx, wy + d.dy, ISLAND_GRID); w = isl.w; h = isl.h; }
      const a = w2s(x - w / 2, y - h / 2), e = w2s(x + w / 2, y + h / 2);
      c.strokeStyle = COL.ghost; c.lineWidth = 2; c.setLineDash([6, 3]);
      if (isl.shape === "round") { c.beginPath(); c.ellipse((a[0] + e[0]) / 2, (a[1] + e[1]) / 2, Math.abs(e[0] - a[0]) / 2, Math.abs(e[1] - a[1]) / 2, 0, 0, Math.PI * 2); c.stroke(); }
      else c.strokeRect(Math.min(a[0], e[0]), Math.min(a[1], e[1]), Math.abs(e[0] - a[0]), Math.abs(e[1] - a[1]));
      c.setLineDash([]);
    } else if (d.via != null) {
      const [x, y] = snap(wx + d.dx, wy + d.dy, ISLAND_GRID), q = w2s(x, y), r = Math.max(3, S.via_pad / 2 * sc);
      c.strokeStyle = COL.ghost; c.lineWidth = 2; c.beginPath(); c.arc(q[0], q[1], r, 0, Math.PI * 2); c.stroke();
    } else if (d.trace != null) {
      const off = [wx - d.start[0], wy - d.start[1]], a = d.base[d.seg], b = d.base[d.seg + 1];
      if (a && b) line(c, w2s(a[0] + off[0], a[1] + off[1]), w2s(b[0] + off[0], b[1] + off[1]), COL.ghost, Math.max(2, d.basew[d.seg] * sc), [8, 4]);
    }
    return;
  }
  const t = S.tool;
  if (t === "island") {
    if (islandAt(wx, wy) == null) {
      const [x, y] = snap(wx, wy, ISLAND_GRID), n = S.island_new, a = w2s(x - n.w / 2, y - n.h / 2), e = w2s(x + n.w / 2, y + n.h / 2);
      c.fillStyle = COL.ghost;
      if (n.shape === "round") { c.beginPath(); c.ellipse((a[0] + e[0]) / 2, (a[1] + e[1]) / 2, Math.abs(e[0] - a[0]) / 2, Math.abs(e[1] - a[1]) / 2, 0, 0, Math.PI * 2); c.fill(); }
      else c.fillRect(Math.min(a[0], e[0]), Math.min(a[1], e[1]), Math.abs(e[0] - a[0]), Math.abs(e[1] - a[1]));
    }
  } else if (t === "place" && S.ghost) {
    const [x, y] = snap(wx, wy);
    const gcol = S.arm_mirror ? COL.mirrored : COL.ghost;
    for (const s of S.ghost.shapes) shape(c, s, gcol, 0, x, y);
    c.fillStyle = COL.hole;
    for (const [ox, oy, dd] of S.ghost.drills) { const q = w2s(ox + x, oy + y); c.beginPath(); c.arc(q[0], q[1], Math.max(1, dd / 2 * sc), 0, Math.PI * 2); c.fill(); }
    for (const sg of S.ghost.segs) line(c, w2s(sg[0] + x, sg[1] + y), w2s(sg[2] + x, sg[3] + y), gcol, 1);
    if (S.arm_mirror) { const q = w2s(x, y); c.fillStyle = COL.mirrored; c.font = "bold 12px system-ui, sans-serif"; c.textAlign = "left"; c.textBaseline = "bottom"; c.fillText("MIRRORED (Shift+M)", q[0] + 12, q[1] - 12); }
  } else if (t === "wire" && S.pending_pin) {
    const a = w2s(...S.pending_pin), e = w2s(wx, wy), rig = shiftDown || S.rigid_next;
    line(c, a, e, COL.air_shadow, 6); line(c, a, e, rig ? COL.rigid : COL.air, 3, [8, 4]);
    c.fillStyle = rig ? COL.rigid : COL.air; c.font = "bold 12px system-ui, sans-serif"; c.textAlign = "left"; c.textBaseline = "middle";
    c.fillText(rig ? "rigid" : "Shift = rigid", e[0] + 12, e[1] - 12);
  } else if (t === "trace" && S.trace_pts.length) {
    const seq = S.trace_pts.concat([snapDir(S.trace_pts[S.trace_pts.length - 1], [wx, wy])]);
    for (let i = 0; i + 1 < seq.length; i++) line(c, w2s(...seq[i]), w2s(...seq[i + 1]), COL.trace_prev, Math.max(2, S.trace_w * sc));
  } else if (t === "cut" && S.cut_start) {
    const [sx, sy] = w2s(...S.cut_start.p);
    line(c, [sx - 6, sy - 6], [sx + 6, sy + 6], COL.drc, 3); line(c, [sx - 6, sy + 6], [sx + 6, sy - 6], COL.drc, 3);
  } else if (t === "jumper" && S.jump_start) {
    line(c, w2s(...S.jump_start), w2s(wx, wy), COL.jump, 1.5, [6, 4]);
  }
}

// ------------------------------------------------------------------ mouse and keys
function evW(e) { const r = canvas.getBoundingClientRect(); const sx = e.clientX - r.left, sy = e.clientY - r.top; const [x, y] = s2w(sx, sy); return { sx, sy, x, y }; }
canvas.addEventListener("contextmenu", e => e.preventDefault());
canvas.addEventListener("mousedown", async e => {
  closePopup();
  canvas.focus();
  if (!S) return;
  const p = evW(e);
  if (e.button === 1 || e.button === 2) { pan = { sx: p.sx, sy: p.sy, ox: V.ox, oy: V.oy, moved: false, button: e.button }; return; }
  if (e.button !== 0) return;
  DR = null; pressPending = true; upWhilePending = null;
  const out = await api("press", { x: p.x, y: p.y, shift: e.shiftKey, scale: V.scale });
  pressPending = false;
  if (out.drag) {
    // the mouse may have moved on while the server answered: count that movement too
    const far = (q) => Math.abs(q.sx - p.sx) + Math.abs(q.sy - p.sy) > 3;
    DR = { desc: out.drag, start: [p.sx, p.sy], moved: far(cursor) };
    if (DR.moved) backKey = "";
    if (upWhilePending) { const u = upWhilePending; upWhilePending = null; if (far(u)) DR.moved = true; finishDrag(u); }
    else draw();
  } else if (upWhilePending) { const u = upWhilePending; upWhilePending = null; wireRelease(u); }
});
window.addEventListener("mousemove", e => {
  if (!S) return;
  shiftDown = e.shiftKey;
  const p = evW(e);
  cursor = { x: p.x, y: p.y, sx: p.sx, sy: p.sy };
  $("cursor").textContent = "X " + p.x.toFixed(2) + "  Y " + p.y.toFixed(2) + " mm";
  if (pan) {
    if (Math.abs(p.sx - pan.sx) + Math.abs(p.sy - pan.sy) > 4 || pan.moved) {
      pan.moved = true; V.ox = pan.ox + p.sx - pan.sx; V.oy = pan.oy + p.sy - pan.sy; canvas.style.cursor = "grabbing"; backKey = ""; draw();
    }
    return;
  }
  if (DR) {
    if (!DR.moved && Math.abs(p.sx - DR.start[0]) + Math.abs(p.sy - DR.start[1]) > 3) { DR.moved = true; backKey = ""; }
    if (DR.moved) { draw(); if (DR.desc.ref) probePart(DR.desc.ref, p.x + DR.desc.dx, p.y + DR.desc.dy); }
    return;
  }
  if (pressPending) return;
  if (["place", "wire", "trace", "jumper", "cut", "island"].includes(S.tool)) draw();
  if (["select", "wire", "trace", "trim", "cut"].includes(S.tool)) requestHover(p.x, p.y);
});
window.addEventListener("mouseup", async e => {
  if (!S) return;
  const p = evW(e);
  if (pan) {
    const was = pan; pan = null; canvas.style.cursor = "crosshair";
    if (!was.moved && was.button === 2) contextMenu(p);
    return;
  }
  if (e.button !== 0) return;
  if (pressPending) { upWhilePending = p; return; }
  if (DR) finishDrag(p); else wireRelease(p);
});
function finishDrag(p) {
  const d = DR; DR = null; backKey = ""; probeHits = []; probeKey = "";
  if (d && (d.moved || d.desc.draw_island)) api("drag_to", { x: p.x, y: p.y }); else draw();
}
function wireRelease(p) {
  // press on one pin, drag, let go on another: that is a wire too
  if (S.tool === "wire" && S.pending_pin) {
    const a = w2s(...S.pending_pin);
    if (Math.abs(p.sx - a[0]) + Math.abs(p.sy - a[1]) > 8 && Math.hypot(p.sx - a[0], p.sy - a[1]) > 8) api("press", { x: p.x, y: p.y, shift: shiftDown, scale: V.scale });
  }
}
canvas.addEventListener("dblclick", e => { if (!S) return; const p = evW(e); api("double", { x: p.x, y: p.y }); });
canvas.addEventListener("wheel", e => { if (!S) return; e.preventDefault(); const p = evW(e); zoomAt(p.sx, p.sy, e.deltaY < 0 ? 1.15 : 1 / 1.15); }, { passive: false });
// live collision check while a part is dragged: the server says where its pads would hit another net
let probeBusy = false, probeNext = null, probeHits = [], probeKey = "";
async function probePart(ref, x, y) {
  const g = S.grid, key = Math.round(x / g) + "," + Math.round(y / g);
  if (key === probeKey) return;
  if (probeBusy) { probeNext = [ref, x, y]; return; }
  probeBusy = true; probeKey = key;
  try {
    const j = await post("/api/cmd", { name: "probe_part", args: { ref, x, y } });
    probeHits = (j.out && j.out.hits) || [];
    if (DR) { setStatus(ref + (probeHits.length ? ": " + probeHits.length + " COLLISION(S) here, shown red. Let go somewhere clear." : ": no collisions here.")); draw(); }
  } catch (e) { /* next move tries again */ }
  probeBusy = false;
  if (probeNext) { const q = probeNext; probeNext = null; probePart(q[0], q[1], q[2]); }
}
async function requestHover(x, y) {
  const now = Date.now();
  if (hoverInFlight) { hoverQueued = [x, y]; return; }
  if (now - lastHoverReq < 60) { hoverQueued = [x, y]; setTimeout(() => { if (hoverQueued && !hoverInFlight) { const q = hoverQueued; hoverQueued = null; requestHover(q[0], q[1]); } }, 70); return; }
  lastHoverReq = now; hoverInFlight = true;
  try {
    const j = await post("/api/cmd", { name: "hover", args: { x, y, scale: V.scale } });
    const net = j.out.net || null; hoverHit = j.out.hit || {};
    if (net !== hoverNet) { hoverNet = net; backKey = ""; draw(); $("hovernet").textContent = net ? "net " + net : ""; }
    if (S.tool === "select") canvas.style.cursor = (hoverHit.trace != null || (hoverHit.part && hoverHit.pin == null)) ? "move" : "default";
    else if (S.tool === "trim" || S.tool === "cut") canvas.style.cursor = hoverHit.trace != null ? "crosshair" : "not-allowed";
    else canvas.style.cursor = "crosshair";
  } catch (e) { /* the next move tries again */ }
  hoverInFlight = false;
  if (hoverQueued) { const q = hoverQueued; hoverQueued = null; requestHover(q[0], q[1]); }
}
canvas.tabIndex = 0;
document.addEventListener("keydown", e => {
  if (!S) return;
  const tag = (e.target.tagName || "").toLowerCase();
  if (!$("modal-back").hidden) { if (e.key === "Escape") closeModal(); return; }
  if (tag === "input" || tag === "textarea" || tag === "select") { if (e.key === "Escape") e.target.blur(); return; }
  const k = e.key, ctrl = e.ctrlKey || e.metaKey;
  const tools = { s: "select", p: "place", w: "wire", t: "trace", x: "trim", c: "cut", j: "jumper", i: "island", v: "via" };
  if (ctrl && k.toLowerCase() === "z") { e.preventDefault(); api("undo"); }
  else if (ctrl && k.toLowerCase() === "y") { e.preventDefault(); api("redo"); }
  else if (ctrl && k.toLowerCase() === "d") { e.preventDefault(); api("duplicate"); }
  else if (ctrl && k.toLowerCase() === "s") { e.preventDefault(); saveBoard(); }
  else if (ctrl && k.toLowerCase() === "o") { e.preventDefault(); $("file-open").click(); }
  else if (!ctrl && tools[k.toLowerCase()] && !e.shiftKey) api("tool", { name: tools[k.toLowerCase()] });
  else if (k === "Escape") { closePopup(); api("escape"); }
  else if (k === "Delete" || k === "Backspace") { if (S.tool === "trace" && S.trace_pts.length) api("trace_backup"); else api("delete"); }
  else if (k === "Enter") { if (S.tool === "trace") api("finish_trace"); }
  else if (k.toLowerCase() === "r") api("rotate", { step: e.shiftKey ? -90 : 90 });
  else if (k.toLowerCase() === "f") fit();
  else if (k === "M" && e.shiftKey) api("mirror");
  else if (k.toLowerCase() === "m") toggleMirror();
  else if (k.startsWith("Arrow")) { e.preventDefault(); const d = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, 1], ArrowDown: [0, -1] }[k]; api("nudge", { dx: d[0], dy: d[1], big: e.shiftKey }); }
  else return;
  e.preventDefault();
});
document.addEventListener("keyup", e => { shiftDown = e.shiftKey; });
function toggleMirror() { V.mirror = !V.mirror; setStatus("Viewing the " + (V.mirror ? "COPPER (solder)" : "COMPONENT") + " side"); backKey = ""; draw(); }

// ------------------------------------------------------------------ chrome (tool bar, status)
function setStatus(t) { $("status").textContent = t || ""; }
function updateChrome() {
  document.querySelectorAll(".tool").forEach(b => b.classList.toggle("active", b.dataset.tool === S.tool));
  $("btn-undo").disabled = !S.can_undo; $("btn-redo").disabled = !S.can_redo;
  $("stamp").textContent = "SoloTrace v" + S.version + " (Built " + S.build + ") WIP";
  const rb = $("route-badge");
  if (S.unrouted < 0) { rb.textContent = "no nets yet"; rb.className = "badge"; }
  else if (S.unrouted) { rb.textContent = S.unrouted + " to route"; rb.className = "badge"; }
  else { rb.textContent = "all routed"; rb.className = "badge ok"; }
  setModeButton(S.parts_mode);
  if (S.armed !== armedPid) { armedPid = S.armed; markArmed(); }
}
function showJob(job) {
  const box = $("job");
  if (job && job.inline) {      // in-browser version: the job runs inside the request; no polling, no cancel
    box.hidden = false; $("job-cancel").hidden = true; $("job-bar").value = job.frac * 100;
    setStatus(job.label + ": " + job.msg + "  (working in your browser: the page answers again when it is done)");
    return;
  }
  if (job) { box.hidden = false; $("job-cancel").hidden = false; $("job-bar").value = job.frac * 100; setStatus(job.label + ": " + job.msg); clearTimeout(jobTimer); jobTimer = setTimeout(getState, 400); }
  else box.hidden = true;
}
$("job-cancel").onclick = () => api("cancel_job");
document.querySelectorAll(".tool").forEach(b => b.onclick = () => api("tool", { name: b.dataset.tool }));
$("btn-undo").onclick = () => api("undo"); $("btn-redo").onclick = () => api("redo");
$("btn-fit").onclick = fit; $("btn-mirror").onclick = toggleMirror;
$("btn-route").onclick = () => api("auto_route"); $("btn-drc").onclick = () => api("show_drc");

// ------------------------------------------------------------------ parts list
const MODE_ICONS = {
  tht: '<path d="M5 12a10 10 0 0 1 20 0v2H5z" fill="#2b2b2b"/><rect x="5" y="11" width="20" height="3" fill="#2b2b2b"/>' +
       '<rect x="8" y="14" width="3" height="15" fill="#e6e9ec"/><rect x="13.5" y="14" width="3" height="15" fill="#e6e9ec"/><rect x="19" y="14" width="3" height="15" fill="#e6e9ec"/><rect x="7" y="5" width="2" height="6" fill="#6d6d6d"/>',
  smd: '<rect x="9" y="7" width="12" height="16" fill="#2b2b2b"/><rect x="9" y="7" width="12" height="2" fill="#4a4a4a"/>' +
       '<rect x="3" y="10" width="6" height="3" fill="#e6e9ec"/><rect x="3" y="18" width="6" height="3" fill="#e6e9ec"/><rect x="21" y="14" width="6" height="3" fill="#e6e9ec"/><rect x="11" y="10" width="2" height="2" fill="#fff"/>',
};
function setModeButton(mode) {
  const other = mode === "smd" ? "tht" : "smd";
  $("mode-icon").innerHTML = MODE_ICONS[other];
  $("mode-text").textContent = other === "smd" ? "SMD parts" : "Through-hole parts";
  $("mode-btn").title = mode === "smd"
    ? "The list shows SMD parts now. Click to go back to the through-hole parts (the normal ones with legs through the board)."
    : "Click to swap the list for the common large SMD parts (0603 to 2512 chips, SOT-23, SOT-223, SOIC, DPAK, SMA/SMB diodes, tantalum and electrolytic caps). SMD parts sit on the COPPER side; press M to see the board as you solder it.";
}
$("mode-btn").onclick = async () => { await api("parts_mode", { mode: S.parts_mode === "smd" ? "tht" : "smd" }); loadLibrary(); };
let searchTimer = null;
$("search").addEventListener("input", () => { clearTimeout(searchTimer); searchTimer = setTimeout(loadLibrary, 150); });
async function loadLibrary() {
  const q = $("search").value.trim();
  const j = await (await xfetch("/api/library?q=" + encodeURIComponent(q))).json();
  const tree = $("tree"); tree.innerHTML = "";
  for (const g of j.tree) {
    const gd = document.createElement("div"); gd.className = "grp" + ((q || libOpen["g:" + g.name]) ? "" : " closed");
    const row = document.createElement("div"); row.className = "row";
    row.innerHTML = '<span class="arrow">' + (gd.classList.contains("closed") ? "&#9656;" : "&#9662;") + "</span>" + groupIcon(g.name) + "<span>" + esc(g.name) + "</span>";
    row.onclick = () => { gd.classList.toggle("closed"); libOpen["g:" + g.name] = !gd.classList.contains("closed"); row.querySelector(".arrow").innerHTML = gd.classList.contains("closed") ? "&#9656;" : "&#9662;"; };
    gd.appendChild(row);
    const kids = document.createElement("div"); kids.className = "kids";
    for (const sub of g.subs) {
      let holder = kids;
      if (sub.name) {
        const sd = document.createElement("div"); const key = "s:" + g.name + ":" + sub.name;
        sd.className = "sub" + ((q || libOpen[key] || g.subs.length === 1) ? "" : " closed");
        const srow = document.createElement("div"); srow.className = "row";
        srow.innerHTML = '<span class="arrow">' + (sd.classList.contains("closed") ? "&#9656;" : "&#9662;") + "</span>" + esc(sub.name);
        srow.onclick = () => { sd.classList.toggle("closed"); libOpen[key] = !sd.classList.contains("closed"); srow.querySelector(".arrow").innerHTML = sd.classList.contains("closed") ? "&#9656;" : "&#9662;"; };
        sd.appendChild(srow); const sk = document.createElement("div"); sk.className = "kids"; sd.appendChild(sk); kids.appendChild(sd); holder = sk;
      }
      for (const p of sub.parts) {
        const pd = document.createElement("div"); pd.className = "part" + (p.id === armedPid ? " armed" : ""); pd.dataset.pid = p.id; pd.textContent = p.name; pd.title = p.name;
        pd.onclick = () => pickPart(p.id);
        holder.appendChild(pd);
      }
    }
    gd.appendChild(kids); tree.appendChild(gd);
  }
  const quick = $("quick"); quick.innerHTML = '<option value="">Favourites &amp; recent...</option>';
  for (const p of j.quick) { const o = document.createElement("option"); o.value = p.id; o.textContent = p.name; quick.appendChild(o); }
}
function groupIcon(name) {
  const icons = {
    "Chips (DIP)": '<rect x="5" y="2" width="8" height="14" fill="#2b2b2b"/><rect x="3" y="3" width="3" height="2" fill="#d9822b"/><rect x="3" y="7" width="3" height="2" fill="#d9822b"/><rect x="3" y="11" width="3" height="2" fill="#d9822b"/><rect x="12" y="3" width="3" height="2" fill="#d9822b"/><rect x="12" y="7" width="3" height="2" fill="#d9822b"/><rect x="12" y="11" width="3" height="2" fill="#d9822b"/>',
    "Transistors & regulators": '<path d="M3 9a6 6 0 0 1 12 0v1H3z" fill="#2b2b2b"/><rect x="4" y="10" width="2" height="7" fill="#9aa3aa"/><rect x="8" y="10" width="2" height="7" fill="#9aa3aa"/><rect x="12" y="10" width="2" height="7" fill="#9aa3aa"/>',
    "Resistors, diodes & inductors": '<rect x="0" y="8" width="18" height="2" fill="#9aa3aa"/><rect x="4" y="5" width="10" height="8" fill="#d8b77e"/><rect x="6" y="5" width="1" height="8" fill="#8b4513"/><rect x="9" y="5" width="1" height="8" fill="#111"/><rect x="12" y="5" width="1" height="8" fill="#d62828"/>',
    "Capacitors": '<rect x="4" y="1" width="10" height="13" fill="#2f6db3"/><rect x="11" y="1" width="2" height="13" fill="#d6e4f5"/><rect x="6" y="14" width="1" height="4" fill="#9aa3aa"/><rect x="11" y="14" width="1" height="4" fill="#9aa3aa"/>',
    "LEDs": '<circle cx="9" cy="7" r="6" fill="#e63946"/><circle cx="7" cy="5" r="2" fill="#ffb3b8"/><rect x="6" y="12" width="1" height="6" fill="#9aa3aa"/><rect x="11" y="12" width="1" height="6" fill="#9aa3aa"/>',
    "Pots, switches & crystals": '<circle cx="9" cy="9" r="7" fill="#3a7bd5"/><circle cx="9" cy="9" r="3" fill="#fff"/><rect x="8" y="2" width="2" height="6" fill="#fff"/>',
    "Connectors": '<rect x="1" y="4" width="16" height="10" fill="#2a9d8f"/><circle cx="4" cy="9" r="2.2" fill="#e9f5f3"/><circle cx="9" cy="9" r="2.2" fill="#e9f5f3"/><circle cx="14" cy="9" r="2.2" fill="#e9f5f3"/>',
    "Board bits": '<circle cx="9" cy="9" r="7.5" fill="#d9822b"/><circle cx="9" cy="9" r="2.5" fill="#eef1f4"/>',
    "SMD": '<rect x="5" y="5" width="8" height="8" fill="#2b2b2b"/><rect x="1" y="5" width="4" height="2" fill="#d9822b"/><rect x="1" y="8" width="4" height="2" fill="#d9822b"/><rect x="1" y="11" width="4" height="2" fill="#d9822b"/><rect x="13" y="5" width="4" height="2" fill="#d9822b"/><rect x="13" y="8" width="4" height="2" fill="#d9822b"/><rect x="13" y="11" width="4" height="2" fill="#d9822b"/>',
    "My parts": '<path d="M3 15 L14 4 L16 6 L5 17 Z" fill="#b8691c"/><rect x="2" y="15" width="2" height="2" fill="#2b2b2b"/>',
  };
  return '<svg class="gicon" viewBox="0 0 18 18">' + (icons[name] || icons["My parts"]) + "</svg>";
}
function markArmed() { document.querySelectorAll("#tree .part").forEach(p => p.classList.toggle("armed", p.dataset.pid === armedPid)); }
$("quick").onchange = () => { const v = $("quick").value; if (v) pickPart(v); $("quick").value = ""; };
let previewPid = null;
async function pickPart(pid) {
  previewPid = pid;
  await api("arm", { pid });
  markArmed();
  const j = await (await xfetch("/api/part?pid=" + encodeURIComponent(pid))).json();
  drawPreview(j);
  $("lib-info").textContent = (j.name || "") + (j.pins ? "  (" + j.pins + " pins)" : "") + (j.note ? "\n" + j.note : "");
  $("fav-btn").textContent = j.favourite ? "★ Favourite" : "☆ Favourite";
  $("fav-btn").dataset.on = j.favourite ? "1" : "";
}
$("fav-btn").onclick = async () => { if (!previewPid) return; await api("fav", { pid: previewPid, on: !$("fav-btn").dataset.on }); pickPart(previewPid); loadLibrary(); };
function drawPreview(j) {
  const pc = $("preview"), c = pc.getContext("2d"), dpr = window.devicePixelRatio || 1;
  const W = pc.clientWidth, H = pc.clientHeight; pc.width = W * dpr; pc.height = H * dpr; c.setTransform(dpr, 0, 0, dpr, 0, 0);
  c.fillStyle = COL.bg; c.fillRect(0, 0, W, H);
  if (!j.shapes) return;
  let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
  const grow = (x, y) => { x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y); };
  for (const s of j.shapes) { if (s.k === "c") { grow(s.a[0] - s.r, s.a[1] - s.r); grow(s.b[0] + s.r, s.b[1] + s.r); } else for (const p of s.pts) grow(p[0], p[1]); }
  for (const sg of j.segs) { grow(sg[0], sg[1]); grow(sg[2], sg[3]); }
  const sc = Math.min((W - 20) / Math.max(1, x1 - x0), (H - 20) / Math.max(1, y1 - y0), 20);
  const ox = (W - (x1 - x0) * sc) / 2 - x0 * sc, oy = (H - (y1 - y0) * sc) / 2 + y1 * sc;
  const P = (x, y) => [ox + x * sc, oy - y * sc];
  c.fillStyle = COL.copper; c.strokeStyle = COL.copper; c.lineCap = "round";
  for (const s of j.shapes) {
    if (s.k === "c") { const a = P(...s.a), b = P(...s.b), w = Math.max(1, 2 * s.r * sc); if (Math.hypot(a[0] - b[0], a[1] - b[1]) < .01) { c.beginPath(); c.arc(a[0], a[1], w / 2, 0, Math.PI * 2); c.fill(); } else { c.lineWidth = w; c.beginPath(); c.moveTo(a[0], a[1]); c.lineTo(b[0], b[1]); c.stroke(); } }
    else { c.beginPath(); s.pts.forEach((p, i) => { const q = P(...p); if (i) c.lineTo(q[0], q[1]); else c.moveTo(q[0], q[1]); }); c.closePath(); c.fill(); }
  }
  c.fillStyle = COL.hole; for (const [x, y, d] of j.drills) { const q = P(x, y); c.beginPath(); c.arc(q[0], q[1], Math.max(1, d / 2 * sc), 0, Math.PI * 2); c.fill(); }
  c.strokeStyle = COL.outline; c.lineWidth = 1; for (const sg of j.segs) { const a = P(sg[0], sg[1]), b = P(sg[2], sg[3]); c.beginPath(); c.moveTo(a[0], a[1]); c.lineTo(b[0], b[1]); c.stroke(); }
}

// ------------------------------------------------------------------ the side panel
function esc(s) { return String(s).replace(/[&<>"]/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[ch])); }
function renderPanel() {
  const p = $("panel"); p.innerHTML = "";
  for (const w of PANEL) p.appendChild(widget(w));
}
function widget(w) {
  let el;
  if (w.t === "head") { el = document.createElement("div"); el.className = "head"; el.textContent = w.text; }
  else if (w.t === "label") { el = document.createElement("div"); el.textContent = w.text; if (w.muted) el.className = "muted"; if (w.warn) el.className = "warn-text"; if (w.bold) el.style.fontWeight = "700"; if (w.rigid) el.className = "rigid"; if (w.mirror) el.className = "mirror-note"; }
  else if (w.t === "sep") { el = document.createElement("hr"); }
  else if (w.t === "row") { el = document.createElement("div"); el.className = "row"; for (const k of w.items) el.appendChild(widget(k)); }
  else if (w.t === "button") { el = document.createElement("button"); el.textContent = w.label; if (w.style === "red") el.className = "red"; if (w.small) el.className += " small"; el.onclick = () => runCmd(w.cmd, w.args); }
  else if (w.t === "check") {
    el = document.createElement("label"); el.className = "check" + (w.mirror ? " mirror-check" : ""); const i = document.createElement("input"); i.type = "checkbox"; i.checked = !!w.value; if (w.id) i.id = "pw-" + w.id;
    i.onchange = () => { if (w.cmd !== "noop") runCmd(w.cmd, Object.assign({}, w.args, { value: i.checked })); };
    el.appendChild(i); el.appendChild(document.createTextNode(" " + w.label));
  }
  else if (w.t === "entry") {
    el = document.createElement("div"); const l = document.createElement("label"); l.className = "lab"; l.textContent = w.label; el.appendChild(l);
    const i = document.createElement("input"); i.type = "text"; i.value = w.value == null ? "" : w.value; if (w.focus) i.dataset.focus = "1";
    const commit = () => { if (String(i.value) !== String(w.value == null ? "" : w.value)) { w.value = i.value; runCmd(w.cmd, Object.assign({}, w.args, { value: w.num ? parseFloat(i.value) : i.value })); } };
    i.onchange = commit; i.onkeydown = e => { if (e.key === "Enter") { commit(); i.blur(); } };
    el.appendChild(i); if (w.hint) { const h = document.createElement("div"); h.className = "hint"; h.textContent = w.hint; el.appendChild(h); }
  }
  else if (w.t === "select") {
    el = document.createElement("div"); const l = document.createElement("label"); l.className = "lab"; l.textContent = w.label; el.appendChild(l);
    const s = document.createElement("select");
    for (const o of w.options) { const opt = document.createElement("option"); const [v, t] = Array.isArray(o) ? o : [o, o]; opt.value = v; opt.textContent = t; if (String(v) === String(w.value)) opt.selected = true; s.appendChild(opt); }
    s.onchange = () => runCmd(w.cmd, Object.assign({}, w.args, { value: s.value })); el.appendChild(s);
  }
  else if (w.t === "radio") {
    el = document.createElement("div"); el.className = "radio"; const l = document.createElement("div"); l.className = "lab"; l.textContent = w.label; el.appendChild(l);
    const name = "r" + Math.random().toString(36).slice(2);
    for (const [v, t] of w.options) { const lab = document.createElement("label"); const i = document.createElement("input"); i.type = "radio"; i.name = name; i.value = v; i.checked = String(v) === String(w.value); i.onchange = () => runCmd(w.cmd, Object.assign({}, w.args, { value: v })); lab.appendChild(i); lab.appendChild(document.createTextNode(" " + t)); el.appendChild(lab); }
  }
  else if (w.t === "slider") {
    el = document.createElement("div");
    const r = document.createElement("input"); r.type = "range"; r.min = w.min; r.max = w.max; r.step = w.step; r.value = w.value;
    const cap = document.createElement("div"); cap.className = "muted";
    const caption = (v) => { v = parseFloat(v); cap.textContent = v.toFixed(2) + " mm" + (w.caption && Math.abs(v - w.value) < 1e-9 ? w.caption.slice(w.caption.indexOf("  ~")) : ""); };
    caption(w.value);
    const send = (v) => { v = Math.max(w.min, Math.min(w.max, parseFloat(v))); if (isNaN(v)) return; const a = Object.assign({}, w.args, { value: v }); if (w.args.apply_existing_from) { const cb = $("pw-" + w.args.apply_existing_from); a.apply_existing = cb ? cb.checked : true; } runCmd(w.cmd, a); };
    r.oninput = () => caption(r.value); r.onchange = () => send(r.value);
    el.appendChild(r); el.appendChild(cap);
    const pr = document.createElement("div"); pr.className = "presets";
    for (const v of w.presets) { const b = document.createElement("button"); b.textContent = v; b.onclick = () => send(v); pr.appendChild(b); }
    el.appendChild(pr);
    const row = document.createElement("div"); row.className = "row"; row.appendChild(document.createTextNode("Exact mm: "));
    const ex = document.createElement("input"); ex.type = "text"; ex.size = 6; ex.value = Number(w.value).toFixed(2); ex.style.width = "70px";
    ex.onkeydown = e => { if (e.key === "Enter") send(ex.value); }; ex.onchange = () => send(ex.value); row.appendChild(ex); el.appendChild(row);
  }
  else { el = document.createElement("div"); el.textContent = JSON.stringify(w); }
  return el;
}
async function runCmd(cmd, args) {
  args = args || {};
  if (cmd === "fit") return fit();
  if (cmd === "mirror") return toggleMirror();
  if (cmd === "pick_file") { if (args.what === "kicad") $("file-kicad").click(); return; }
  if (cmd === "show_countersink") { const out = await api(cmd, args); return out; }
  return api(cmd, args);
}

// ------------------------------------------------------------------ menus
function closePopup() { const p = $("menu-popup"); p.hidden = true; p.innerHTML = ""; document.querySelectorAll(".menu.open").forEach(m => m.classList.remove("open")); }
function buildMenu(items, container) {
  for (const it of items) {
    if (it.sep) { const d = document.createElement("div"); d.className = "sep"; container.appendChild(d); continue; }
    const d = document.createElement("div"); d.className = "item" + (it.head ? " head" : "") + (it.disabled ? " disabled" : "") + (it.sub ? " has-sub" : "");
    const lab = document.createElement("span"); lab.textContent = (it.checked === true ? "☑ " : it.checked === false ? "☐ " : "") + it.label; d.appendChild(lab);
    if (it.key) { const k = document.createElement("span"); k.className = "key"; k.textContent = it.key; d.appendChild(k); }
    if (it.sub) { const sm = document.createElement("div"); sm.className = "popup submenu"; buildMenu(it.sub, sm); d.appendChild(sm); }
    else if (!it.head && !it.disabled) d.onclick = (e) => { e.stopPropagation(); closePopup(); if (it.action) it.action(); else if (it.cmd) runCmd(it.cmd, it.args); };
    container.appendChild(d);
  }
}
function showPopup(items, x, y) {
  const p = $("menu-popup"); p.innerHTML = ""; buildMenu(items, p); p.hidden = false;
  const r = p.getBoundingClientRect();
  p.style.left = Math.max(0, Math.min(x, window.innerWidth - r.width - 4)) + "px";
  p.style.top = Math.max(0, Math.min(y, window.innerHeight - r.height - 4)) + "px";
}
document.addEventListener("mousedown", e => { if (!e.target.closest("#menu-popup") && !e.target.closest(".menu")) closePopup(); });
async function contextMenu(p) {
  const j = await (await xfetch("/api/menu?x=" + p.x + "&y=" + p.y)).json();
  applyState(j.state);
  const r = canvas.getBoundingClientRect();
  showPopup(j.menu, r.left + p.sx, r.top + p.sy);
}
function menuItems(which) {
  const st = S.settings;
  const check = (label, key, val) => ({ label, checked: !!val, cmd: "setting", args: { key, value: !val } });
  const demos = demoNames;
  if (which === "file") return [
    { label: "New board...", cmd: "dialog", args: { name: "new" } },
    { label: "Open...", action: () => $("file-open").click(), key: "Ctrl+O" },
    ...(BROWSER ? [] : [{ label: "Open recent", sub: recentItems() }]),
    { label: "Save (download .solotrace)", action: saveBoard, key: "Ctrl+S" },
    ...(BROWSER ? [] : [{ label: "Save to the opened file" + (S.path ? " (" + S.path + ")" : ""), cmd: "save_path", args: {}, disabled: !S.path }]),
    { label: "Recover autosave", cmd: "recover_autosave", args: {} },
    { sep: true },
    { label: "Examples", sub: demos.map(n => ({ label: n, cmd: "demo", args: { name: n } })) },
    { label: "Import netlist (text)...", action: () => $("file-netlist").click() },
    { label: "Export netlist (text)", action: () => download("/api/export/netlist") },
    { sep: true },
    ...(BROWSER ? [] : [{ label: "Quit SoloTrace (stops the local server)", action: quitApp }]),
  ];
  if (which === "edit") return [
    { label: "Undo", cmd: "undo", args: {}, key: "Ctrl+Z", disabled: !S.can_undo }, { label: "Redo", cmd: "redo", args: {}, key: "Ctrl+Y", disabled: !S.can_redo },
    { sep: true },
    { label: "Delete selection", cmd: "delete", args: {}, key: "Del" }, { label: "Duplicate", cmd: "duplicate", args: {}, key: "Ctrl+D" },
    { label: "Rotate 90", cmd: "rotate", args: { step: 90 }, key: "R" }, { label: "Rotate back 90", cmd: "rotate", args: { step: -90 }, key: "Shift+R" },
    { label: "Mirror part (mount it under the board)", cmd: "mirror", args: {}, key: "Shift+M" },
    { sep: true },
    { label: "Fit board", action: fit, key: "F" }, { label: "Flip view (copper / component side)", action: toggleMirror, key: "M" },
    { label: "Show grid", checked: V.showGrid, action: () => { V.showGrid = !V.showGrid; backKey = ""; draw(); } },
    { label: "Show rubber bands (unrouted connections)", checked: S.show_air !== false, cmd: "show_air", args: { value: S.show_air === false } },
  ];
  if (which === "board") return [
    { label: "Auto-place", cmd: "auto_place", args: {} }, { label: "Auto-route", cmd: "auto_route", args: {} },
    { label: "Clear automatic routes", cmd: "clear_auto", args: {} },
    { label: "Clear ALL routes (including hand-drawn)...", action: () => ask("Remove every trace and jumper, including ones you drew by hand?", () => api("clear_all")) },
    { label: "Tidy all traces", cmd: "tidy_all", args: {} }, { label: "Check (DRC)", cmd: "show_drc", args: {} },
    { sep: true },
    { label: "Board size and rules...", cmd: "dialog", args: { name: "settings" } },
    { label: "Ground fill (deadbug / Manhattan)...", cmd: "dialog", args: { name: "islands" } },
    { label: "Ground fill on", checked: st.island_mode, cmd: "toggle_islands", args: {} },
    { label: "Back-side ground plane...", cmd: "dialog", args: { name: "backplane" } },
    { sep: true },
    check("Auto-route may add wire-link jumpers", "allow_jumpers", st.allow_jumpers),
    check("Keep traces out from under part bodies", "keep_out_under_parts", st.keep_out),
    { label: "Auto-route algorithm", sub: [["auto", "Auto (negotiated, then classic if needed)"], ["negotiated", "Negotiated congestion (PathFinder)"], ["classic", "Classic (best of 6 orders)"]].map(([v, t]) => ({ label: t, checked: st.router === v, cmd: "setting", args: { key: "router", value: v } })) },
    { label: "Auto-place algorithm", sub: [["anneal", "Annealing (length and crossings)"], ["routability", "Routability (congestion-aware, experimental)"]].map(([v, t]) => ({ label: t, checked: st.placer === v, cmd: "setting", args: { key: "placer", value: v } })) },
    { label: "New parts get", sub: [["tht", "Through-hole pads"], ["dead", "Deadbug pads (no holes)"], ["mixed", "Both"]].map(([v, t]) => ({ label: t, checked: S.default_style === v, cmd: "default_style", args: { value: v } })) },
  ];
  if (which === "parts") return [
    { label: "Through-hole parts", checked: S.parts_mode === "tht", action: async () => { await api("parts_mode", { mode: "tht" }); loadLibrary(); } },
    { label: "SMD parts", checked: S.parts_mode === "smd", action: async () => { await api("parts_mode", { mode: "smd" }); loadLibrary(); } },
    { sep: true },
    { label: "New footprint (My parts)...", cmd: "dialog", args: { name: "footprint" } },
    { label: "Import a KiCad footprint (.kicad_mod)...", action: () => $("file-kicad").click() },
    { label: "Reload the parts list", action: loadLibrary },
  ];
  if (which === "export") {
    const items = [
      { label: "Gerber + drill (zip)", action: () => exportChecked("/api/export/gerber") },
      { label: "PDF, 1:1 mirrored (toner transfer)", action: () => exportChecked("/api/export/pdf?mirror=1") },
      { label: "PDF, 1:1 as designed", action: () => exportChecked("/api/export/pdf?mirror=0") },
      { label: "SVG, 1:1 mirrored", action: () => exportChecked("/api/export/svg?mirror=1") },
      { label: "SVG, 1:1 as designed", action: () => exportChecked("/api/export/svg?mirror=0") },
    ];
    if (st.backplane) items.push({ label: "Back-side ground plane PDF", action: () => exportChecked("/api/export/pdf?mirror=0&layer=top") },
      { label: "Back-side ground plane SVG", action: () => exportChecked("/api/export/svg?mirror=0&layer=top") },
      { label: "Countersink list", cmd: "show_countersink", args: {} });
    items.push({ sep: true }, { label: "Laser G-code (Elegoo Phecda)...", cmd: "dialog", args: { name: "laser" } },
      { sep: true }, { label: "Bill of materials (csv)", action: () => download("/api/export/bom") });
    return items;
  }
  if (which === "help") return [
    { label: "Quick guide", cmd: "help", args: {} }, { label: "About SoloTrace", cmd: "about", args: {} },
    { label: "Project page on GitHub", action: () => window.open("https://github.com/The-Dorkknight/solotrace", "_blank") },
  ];
  return [];
}
let recentCache = [], demoNames = [];
function recentItems() { return recentCache.length ? recentCache.map(p => ({ label: p, cmd: "open_path", args: { path: p } })) : [{ label: "(nothing yet)", disabled: true }]; }
document.querySelectorAll(".menu").forEach(m => {
  m.onclick = (e) => { e.stopPropagation(); if (m.classList.contains("open")) { closePopup(); return; } closePopup(); m.classList.add("open"); const r = m.getBoundingClientRect(); showPopup(menuItems(m.dataset.menu), r.left, r.bottom + 2); };
});

// ------------------------------------------------------------------ files
async function download(url, body) {
  let r;
  try { r = body ? await xfetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }) : await xfetch(url); }
  catch (e) { showText("SoloTrace", "Download failed: " + e.message, true); return false; }
  if (!r.ok) { let t = await r.text(); try { t = JSON.parse(t).error || t; } catch (e) { /* plain */ } showText("SoloTrace", t, true); return false; }
  const blob = await r.blob();
  const cd = r.headers.get("Content-Disposition") || "", m = /filename="([^"]+)"/.exec(cd);
  const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = m ? m[1] : "solotrace-file"; document.body.appendChild(a); a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 2000);
  return true;
}
async function saveBoard() { if (await download("/api/export/board")) api("saved"); }
async function exportChecked(url) {
  const out = await api("export_check");
  if (out.warning) ask(out.warning + "\n\nExport anyway?", () => download(url)); else download(url);
}
function readFile(input, cb) {
  input.onchange = () => { const f = input.files[0]; if (!f) return; const rd = new FileReader(); rd.onload = () => cb(rd.result, f.name); rd.readAsText(f); input.value = ""; };
}
readFile($("file-open"), (text, name) => { const go = () => api("open_text", { text, name }); if (S.dirty) ask("This board has unsaved changes. Open " + name + " anyway?", go); else go(); });
readFile($("file-netlist"), (text, name) => api("import_netlist", { text, name }));
readFile($("file-kicad"), async (text) => {
  const out = await api("import_kicad", { text });
  if (out.preset) { await api("dialog", { name: "footprint" }); for (const k in out.preset) { const el = $("modal").querySelector('[data-k="' + k + '"]'); if (el) el.value = out.preset[k]; } }
});
async function quitApp() {
  if (BROWSER) { showText("SoloTrace", "This is the in-browser version: just close the tab. Your settings and the autosave stay in this browser; use Save to keep the board as a file."); return; }
  const go = async () => { try { await fetch("/api/quit"); } catch (e) { /* gone */ } document.body.innerHTML = '<div style="padding:40px;font:15px system-ui"><b>SoloTrace has stopped.</b> You can close this tab. Double-click the launcher to start it again.</div>'; };
  if (S.dirty) ask("This board has unsaved changes (Save downloads a .solotrace file). Quit anyway?", go); else go();
}

// ------------------------------------------------------------------ modals
function openModal(html) { $("modal").innerHTML = html; $("modal-back").hidden = false; return $("modal"); }
function closeModal() { $("modal-back").hidden = true; $("modal").innerHTML = ""; alertOpen = false; showNextAlert(); }
function showText(title, text, isError, downloadKind) {
  const m = openModal("<h2>" + esc(title) + "</h2>" + (isError ? '<div class="error"></div>' : "<pre></pre>") + '<div class="buttons"></div>');
  m.querySelector(isError ? ".error" : "pre").textContent = text;
  const b = m.querySelector(".buttons");
  if (downloadKind) { const d = document.createElement("button"); d.textContent = "Save as text..."; d.onclick = () => download("/api/export/" + downloadKind); b.appendChild(d); }
  const ok = document.createElement("button"); ok.textContent = "OK"; ok.className = "accent"; ok.onclick = closeModal; b.appendChild(ok); ok.focus();
}
function ask(text, yes, no) {
  const m = openModal('<h2>SoloTrace</h2><div class="text"></div><div class="buttons"></div>');
  m.querySelector(".text").textContent = text;
  const b = m.querySelector(".buttons");
  const y = document.createElement("button"); y.textContent = "Yes"; y.className = "accent"; y.onclick = () => { closeModal(); yes(); }; b.appendChild(y);
  const n = document.createElement("button"); n.textContent = "No"; n.onclick = () => { closeModal(); if (no) no(); }; b.appendChild(n); y.focus();
}
function showNextAlert() {
  if (alertOpen || !alertsQueue.length || !$("modal-back").hidden) return;
  const a = alertsQueue.shift(); alertOpen = true;
  if (a.kind === "ask") ask(a.text, () => api(a.cmd, a.args), a.no_cmd ? () => api(a.no_cmd, a.no_args) : null);
  else showText(a.kind === "error" ? "Something went wrong" : "SoloTrace", a.text, a.kind === "error");
}
function showDrc(d) {
  const box = $("drc-box"); box.hidden = false;
  $("drc-summary").textContent = d.summary;
  const l = $("drc-list"); l.innerHTML = "";
  for (const it of d.issues) {
    const r = document.createElement("div"); r.className = "issue";
    r.innerHTML = '<span class="sev ' + it.severity + '">' + it.severity + "</span> " + esc(it.kind) + ": " + esc(it.message);
    r.onclick = () => { api("set_marks", { pts: [[it.x, it.y]] }); centreOn(it.x, it.y); };
    l.appendChild(r);
  }
}
$("drc-close").onclick = () => { $("drc-box").hidden = true; api("clear_marks"); };

function fieldHtml(f) {
  if (f.type === "head") return '<div class="fhead">' + esc(f.label) + "</div>";
  let inp;
  if (f.type === "check") return '<label></label><label><input type="checkbox" data-k="' + esc(f.k) + '"' + (f.value ? " checked" : "") + "> " + esc(f.label) + "</label>";
  if (f.type === "select") inp = '<select data-k="' + esc(f.k) + '">' + f.options.map(o => { const [v, t] = Array.isArray(o) ? o : [o, o]; return '<option value="' + esc(v) + '"' + (String(v) === String(f.value) ? " selected" : "") + ">" + esc(t) + "</option>"; }).join("") + "</select>";
  else if (f.type === "textarea") inp = '<textarea data-k="' + esc(f.k) + '">' + esc(f.value == null ? "" : f.value) + "</textarea>";
  else inp = '<input type="' + (f.type === "number" ? "text" : "text") + '" data-k="' + esc(f.k) + '" value="' + esc(f.value == null ? "" : f.value) + '"' + (f.type === "number" ? ' size="8" inputmode="decimal"' : "") + ">";
  return "<label>" + esc(f.label) + "</label>" + inp;
}
function readFields(m, fields) {
  const v = {};
  for (const f of fields) {
    if (f.type === "head") continue;
    const el = m.querySelector('[data-k="' + f.k + '"]'); if (!el) continue;
    v[f.k] = f.type === "check" ? el.checked : el.value;
  }
  return v;
}
function openDialog(d) {
  if (d.laser) return openLaser(d);
  const m = openModal("<h2>" + esc(d.title) + "</h2>" + (d.warn ? '<div class="warnbox">' + esc(d.warn) + "</div>" : "") +
    '<div class="fields">' + d.fields.map(fieldHtml).join("") + "</div>" + (d.info ? '<div class="info">' + esc(d.info) + "</div>" : "") +
    '<div class="error" hidden></div><div class="buttons"></div>');
  const b = m.querySelector(".buttons");
  if (d.submit) {
    const ok = document.createElement("button"); ok.textContent = d.ok || "OK"; ok.className = "accent";
    ok.onclick = async () => { const out = await api(d.submit, { values: readFields(m, d.fields) }); if (out && out.error) { const e = m.querySelector(".error"); e.hidden = false; e.textContent = out.error; } else closeModal(); };
    b.appendChild(ok);
  }
  for (const x of d.buttons || []) {
    const bt = document.createElement("button"); bt.textContent = x.label;
    bt.onclick = async () => {
      if (x.cmd === "footprint_preset") { const out = await api(x.cmd, x.args); if (out.pads) m.querySelector('[data-k="pads"]').value = out.pads; return; }
      if (x.cmd === "pick_file") { readFile($("file-kicad"), async (text) => { const out = await api("import_kicad", { text }); if (out.preset) for (const k in out.preset) { const el = m.querySelector('[data-k="' + k + '"]'); if (el) el.value = out.preset[k]; } }); $("file-kicad").click(); return; }
      runCmd(x.cmd, x.args);
    };
    b.appendChild(bt);
  }
  const c = document.createElement("button"); c.textContent = d.submit ? "Cancel" : "Close"; c.onclick = closeModal; b.appendChild(c);
  const first = m.querySelector("input, select, textarea"); if (first) first.focus();
}
function openLaser(d) {
  const m = openModal("<h2>" + esc(d.title) + "</h2><div class=\"warnbox\">" + esc(d.warn) + '</div><div class="laser"><div><div class="fields">' +
    d.fields.map(fieldHtml).join("") + '</div><div class="buttons"><button class="accent" id="lz-save">Save G-code</button><button id="lz-prev">Update preview</button>' +
    '<button id="lz-frame">Frame file</button><button id="lz-speed">Speed/power test</button><button id="lz-ladder">Trace/gap test</button><button id="lz-close">Close</button></div>' +
    '<div class="info">' + esc(d.info) + '</div></div><div><div id="lz-summary" style="font-weight:700"></div><div id="lz-warn" class="warn-text"></div><img id="lz-img" alt="laser preview"><div class="muted">Preview: component-side view. Orange = paint burned off, dark = paint stays.</div></div></div>');
  const vals = () => readFields(m, d.fields);
  const layer = () => { const el = m.querySelector('[data-k="layer"]'); return el ? el.value : "bottom"; };
  const refresh = async () => {
    const v = vals(); delete v.layer;
    const j = await post("/api/laser/preview", { values: v, layer: layer() });
    if (j.error) { $("lz-warn").textContent = j.error; $("lz-summary").textContent = ""; return; }
    $("lz-img").src = "data:image/png;base64," + j.png; $("lz-summary").textContent = j.summary + " (" + j.options + ")"; $("lz-warn").textContent = (j.warnings || []).join("\n");
  };
  $("lz-prev").onclick = refresh; $("lz-close").onclick = closeModal;
  $("lz-save").onclick = () => { const v = vals(); delete v.layer; download("/api/laser/gcode", { kind: "board", values: v, layer: layer() }); };
  $("lz-frame").onclick = () => download("/api/laser/gcode", { kind: "frame", values: vals() });
  $("lz-speed").onclick = () => download("/api/laser/gcode", { kind: "speed", values: vals() });
  $("lz-ladder").onclick = () => download("/api/laser/gcode", { kind: "ladder", values: vals() });
  refresh();
}
function disclaimer(title) {
  const m = openModal("<h2>Please read first</h2><div class=\"disclaimer\"></div><div class=\"buttons\"><label><input type=\"checkbox\" id=\"dc-chk\"> I have read this and accept the risks</label></div><div class=\"buttons\"><button class=\"accent\" id=\"dc-ok\" disabled>I agree</button><button id=\"dc-quit\">Quit</button></div>");
  m.querySelector(".disclaimer").textContent = title + "\n\n" + S.wip + "\n\nThis is early, untested software. Check every 1:1 print against your real parts before etching.\n\n" +
    "LASER SAFETY: a diode laser can blind you and start fires. Wear laser safety glasses rated for your laser, ventilate (burning paint makes fumes), never leave a running laser unattended, and keep a fire extinguisher or water nearby. The laser only removes paint; the board is then etched in chemicals that need their own care.\n\n" +
    "Licence: PolyForm Noncommercial 1.0.0 (source-available). No warranty, no liability.";
  $("dc-chk").onchange = () => { $("dc-ok").disabled = !$("dc-chk").checked; };
  $("dc-ok").onclick = async () => { await api("accept"); closeModal(); };
  $("dc-quit").onclick = async () => {
    if (BROWSER) { document.body.innerHTML = '<div style="padding:40px;font:15px system-ui">You can close this tab.</div>'; return; } try { await fetch("/api/quit"); } catch (e) { /* gone */ } document.body.innerHTML = '<div style="padding:40px;font:15px system-ui">SoloTrace has stopped. You can close this tab.</div>'; };
}

// ------------------------------------------------------------------ start
window.addEventListener("resize", resize);
async function start() {
  resize();
  if (BROWSER) {
    startWorker();
    loadingText("Loading SoloTrace in your browser...");
    window.addEventListener("beforeunload", (e) => { if (S && S.dirty) { e.preventDefault(); e.returnValue = ""; } });
    try { await workerReady; } catch (e) { return; }
  }
  const j = await getState();
  if (!j) return;
  recentCache = j.recent || []; demoNames = j.demos || [];
  fit();
  loadLibrary();
  if (!j.accepted) disclaimer(j.title);
  if (BROWSER) { document.getElementById("wip").textContent = "WORK IN PROGRESS: MANY FEATURES MAY BE BROKEN \u2014 running entirely in your browser (nothing to install, nothing uploaded). Not tested on a real Elegoo Phecda yet."; return; }
  setInterval(() => fetch("/api/ping").catch(() => {}), 10000);
  fetch("/api/ping").catch(() => {});
}
start();
