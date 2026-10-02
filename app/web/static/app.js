/* FB-like dashboard: polling, tree render, filters. */
"use strict";

const state = {
  postUrl: window.__POST_URL__ || "",
  sort: window.__SORT__ || "newest",
  knownIds: new Set(),
  firstLoad: true,
  data: null,
  pollMs: 2000,
  pollTimer: null,
  defaultReply: "",
  monitorWasRunning: null,
};

function liveLabel() {
  const s = state.pollMs / 1000;
  return `อัปเดตอัตโนมัติทุก ${Number.isInteger(s) ? s : state.pollMs + " ms"} วิ`;
}

function resetPollTimer() {
  if (state.pollTimer) clearInterval(state.pollTimer);
  state.pollTimer = setInterval(fetchData, state.pollMs);
  document.getElementById("live-text").textContent = liveLabel();
}

const AVATAR_COLORS = ["#0866ff", "#009444", "#7b2ff7", "#e41e3f", "#ff7f00", "#00838f", "#5c6bc0", "#8d6e63"];

function avatarColor(name) {
  let h = 0;
  for (const ch of name) h = (h * 31 + ch.codePointAt(0)) >>> 0;
  return AVATAR_COLORS[h % AVATAR_COLORS.length];
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function relTime(iso) {
  if (!iso) return "";
  const t = new Date(iso.replace(" ", "T")).getTime();
  if (Number.isNaN(t)) return iso;
  const s = Math.max(0, Math.floor((Date.now() - t) / 1000));
  if (s < 10) return "เมื่อสักครู่";
  if (s < 60) return `${s} วินาทีที่แล้ว`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m} นาทีที่แล้ว`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h} ชั่วโมงที่แล้ว`;
  const d = Math.floor(h / 24);
  if (d < 7) return `${d} วันที่แล้ว`;
  return new Date(t).toLocaleString("th-TH");
}

function logEvent(msg, cls) {
  const list = document.getElementById("log-list");
  if (!list) return;
  const div = document.createElement("div");
  div.className = "log-item" + (cls ? " " + cls : "");
  const t = new Date().toLocaleTimeString("th-TH", { hour12: false });
  div.innerHTML = `<time>${esc(t)}</time><span></span>`;
  div.querySelector("span").textContent = msg;
  list.prepend(div);
  while (list.children.length > 30) list.removeChild(list.lastChild);
}

function commentNode(c, depth) {
  const isNew = !state.knownIds.has(c.id) && !state.firstLoad;
  const avSize = depth > 0 ? " small" : "";
  const badges = [];
  if (c.is_owner) badges.push('<span class="badge">เจ้าของโพสต์</span>');
  if (c.replied) badges.push('<span class="badge gray">ตอบแล้ว ✓</span>');
  const kids = (c.children || []).map((k) => commentNode(k, depth + 1)).join("");
  return `
  <div class="comment" data-id="${esc(c.id)}" data-author="${esc(c.author)}" data-new="${isNew ? 1 : 0}" data-replied="${c.replied ? 1 : 0}" data-owner="${c.is_owner ? 1 : 0}">
    <div class="avatar${avSize}" style="background:${avatarColor(c.author)}">${esc(c.author.trim()[0] || "?")}</div>
    <div class="body">
      <div class="bubble">
        <div class="name">${esc(c.author)}${badges.join("")}</div>
        <div class="text">${esc(c.message)}</div>
      </div>
      <div class="actions"><b>ถูกใจ</b>${c.replied ? '<span class="replied-tag">ตอบแล้ว ✓</span>' : `<button class="reply-btn" data-id="${esc(c.id)}">ตอบกลับ</button>`}<span>${esc(relTime(c.created_time))}</span>${isNew ? '<span class="new-flag">· มาใหม่</span>' : ""}</div>
      <div class="reply-slot"></div>
      ${kids ? `<div class="children">${kids}</div>` : ""}
    </div>
  </div>`;
}

function flatten(tree, out = []) {
  for (const c of tree) { out.push(c); flatten(c.children || [], out); }
  return out;
}

function applyFilters() {
  const q = document.getElementById("search").value.trim().toLowerCase();
  const ownerOnly = document.getElementById("owner-only").checked;
  const unrepliedOnly = document.getElementById("unreplied-only").checked;
  const newOnly = document.getElementById("new-only").checked;
  let visible = 0;
  document.querySelectorAll("#comments .comment").forEach((el) => {
    const text = (el.dataset.author + " " + el.querySelector(".text").textContent).toLowerCase();
    let show = true;
    if (q && !text.includes(q)) show = false;
    if (ownerOnly && el.dataset.owner !== "1") show = false;
    if (unrepliedOnly && el.dataset.replied === "1") show = false;
    if (newOnly && el.dataset.new !== "1") show = false;
    el.style.display = show ? "" : "none";
    if (show) visible++;
  });
  document.getElementById("empty").hidden = visible !== 0;
}

function render(data) {
  state.data = data;
  const err = document.getElementById("dberr");
  if (data.db_error) {
    err.hidden = false;
    err.textContent = "⚠️ " + data.db_error;
  } else {
    err.hidden = true;
  }
  const tree = data.comments || [];
  const stats = data.stats || {};

  // Post card
  const owner = stats.owner || "—";
  document.getElementById("post-author").textContent = owner;
  document.getElementById("post-avatar").textContent = (owner.trim()[0] || "ก");
  document.getElementById("post-avatar").style.background = avatarColor(owner);
  document.getElementById("post-group").textContent = "โพสต์ในกลุ่ม Facebook";
  const times = flatten(tree).map((c) => c.created_time).filter(Boolean).sort();
  document.getElementById("post-time").textContent = times.length ? relTime(times[0]) : "—";
  document.getElementById("post-content").innerHTML =
    `ติดตามความคิดเห็นของโพสต์นี้แบบเรียลไทม์<br><span class="muted" style="font-size:13px">${esc(data.post_url)}</span>`;
  document.getElementById("post-link").href = data.post_url;
  document.getElementById("count-comments").textContent = `💬 ${stats.total ?? 0} ความคิดเห็น (${stats.top_level ?? 0} หลัก · ${stats.replies ?? 0} ตอบกลับ)`;
  document.getElementById("updated-at").textContent = data.updated_at ? `อัปเดต ${relTime(data.updated_at)}` : "";

  // Comments
  document.getElementById("comments").innerHTML = tree.map((c) => commentNode(c, 0)).join("");
  const fresh = document.querySelectorAll('#comments .comment[data-new="1"]').length;
  flatten(tree).forEach((c) => state.knownIds.add(c.id));
  if (!state.firstLoad && fresh > 0) logEvent(`พบคอมเมนต์ใหม่ ${fresh} รายการ`, "ok");

  // Sidebar stats
  document.getElementById("st-total").textContent = stats.total ?? 0;
  document.getElementById("st-t1").textContent = stats.top_level ?? 0;
  document.getElementById("st-replies").textContent = stats.replies ?? 0;
  document.getElementById("st-owner").textContent = `${stats.owner ?? "—"} (${stats.owner_comments ?? 0})`;
  document.getElementById("st-replied").textContent = stats.replied ?? 0;
  document.getElementById("st-updated").textContent = data.updated_at ? relTime(data.updated_at) : "—";

  const ar = data.auto_reply || {};
  state.defaultReply = ar.reply_message || "";
  document.getElementById("ar-status").textContent = ar.enabled ? "เปิด 🟢" : "ปิด ⚪";
  document.getElementById("ar-msg").textContent = ar.reply_message ? `ข้อความตอบ: ${ar.reply_message}` : "";

  // Post list
  const list = document.getElementById("post-list");
  list.innerHTML = "";
  (data.posts || []).forEach((u) => {
    const row = document.createElement("div");
    row.className = "post-row";
    const b = document.createElement("button");
    b.className = "url";
    b.textContent = u;
    if (u === data.post_url) b.classList.add("active");
    b.onclick = () => { state.postUrl = u; state.firstLoad = true; state.knownIds.clear(); fetchData(); };
    const del = document.createElement("button");
    del.className = "del";
    del.title = "ลบโพสต์นี้พร้อมคอมเมนต์ที่เก็บไว้";
    del.textContent = "✕";
    del.onclick = () => delPost(u);
    row.appendChild(b);
    row.appendChild(del);
    list.appendChild(row);
  });

  applyFilters();
  state.firstLoad = false;
}

async function fetchData() {
  try {
    const url = `/api/comments?post_url=${encodeURIComponent(state.postUrl)}&sort=${state.sort}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(res.status);
    render(await res.json());
    document.getElementById("live-dot").classList.add("on");
    document.getElementById("live-text").textContent = liveLabel();
  } catch (e) {
    document.getElementById("live-dot").classList.remove("on");
    document.getElementById("live-text").textContent = "เชื่อมต่อไม่ได้ กำลังลองใหม่...";
    logEvent("ดึงข้อมูลไม่ได้: " + (e.message || e), "err");
  }
}

async function addPost() {
  const input = document.getElementById("new-post-url");
  const msg = document.getElementById("add-post-msg");
  const url = input.value.trim();
  if (!url) return;
  msg.hidden = false;
  msg.className = "form-msg";
  msg.textContent = "กำลังเพิ่ม...";
  try {
    const res = await fetch("/api/posts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || res.status);
    msg.className = "form-msg ok";
    msg.textContent = "เพิ่มแล้ว ✓";
    logEvent("เพิ่มโพสต์ติดตาม: " + data.url, "ok");
    input.value = "";
    state.postUrl = data.url;
    state.firstLoad = true;
    state.knownIds.clear();
    await fetchData();
  } catch (e) {
    msg.className = "form-msg err";
    msg.textContent = e.message;
    logEvent("เพิ่มโพสต์ไม่ได้: " + e.message, "err");
  }
}

async function delPost(url) {
  if (!confirm(`ลบโพสต์นี้ออกจากรายการ?\n\n${url}\n\nคอมเมนต์ทั้งหมดที่เก็บไว้ของโพสต์นี้จะถูกลบด้วย`)) return;
  try {
    const res = await fetch("/api/posts", {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || res.status);
    logEvent(`ลบโพสต์แล้ว (คอมเมนต์ ${data.deleted_comments ?? 0} รายการ)`, "ok");
    if (state.postUrl === url) {
      state.postUrl = (data.posts || [])[0] || "";
      state.firstLoad = true;
      state.knownIds.clear();
    }
    await fetchData();
  } catch (e) {
    alert("ลบไม่ได้: " + e.message);
    logEvent("ลบโพสต์ไม่ได้: " + e.message, "err");
  }
}

// Per-comment auto-reply: one click sends immediately with default message
document.getElementById("comments").addEventListener("click", async (e) => {
  const btn = e.target.closest(".reply-btn");
  if (!btn || btn.disabled) return;
  const commentEl = btn.closest(".comment");
  const slot = commentEl.querySelector(".reply-slot");
  const message = state.defaultReply;
  if (!message) {
    slot.innerHTML = `<div class="reply-status err">ยังไม่ได้ตั้งข้อความตอบกลับ (ดู config auto_reply.reply_message)</div>`;
    logEvent(`ตอบกลับ ${btn.dataset.id} ไม่ได้: ไม่มีข้อความ default`, "err");
    return;
  }
  btn.disabled = true;
  slot.innerHTML = `<div class="reply-status">กำลังส่ง "${esc(message)}"...</div>`;
  const status = slot.querySelector(".reply-status");
  logEvent(`ส่งตอบกลับถึง ${commentEl.dataset.author || btn.dataset.id}...`);
  try {
    const res = await fetch("/api/reply", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ comment_id: btn.dataset.id, message }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || res.status);
    pollReplyJob(data.job_id, status, commentEl, slot, btn);
  } catch (err) {
    btn.disabled = false;
    status.className = "reply-status err";
    status.textContent = "ส่งไม่ได้: " + err.message;
    logEvent("ส่งตอบกลับไม่ได้: " + err.message, "err");
  }
});

async function pollReplyJob(jobId, statusEl, commentEl, slot, btn) {
  for (let i = 0; i < 60; i++) { // max ~2 min
    await new Promise((r) => setTimeout(r, 2000));
    try {
      const data = await (await fetch(`/api/reply/${jobId}`)).json();
      if (data.status === "done") {
        statusEl.className = "reply-status ok";
        statusEl.textContent = "ตอบกลับแล้ว ✓ (" + (data.detail || "") + ")";
        logEvent(`ตอบกลับ ${commentEl.dataset.author || ""} แล้ว ✓`, "ok");
        setTimeout(fetchData, 1500); // refresh to show ตอบแล้ว badge
        return;
      }
      if (data.status === "failed") {
        if (btn) btn.disabled = false;
        statusEl.className = "reply-status err";
        statusEl.textContent = "ล้มเหลว: " + (data.detail || "");
        logEvent("ตอบกลับล้มเหลว: " + (data.detail || ""), "err");
        return;
      }
      statusEl.textContent = `กำลังดำเนินการ... (${data.status === "queued" ? "รอคิว" : "เปิดเบราว์เซอร์"})`;
    } catch (e) {
      statusEl.textContent = "รอผล...";
    }
  }
  if (btn) btn.disabled = false;
  statusEl.className = "reply-status err";
  statusEl.textContent = "หมดเวลา (~2 นาที) ลองรีเฟรชดูว่าตอบไปแล้วหรือไม่";
  logEvent("ตอบกลับหมดเวลา (~2 นาที)", "err");
}

async function fetchMonitor() {
  try {
    const data = await (await fetch("/api/monitor")).json();
    document.getElementById("pg-monitor").textContent = data.monitor.running ? "ทำงาน 🟢" : "หยุด 🔴";
    document.getElementById("pg-headless").textContent = data.monitor.headless ? "เบื้องหลัง" : "มีหน้าต่าง";
    document.getElementById("pg-web").textContent = "ทำงาน 🟢";
    document.getElementById("pg-session").textContent = data.session ? data.session.modified : "ไม่มีไฟล์";
    document.getElementById("pg-dbrows").textContent = data.db.rows ?? "–";
    const box = document.getElementById("mon-log");
    const tail = data.log.tail || [];
    box.textContent = tail.length ? tail.join("\n") : "(ไม่มี log ใหม่)";
    box.scrollTop = box.scrollHeight;
    if (!data.monitor.running && state.monitorWasRunning !== false) {
      logEvent("มอนิเตอร์หยุดทำงาน!", "err");
    }
    if (data.monitor.running && state.monitorWasRunning === false) {
      logEvent("มอนิเตอร์กลับมาทำงานแล้ว", "ok");
    }
    state.monitorWasRunning = data.monitor.running;
  } catch (e) { /* next tick retries */ }
}

// Events
document.getElementById("sort").value = state.sort;
document.getElementById("sort").addEventListener("change", (e) => { state.sort = e.target.value; fetchData(); });
document.getElementById("poll-ms").addEventListener("change", (e) => {
  let ms = parseInt(e.target.value, 10);
  if (Number.isNaN(ms)) ms = 3000;
  ms = Math.min(60000, Math.max(500, ms));
  e.target.value = ms;
  state.pollMs = ms;
  resetPollTimer();
  fetchData();
});
document.getElementById("refresh-now").addEventListener("click", fetchData);
document.getElementById("add-post-btn").addEventListener("click", addPost);
document.getElementById("new-post-url").addEventListener("keydown", (e) => {
  if (e.key === "Enter") addPost();
});
["search", "owner-only", "unreplied-only", "new-only"].forEach((id) => {
  document.getElementById(id === "search" ? "search" : id).addEventListener(id === "search" ? "input" : "change", applyFilters);
});
setInterval(() => { if (state.data) render(state.data); }, 30000); // refresh relative times

// First paint from server-embedded JSON, then go live
try {
  render(window.__INITIAL__);
  document.getElementById("live-dot").classList.add("on");
  document.getElementById("live-text").textContent = liveLabel();
} catch (e) {
  fetchData();
}
resetPollTimer();
setTimeout(fetchData, 3000);
fetchMonitor();
setInterval(fetchMonitor, 5000);
