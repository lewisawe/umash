/* ============================================================================
   Umash — app view logic
   Renders a case, drives the batch-then-escalate flow, and enforces the
   safety invariant through the UI (approve is disabled until a decision is
   typed; the data layer refuses regardless).
   ========================================================================== */
(function () {
  const { CaseState, Store, PHASE_ORDER, PHASE_LABEL, JURISDICTION_NAME } = window.Umash;

  const $ = (id) => document.getElementById(id);
  const el = (tag, cls, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; };
  const esc = (s) => (s || "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  let current = null;          // active CaseState
  let queue = [];              // escalation queue (task ids)
  let queueIndex = 0;

  const STATUS_LABEL = { pending: "Pending", drafted: "Drafted", approved: "Approved",
                         sent: "Sent", confirmed: "Confirmed", declined: "Declined" };

  // Small, dignified per-phase line art (ink line, single lime accent).
  // dawn = immediate · candle = funeral · letter = admin · sprig = aftercare.
  const _svg = (inner) => `<svg viewBox="0 0 32 32" width="26" height="26" fill="none" aria-hidden="true">${inner}</svg>`;
  const PHASE_ART = {
    immediate: _svg('<circle cx="16" cy="20" r="7" fill="#cdfe00"/><line x1="3" y1="20" x2="29" y2="20" stroke="#0a1217" stroke-width="1.5"/>'),
    funeral:   _svg('<rect x="13" y="14" width="6" height="12" rx="2" fill="none" stroke="#0a1217" stroke-width="1.5"/><path d="M16 14c3-2 3-6 0-8-3 2-3 6 0 8z" fill="#cdfe00"/>'),
    admin:     _svg('<rect x="6" y="10" width="20" height="14" rx="3" fill="none" stroke="#0a1217" stroke-width="1.5"/><path d="M6 12l10 7 10-7" stroke="#0a1217" stroke-width="1.5" fill="none"/>'),
    aftercare: _svg('<line x1="16" y1="27" x2="16" y2="12" stroke="#0a1217" stroke-width="1.5"/><path d="M16 17c-3-1-5 0-7-2M16 14c3-1 5-1 7-3" stroke="#0a1217" stroke-width="1.5" stroke-linecap="round"/><circle cx="21" cy="10" r="2.5" fill="#cdfe00"/>'),
  };

  // ---------------------------------------------------------------- views
  function show(view) {
    ["view-create", "view-dash", "view-cases"].forEach(v => $(v).hidden = (v !== view));
  }

  function toast(msg) {
    const t = $("toast"); t.textContent = msg; t.classList.add("show");
    clearTimeout(t._timer); t._timer = setTimeout(() => t.classList.remove("show"), 2200);
  }

  function persist() { if (current) Store.save(current); }

  // ---------------------------------------------------------------- create
  function createCase() {
    const name = $("f-name").value.trim() || "the deceased";
    const died = $("f-died").value;
    const rest = $("f-rest").value;
    const faith = $("f-faith").value || null;
    const id = `${name.replace(/[^a-z0-9]+/gi, "-").toLowerCase()}-${Date.now().toString(36)}`.slice(0, 40);
    current = CaseState.build(id, died, rest, name, faith);
    // Umash prepares routine drafts quietly as soon as the plan is built.
    current.routine().forEach(t => current.recordDraft(t.id));
    current.weighty().forEach(t => current.recordDraft(t.id));  // decision-prompt draft
    persist();
    renderDash();
    show("view-dash");
  }

  // ---------------------------------------------------------------- dash
  function renderDash() {
    const c = current;
    const restName = JURISDICTION_NAME[c.restIn];
    const diedName = JURISDICTION_NAME[c.diedIn];
    $("case-title").textContent = c.name.charAt(0).toUpperCase() + c.name.slice(1);
    const meta = $("case-meta"); meta.innerHTML = "";
    meta.appendChild(el("span", null, `Died in ${esc(diedName)}`));
    meta.appendChild(el("span", null, `Laid to rest in ${esc(restName)}`));
    if (c.crossBorder) meta.appendChild(el("span", null, `Cross-border · repatriation ${esc(diedName)} → ${esc(restName)}`));
    if (c.faith && window.Umash.FAITHS[c.faith]) meta.appendChild(el("span", null, `${esc(window.Umash.FAITHS[c.faith].label)} tradition`));

    // metrics
    const s = c.summary();
    const metrics = $("metrics"); metrics.innerHTML = "";
    [["Total steps", s.total], ["Routine", s.routine], ["Decisions", s.weighty], ["Resolved", s.resolved]]
      .forEach(([label, n]) => {
        const m = el("div", "metric");
        m.appendChild(el("div", "metric__n", String(n)));
        m.appendChild(el("div", "metric__l", label));
        metrics.appendChild(m);
      });
    $("rail").style.width = s.total ? `${Math.round(100 * s.resolved / s.total)}%` : "0%";

    // batch bar — visible only while routine work is unapproved
    const routinePending = c.routine().filter(t => !c.isResolved(t));
    $("batchbar").hidden = routinePending.length === 0;
    $("batch-title").textContent = `${routinePending.length} routine task${routinePending.length === 1 ? "" : "s"}, prepared quietly`;

    // escalation bar
    const escalations = c.pendingEscalations();
    $("escbar").hidden = escalations.length === 0;
    $("esc-title").textContent = `${escalations.length} decision${escalations.length === 1 ? "" : "s"} waiting`;

    // phases
    const wrap = $("phases"); wrap.innerHTML = "";
    for (const phase of PHASE_ORDER) {
      const tasks = c.tasks.filter(t => t.phase === phase);
      if (!tasks.length) continue;
      const group = el("section", "phase");
      const label = el("div", "phase__label");
      const icon = el("span", "phase__icon");
      icon.innerHTML = PHASE_ART[phase] || "";
      label.appendChild(icon);
      label.appendChild(el("h2", null, esc(PHASE_LABEL[phase])));
      const done = tasks.filter(t => c.isResolved(t)).length;
      label.appendChild(el("span", "phase__count", `${done} / ${tasks.length} resolved`));
      group.appendChild(label);
      tasks.forEach(t => group.appendChild(renderTask(t)));
      wrap.appendChild(group);
    }
    if (window.Umash.wireImages) window.Umash.wireImages();
  }

  function renderTask(t) {
    const c = current;
    const row = el("article", "task");
    const top = el("div", "task__top");

    const left = el("div", "grow");
    left.appendChild(el("div", "task__title", esc(t.title)));
    left.appendChild(el("div", "task__target", `Directed at ${esc(t.target)}`));
    const tags = el("div", "task__tags"); tags.style.marginTop = "8px";

    // status dot + label
    const st = el("span", "tag");
    st.style.borderColor = "var(--color-frost-wash)";
    st.appendChild(el("span", `dot dot--${t.status}`));
    st.appendChild(document.createTextNode(" " + STATUS_LABEL[t.status]));
    tags.appendChild(st);

    // routine / weighty
    tags.appendChild(el("span", t.weighty ? "tag tag--weighty" : "tag tag--routine",
      t.weighty ? "Decision" : "Routine"));

    // deadline
    if (t.deadlineDays != null) {
      const soon = t.deadlineDays <= 3;
      tags.appendChild(el("span", `deadline${soon ? " deadline--soon" : ""}`,
        `⏱ due in ${t.deadlineDays} day${t.deadlineDays === 1 ? "" : "s"}`));
    }
    left.appendChild(tags);
    top.appendChild(left);

    // actions depend on state
    const actions = el("div", "task__actions");
    if (t.weighty && !c.isResolved(t)) {
      const b = el("button", "btn btn--ink btn--sm", "Decide");
      b.onclick = () => openEscalationFor(t.id);
      actions.appendChild(b);
    }
    if (t.status === "approved") {
      const b = el("button", "btn btn--ghost-light btn--sm", "Mark sent");
      b.onclick = () => { c.markSent(t.id); persist(); renderDash(); toast("Marked as sent by you"); };
      actions.appendChild(b);
    }
    if (t.status === "sent") {
      const b = el("button", "btn btn--ghost-light btn--sm", "Mark confirmed");
      b.onclick = () => { c.confirm(t.id); persist(); renderDash(); toast("Institution confirmed"); };
      actions.appendChild(b);
    }
    top.appendChild(actions);
    row.appendChild(top);

    if (t.decision) {
      row.appendChild(el("div", "task__decision", `<strong>Your decision:</strong> ${esc(t.decision)}`));
    }
    return row;
  }

  // ---------------------------------------------------------------- batch
  function approveBatch() {
    const c = current;
    let n = 0;
    c.routine().forEach(t => { if (!c.isResolved(t)) { c.approve(t.id); n++; } });
    persist(); renderDash();
    toast(`${n} routine task${n === 1 ? "" : "s"} approved in one batch`);
  }

  // ---------------------------------------------- escalation flow (queue)
  function startEscalations() {
    queue = current.pendingEscalations().map(t => t.id);
    queueIndex = 0;
    if (!queue.length) return;
    renderModal();
    $("scrim").classList.add("open");
  }

  function openEscalationFor(id) {
    // review a single decision, but keep the "most urgent first" queue behind it
    queue = current.pendingEscalations().map(t => t.id);
    queueIndex = Math.max(0, queue.indexOf(id));
    renderModal();
    $("scrim").classList.add("open");
  }

  function renderModal() {
    const c = current;
    // skip past any that got resolved
    while (queueIndex < queue.length && c.isResolved(c.get(queue[queueIndex]))) queueIndex++;
    if (queueIndex >= queue.length) { closeModal(); renderDash(); return; }

    const t = c.get(queue[queueIndex]);
    $("m-queue").textContent = `Decision ${queueIndex + 1} of ${queue.length} · most urgent first`;
    $("m-title").textContent = t.title;
    $("m-target").textContent = `Directed at ${t.target}`;
    const dl = $("m-deadline");
    if (t.deadlineDays != null) {
      dl.textContent = `⏱ due in ${t.deadlineDays} day${t.deadlineDays === 1 ? "" : "s"}`;
      dl.className = "deadline" + (t.deadlineDays <= 3 ? " deadline--soon" : "");
    } else { dl.textContent = "no fixed deadline"; dl.className = "deadline muted"; }

    const reasons = $("m-reasons"); reasons.innerHTML = "";
    t.reasons.forEach(r => reasons.appendChild(el("li", null, esc(r))));
    $("m-draft").textContent = t.draft;

    const note = $("m-note"); note.value = t.decision || "";
    // SAFETY INVARIANT in the UI: approve stays disabled until a decision exists
    const approveBtn = $("m-approve");
    const sync = () => { approveBtn.disabled = note.value.trim().length === 0; };
    note.oninput = sync; sync();
    note.focus();

    approveBtn.onclick = () => {
      const decision = note.value.trim();
      try {
        c.approve(t.id, decision);         // data layer double-checks the invariant
        persist();
        toast("Decision recorded, task approved");
        queueIndex++; renderModal(); renderDash();
      } catch (e) { toast(e.message); }
    };
    $("m-decline").onclick = () => {
      c.decline(t.id, note.value.trim());
      persist(); toast("Declined and recorded");
      queueIndex++; renderModal(); renderDash();
    };
    $("m-skip").onclick = () => { queueIndex++; renderModal(); if (queueIndex >= queue.length) renderDash(); };
  }

  function closeModal() { $("scrim").classList.remove("open"); }

  // ---------------------------------------------------------------- cases
  function renderCases() {
    const list = $("cases-list"); list.innerHTML = "";
    const ids = Store.ids();
    if (!ids.length) { list.appendChild(el("div", "empty", "No cases yet. Open one to begin.")); return; }
    ids.forEach(id => {
      const c = CaseState.fromJSON(Store.all()[id]);
      const s = c.summary();
      const card = el("article", "task");
      const top = el("div", "task__top");
      const left = el("div", "grow");
      left.appendChild(el("div", "task__title", esc(c.name)));
      left.appendChild(el("div", "task__target",
        `${JURISDICTION_NAME[c.diedIn]} → ${JURISDICTION_NAME[c.restIn]} · ${s.resolved}/${s.total} resolved · ${s.pendingEscalations} decision(s) waiting`));
      top.appendChild(left);
      const actions = el("div", "task__actions");
      const open = el("button", "btn btn--ink btn--sm", "Open");
      open.onclick = () => { current = c; renderDash(); show("view-dash"); };
      const del = el("button", "btn btn--ghost-light btn--sm", "Delete");
      del.onclick = () => { Store.remove(id); renderCases(); };
      actions.appendChild(open); actions.appendChild(del);
      top.appendChild(actions);
      card.appendChild(top);
      list.appendChild(card);
    });
  }

  // ---------------------------------------------------------------- wiring
  $("btn-create").onclick = createCase;
  $("btn-batch").onclick = approveBatch;
  $("btn-esc").onclick = startEscalations;
  $("btn-new-nav").onclick = () => show("view-create");
  $("link-cases").onclick = (e) => { e.preventDefault(); renderCases(); show("view-cases"); };
  $("scrim").onclick = (e) => { if (e.target === $("scrim")) closeModal(); };
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });

  // boot: last case if any, else create
  const ids = Store.ids();
  if (ids.length) { current = Store.load(ids[ids.length - 1]); renderDash(); show("view-dash"); }
  else { show("view-create"); }
})();
