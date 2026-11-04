// Dashboard client: one WebSocket snapshot every 0.5 s -> update the page. No libraries, works offline.
const $ = (id) => document.getElementById(id);
const fmtUp = (s) => {
  s = Math.floor(s || 0);
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), x = s % 60;
  return h ? `${h}h ${m}m` : m ? `${m}m ${x}s` : `${x}s`;
};
const fmtTime = (t) => (t ? new Date(t * 1000).toLocaleTimeString() : "–");

function setPill(el, text, kind) {
  el.textContent = text;
  el.className = `pill pill-${kind}`;
}

function drawSpark(hist, thr) {
  const c = $("spark"), ctx = c.getContext("2d");
  const w = (c.width = c.clientWidth * devicePixelRatio), h = (c.height = 90 * devicePixelRatio);
  ctx.clearRect(0, 0, w, h);
  if (!hist || hist.length < 2) return;
  const vals = hist.map((p) => Math.log10(Math.max(p.score, 1e-3)));
  const lt = Math.log10(Math.max(thr || 1, 1e-3));
  const lo = Math.min(...vals, lt) - 0.2, hi = Math.max(...vals, lt) + 0.2;
  const y = (v) => h - ((v - lo) / (hi - lo)) * h, x = (i) => (i / (vals.length - 1)) * w;
  const css = getComputedStyle(document.documentElement);
  ctx.strokeStyle = css.getPropertyValue("--fail"); ctx.setLineDash([6, 5]); ctx.lineWidth = devicePixelRatio;
  ctx.beginPath(); ctx.moveTo(0, y(lt)); ctx.lineTo(w, y(lt)); ctx.stroke(); ctx.setLineDash([]);
  ctx.strokeStyle = css.getPropertyValue("--accent"); ctx.lineWidth = 2 * devicePixelRatio;
  ctx.beginPath(); vals.forEach((v, i) => (i ? ctx.lineTo(x(i), y(v)) : ctx.moveTo(x(i), y(v)))); ctx.stroke();
}

async function markTruth(id, truth) {
  await fetch(`/api/parts/${id}/truth`, { method: "POST", headers: { "Content-Type": "application/json" },
                                           body: JSON.stringify({ truth }) });
}
window.markTruth = markTruth;

function renderParts(parts) {
  const tb = $("parts");
  if (!parts.length) { tb.innerHTML = '<tr><td colspan="6" class="muted">no parts yet</td></tr>'; return; }
  tb.innerHTML = parts.map((p) => {
    const why = Object.keys(p.reasons || {}).join(", ") || (p.result === "PASS" ? "all checks ok" : "–");
    const cls = p.correct === true ? "ok" : p.correct === false ? "wrong" : "";
    const b = (t, label) => `<button class="t ${p.truth === t ? "sel-" + t : ""}" onclick="markTruth(${p.id},'${t}')">${label}</button>`;
    return `<tr><td>${p.id}</td><td>${fmtTime(p.t_end)}</td>
      <td class="${cls}"><span class="chip chip-${p.result}">${p.result}</span></td>
      <td>${why}</td><td>${p.latency_ms != null ? p.latency_ms.toFixed(0) + " ms" : "–"}</td>
      <td>${b("good", "good")} ${b("defective", "defective")}</td></tr>`;
  }).join("");
}

function render(s) {
  const st = s.stats, k = s.kpis, live = s.live;
  $("device").textContent = st.device_id;
  const stateKind = st.state === "running" ? "ok" : st.state === "SAFE_STATE" ? "bad" : "off";
  setPill($("state"), st.state === "SAFE_STATE" ? "SAFE STATE · line stopped" : st.state.toUpperCase(), stateKind);
  $("fps").textContent = st.fps.toFixed(1);
  $("uptime").textContent = fmtUp(st.uptime_s);
  $("permit").className = "dot " + (st.run_permit ? "on" : "off");
  $("permit").title = st.run_permit ? "run permit ON (conveyor allowed)" : "run permit OFF (conveyor stopped)";

  const v = st.inspection ? (live.verdict || "NONE") : (live.part_in_view ? "SEEN" : "NONE");
  const box = $("verdict");
  box.textContent = v === "NONE" ? "—" : v;
  box.className = "verdict " + (v === "PASS" ? "verdict-pass" : v === "FAIL" ? "verdict-fail" : "verdict-none");
  $("reasons").textContent = (live.reasons || []).join(", ") || (v === "PASS" ? "all checks ok" : v === "NONE" ? "waiting for a part" : "");
  $("inview").textContent = st.inspection ? "inspection on" : "inspection off (counting only)";
  $("dets").textContent = live.detections.map((d) => `${d.name} ${d.conf.toFixed(2)}`).join(" · ") || "no detections";

  $("headline").textContent = k.headline.text;
  $("fpr").textContent = k.headline.false_pass_rate == null ? "–" : `${(100 * k.headline.false_pass_rate).toFixed(0)} %`;
  $("k-thr").textContent = k.throughput_per_min.toFixed(1);
  $("k-yield").textContent = k.yield_pct == null ? "–" : k.yield_pct.toFixed(0);
  $("k-lat").textContent = k.median_latency_ms == null ? "–" : k.median_latency_ms.toFixed(0);

  const m = s.motor;
  if (m && m.score != null) {
    setPill($("motor-state"), m.alert ? "ANOMALY" : "normal", m.alert ? "bad" : "ok");
    $("motor-card").classList.toggle("alert", !!m.alert);
    $("m-score").textContent = m.score.toFixed(1);
    $("m-thr").textContent = m.threshold.toFixed(1);
    $("m-alerts").textContent = m.alerts_total ?? 0;
    drawSpark(m.history, m.threshold);
  }
  renderParts(s.parts);
}

function connect() {
  const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
  ws.onmessage = (e) => render(JSON.parse(e.data));
  ws.onclose = () => { setPill($("state"), "OFFLINE · reconnecting", "bad"); setTimeout(connect, 2000); };
}
connect();
