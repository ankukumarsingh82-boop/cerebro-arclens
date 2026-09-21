const $ = (sel, el = document) => el.querySelector(sel);
const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];

const PALETTE = ["#2fd3b6", "#7aa2ff", "#e4b34a", "#e89ad7", "#ff8b6b", "#9ad7a0"];
let current = null;
let chart = null;
let speakerFilter = "all";
let sarcasmOnly = false;

function speakerColor(name) {
  let h = 0;
  for (const ch of name) h = (h * 33 + ch.charCodeAt(0)) % PALETTE.length;
  return PALETTE[Math.abs(h) % PALETTE.length];
}

function polarityColor(p) {
  if (p >= 0.2) return "#2fd3b6";
  if (p <= -0.2) return "#e85d4c";
  return "#e4b34a";
}

async function getJSON(url, options) {
  const res = await fetch(url, options);
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || res.statusText);
  }
  return res.json();
}

async function loadSamples() {
  const samples = await getJSON("/api/samples");
  const box = $("#samples");
  box.innerHTML = "";
  for (const s of samples) {
    const btn = document.createElement("button");
    btn.className = "sample";
    btn.type = "button";
    btn.dataset.name = s.name;
    btn.innerHTML = `<b>${s.title}</b><span>${s.format} · ${s.preview}</span>`;
    btn.addEventListener("click", () => analyzeSample(s.name));
    box.appendChild(btn);
  }
}

async function analyzeSample(name) {
  setBusy(true);
  try {
    const data = await getJSON(`/api/samples/${encodeURIComponent(name)}`);
    show(data, name);
  } catch (err) {
    alert(err.message);
  } finally {
    setBusy(false);
  }
}

async function analyzeUpload(file) {
  const body = new FormData();
  body.append("file", file);
  setBusy(true);
  try {
    const data = await getJSON("/api/analyze", { method: "POST", body });
    show(data, file.name);
  } catch (err) {
    alert(err.message);
  } finally {
    setBusy(false);
  }
}

async function analyzePaste() {
  const text = $("#paste").value.trim();
  if (!text) return;
  setBusy(true);
  try {
    const data = await getJSON("/api/analyze-text", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, filename: "paste.txt" }),
    });
    show(data, "paste");
  } catch (err) {
    alert(err.message);
  } finally {
    setBusy(false);
  }
}

function setBusy(on) {
  document.body.style.cursor = on ? "progress" : "";
}

function show(data, sourceName) {
  current = data;
  $("#empty").hidden = true;
  $("#workspace").hidden = false;
  $("#stats").hidden = false;
  $$(".sample").forEach((b) => b.classList.toggle("active", b.dataset.name === sourceName));
  renderMeta(data);
  renderChart(data);
  renderHeat(data);
  renderAlerts(data);
  fillFilters(data);
  renderTurns(data);
}

function renderMeta(data) {
  const s = data.arc.summary;
  const alerts = data.alerts;
  const crit = alerts.filter((a) => a.severity === "critical").length;
  $("#stat-list").innerHTML = `
    <dt>Source</dt><dd>${data.meta.source} · ${data.meta.format}</dd>
    <dt>Turns</dt><dd>${data.meta.turn_count}</dd>
    <dt>Speakers</dt><dd>${data.meta.speakers.join(", ") || "—"}</dd>
    <dt>Arc delta</dt><dd>${s.delta.toFixed(2)}</dd>
    <dt>Volatility</dt><dd>${s.volatility.toFixed(2)}</dd>
    <dt>Alerts</dt><dd>${alerts.length} (${crit} critical)</dd>
  `;
  const deltaWord = s.delta < -0.25 ? "cooling into heat" : s.delta > 0.25 ? "warming" : "holding a mixed line";
  $("#arc-caption").textContent =
    `Start ${s.start.toFixed(2)} → end ${s.end.toFixed(2)} · ${deltaWord}. Lowest turn ${s.lowest_turn + 1}.`;
}

function renderChart(data) {
  const ctx = $("#arc-chart").getContext("2d");
  if (chart) chart.destroy();
  const labels = data.turns.map((t) => String(t.index + 1));
  const smoothed = data.arc.points.map((p) => p.smoothed);
  const raw = data.turns.map((t) => t.tone.polarity);
  const alertIdx = new Set(data.alerts.map((a) => a.at_turn));
  const marks = data.turns.map((t, i) => (alertIdx.has(i) ? t.tone.polarity : null));
  const fill = ctx.createLinearGradient(0, 0, 0, 220);
  fill.addColorStop(0, "rgba(47, 211, 182, 0.28)");
  fill.addColorStop(0.5, "rgba(228, 179, 74, 0.08)");
  fill.addColorStop(1, "rgba(232, 93, 76, 0.22)");

  chart = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Smoothed arc",
          data: smoothed,
          borderColor: "#2fd3b6",
          backgroundColor: fill,
          fill: { target: { value: 0 } },
          tension: 0.36,
          borderWidth: 2.4,
          pointRadius: 0,
        },
        {
          label: "Turn polarity",
          data: raw,
          borderColor: "rgba(231, 238, 248, 0.28)",
          pointBackgroundColor: data.turns.map((t) => polarityColor(t.tone.polarity)),
          pointRadius: 3,
          borderWidth: 1,
          tension: 0.12,
        },
        {
          label: "Alerts",
          data: marks,
          showLine: false,
          pointRadius: (ctx) => (ctx.raw == null ? 0 : 6),
          pointBackgroundColor: "#e85d4c",
          pointBorderColor: "#0b0f16",
          pointBorderWidth: 2,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { labels: { color: "#8ea0b8", boxWidth: 10 } },
        tooltip: {
          callbacks: {
            afterBody: (items) => {
              const i = items[0]?.dataIndex ?? 0;
              const t = data.turns[i];
              return `${t.speaker} · ${t.tone.label}` + (t.tone.sarcasm.flag ? " · sarcasm" : "");
            },
          },
        },
      },
      scales: {
        x: { ticks: { color: "#8ea0b8", maxTicksLimit: 16 }, grid: { color: "rgba(38,49,66,0.6)" } },
        y: {
          min: -1,
          max: 1,
          ticks: { color: "#8ea0b8" },
          grid: { color: "rgba(38,49,66,0.6)" },
          title: { display: true, text: "polarity", color: "#8ea0b8" },
        },
      },
      onClick: (_e, elements) => {
        if (!elements.length) return;
        jumpToTurn(elements[0].index);
      },
    },
  });

  const pills = $("#alert-pills");
  const counts = { critical: 0, warning: 0, info: 0 };
  for (const a of data.alerts) counts[a.severity] += 1;
  pills.innerHTML = Object.entries(counts)
    .filter(([, n]) => n)
    .map(([k, n]) => `<span class="pill ${k}">${n} ${k}</span>`)
    .join("");
}

function renderHeat(data) {
  const heat = $("#heat");
  heat.style.gridTemplateColumns = `repeat(${Math.max(1, data.turns.length)}, 1fr)`;
  heat.innerHTML = data.turns
    .map((t) => {
      const c = polarityColor(t.tone.polarity);
      const op = 0.35 + Math.abs(t.tone.polarity) * 0.65;
      return `<i style="background:${c};opacity:${op}"></i>`;
    })
    .join("");
}

function renderAlerts(data) {
  const box = $("#alerts");
  if (!data.alerts.length) {
    box.innerHTML = `<div class="alert info"><b>No escalation raised</b><p>The slope holds. Sarcasm may still be flagged per turn.</p></div>`;
    return;
  }
  box.innerHTML = data.alerts
    .map(
      (a) => `
      <article class="alert ${a.severity}" data-turn="${a.at_turn}">
        <b>${a.title} · ${a.severity}</b>
        <p>${a.detail}</p>
      </article>`
    )
    .join("");
  $$(".alert", box).forEach((el) =>
    el.addEventListener("click", () => jumpToTurn(Number(el.dataset.turn)))
  );
}

function fillFilters(data) {
  const sel = $("#speaker-filter");
  const currentValue = speakerFilter;
  sel.innerHTML =
    `<option value="all">All speakers</option>` +
    data.meta.speakers.map((s) => `<option value="${s}">${s}</option>`).join("");
  sel.value = data.meta.speakers.includes(currentValue) ? currentValue : "all";
  speakerFilter = sel.value;
}

function renderTurns(data) {
  const box = $("#thread");
  const turns = data.turns.filter((t) => {
    if (speakerFilter !== "all" && t.speaker !== speakerFilter) return false;
    if (sarcasmOnly && !t.tone.sarcasm.flag) return false;
    return true;
  });
  box.innerHTML = turns
    .map((t) => {
      const cues = t.tone.sarcasm.cues.slice(0, 3).map((c) => `<span class="chip">${c}</span>`).join("");
      const sarc = t.tone.sarcasm.flag
        ? `<span class="chip sarcastic">sarcasm ${t.tone.sarcasm.score.toFixed(2)}</span>`
        : t.tone.sarcasm.irony
          ? `<span class="chip">irony</span>`
          : "";
      return `
        <article class="turn" id="turn-${t.index}">
          <div class="mercury" style="background:${polarityColor(t.tone.polarity)}"></div>
          <div>
            <div class="turn-meta">
              <span style="color:${speakerColor(t.speaker)}">${t.speaker}</span>
              <span>${t.timestamp || "untimed"} · turn ${t.index + 1} · ${t.tone.polarity.toFixed(2)}</span>
            </div>
            <p class="turn-text">${escapeHtml(t.text)}</p>
            <div class="chips">
              <span class="chip ${t.tone.label}">${t.tone.label}</span>
              ${sarc}
              ${cues}
            </div>
          </div>
        </article>`;
    })
    .join("");
}

function jumpToTurn(index) {
  const el = document.getElementById(`turn-${index}`);
  if (!el) return;
  $$(".turn").forEach((t) => t.classList.remove("active"));
  el.classList.add("active");
  el.scrollIntoView({ behavior: "smooth", block: "center" });
}

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function wireInbox() {
  const form = $("#upload-form");
  const file = $("#file");
  $("#browse").addEventListener("click", (e) => {
    e.preventDefault();
    file.click();
  });
  form.addEventListener("click", (e) => {
    if (e.target.closest("#browse")) return;
    file.click();
  });
  file.addEventListener("change", () => {
    if (file.files[0]) analyzeUpload(file.files[0]);
  });
  ["dragenter", "dragover"].forEach((ev) =>
    form.addEventListener(ev, (e) => {
      e.preventDefault();
      form.classList.add("drag");
    })
  );
  ["dragleave", "drop"].forEach((ev) =>
    form.addEventListener(ev, (e) => {
      e.preventDefault();
      form.classList.remove("drag");
    })
  );
  form.addEventListener("drop", (e) => {
    const f = e.dataTransfer.files[0];
    if (f) analyzeUpload(f);
  });
  $("#paste-run").addEventListener("click", analyzePaste);
  $("#demo").addEventListener("click", () => analyzeSample("slack_incident.txt"));
  $("#speaker-filter").addEventListener("change", (e) => {
    speakerFilter = e.target.value;
    if (current) renderTurns(current);
  });
  $("#sarcasm-only").addEventListener("change", (e) => {
    sarcasmOnly = e.target.checked;
    if (current) renderTurns(current);
  });
  $("#copy-json").addEventListener("click", async () => {
    if (!current) return;
    await navigator.clipboard.writeText(JSON.stringify(current, null, 2));
    $("#copy-json").textContent = "Copied";
    setTimeout(() => ($("#copy-json").textContent = "Copy JSON"), 1200);
  });
}

wireInbox();
loadSamples()
  .then(() => {
    const params = new URLSearchParams(location.search);
    const sample = params.get("sample") || (params.get("demo") === "1" ? "slack_incident.txt" : "");
    if (sample) return analyzeSample(sample);
  })
  .catch((err) => {
    $("#samples").textContent = err.message;
  });
