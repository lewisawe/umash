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

  // Small, dignified per-phase line art (ink line, single lime accent).
  // dawn = immediate · candle = funeral · letter = admin · sprig = aftercare.
  const _svg = (inner) => `<svg viewBox="0 0 32 32" width="26" height="26" fill="none" aria-hidden="true">${inner}</svg>`;
  const PHASE_ART = {
    immediate: _svg('<circle cx="16" cy="20" r="7" fill="#cdfe00"/><line x1="3" y1="20" x2="29" y2="20" stroke="#0a1217" stroke-width="1.5"/>'),
    funeral:   _svg('<rect x="13" y="14" width="6" height="12" rx="2" fill="none" stroke="#0a1217" stroke-width="1.5"/><path d="M16 14c3-2 3-6 0-8-3 2-3 6 0 8z" fill="#cdfe00"/>'),
    admin:     _svg('<rect x="6" y="10" width="20" height="14" rx="3" fill="none" stroke="#0a1217" stroke-width="1.5"/><path d="M6 12l10 7 10-7" stroke="#0a1217" stroke-width="1.5" fill="none"/>'),
    aftercare: _svg('<line x1="16" y1="27" x2="16" y2="12" stroke="#0a1217" stroke-width="1.5"/><path d="M16 17c-3-1-5 0-7-2M16 14c3-1 5-1 7-3" stroke="#0a1217" stroke-width="1.5" stroke-linecap="round"/><circle cx="21" cy="10" r="2.5" fill="#cdfe00"/>'),
  };

  // Inline clock icon (not an emoji — emojis render inconsistently and aren't
  // controllable design tokens). aria-hidden; the text beside it carries meaning.
  const CLOCK = '<svg class="clock" width="13" height="13" viewBox="0 0 16 16" fill="none" aria-hidden="true"><circle cx="8" cy="8" r="6.5" stroke="currentColor" stroke-width="1.3"/><path d="M8 4.5V8l2.5 1.5" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg>';

  function deadlineText(days) {
    return `due in ${days} day${days === 1 ? "" : "s"}`;
  }

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
  let openPhase = null;   // which phase is expanded (one at a time); null = all collapsed

  function renderDash() {
    const c = current;
    const restName = JURISDICTION_NAME[c.restIn];
    const diedName = JURISDICTION_NAME[c.diedIn];
    $("case-title").textContent = c.name.charAt(0).toUpperCase() + c.name.slice(1);
    const meta = $("case-meta"); meta.innerHTML = "";
    meta.appendChild(el("span", null, `Died in ${esc(diedName)}`));
    meta.appendChild(el("span", null, `Laid to rest in ${esc(restName)}`));
    if (c.crossBorder) meta.appendChild(el("span", null, `repatriation ${esc(diedName)} → ${esc(restName)}`));
    if (c.faith && window.Umash.FAITHS[c.faith]) meta.appendChild(el("span", null, `${esc(window.Umash.FAITHS[c.faith].label)} tradition`));

    const s = c.summary();
    const decisionsLeft = c.pendingEscalations().length;
    const routineLeft = c.routine().filter(t => !c.isResolved(t)).length;

    // one quiet status line (was a 4-card metric grid + two big bars)
    const status = $("status-line"); status.innerHTML = "";
    status.appendChild(frag(`<b>${s.resolved}</b> of <b>${s.total}</b> steps handled`));
    if (decisionsLeft) status.appendChild(frag(` · <b>${decisionsLeft}</b> decision${decisionsLeft === 1 ? "" : "s"} for you`));
    if (routineLeft) status.appendChild(frag(` · <b>${routineLeft}</b> routine prepared`));
    $("rail").style.width = s.total ? `${Math.round(100 * s.resolved / s.total)}%` : "0%";

    renderFocus(c, decisionsLeft, routineLeft);
    renderPhases(c);
    if (window.Umash.wireImages) window.Umash.wireImages();
  }

  // small helper: build an element from an HTML string fragment (inline spans)
  function frag(html) { const s = document.createElement("span"); s.innerHTML = html; return s; }

  // THE focal point — one thing to look at.
  function renderFocus(c, decisionsLeft, routineLeft) {
    const slot = $("focus-slot"); slot.innerHTML = "";
    const unresolved = c.tasks.filter(t => !c.isResolved(t));

    if (unresolved.length === 0) {
      const done = el("div", "done-state");
      done.appendChild(el("h3", null, "You've done everything for now."));
      done.appendChild(el("p", null,
        `Every step for ${esc(c.name)} has been handled or decided. There is nothing waiting on you. Rest.`));
      slot.appendChild(done);
      return;
    }

    const next = c.pendingEscalations()[0];
    if (next) {
      // lead with the single most urgent decision
      const card = el("div", "next-action");
      const txt = el("div", "grow");
      txt.appendChild(el("div", "next-action__label", "Your most urgent decision"));
      txt.appendChild(el("div", "next-action__title", esc(next.title)));
      card.appendChild(txt);
      const btn = el("button", "btn btn--lime", "Review it");
      btn.onclick = () => openEscalationFor(next.id);
      card.appendChild(btn);
      slot.appendChild(card);
    } else if (routineLeft) {
      // no decisions pending — the only thing left is to approve routine work, quietly
      const card = el("div", "next-action next-action--calm");
      const txt = el("div", "grow");
      txt.appendChild(el("div", "next-action__label", "No decisions need you right now"));
      txt.appendChild(el("div", "next-action__title",
        `${routineLeft} routine task${routineLeft === 1 ? "" : "s"} prepared, ready to approve together`));
      card.appendChild(txt);
      const btn = el("button", "btn btn--ink", "Approve all");
      btn.onclick = approveBatch;
      card.appendChild(btn);
      slot.appendChild(card);
    }
  }

  // Phases as collapsible summary rows — the eye sees four, not forty-two.
  function renderPhases(c) {
    const wrap = $("phases"); wrap.innerHTML = "";
    for (const phase of PHASE_ORDER) {
      const tasks = c.tasks.filter(t => t.phase === phase);
      if (!tasks.length) continue;
      const done = tasks.filter(t => c.isResolved(t)).length;
      const decisions = tasks.filter(t => t.weighty && !c.isResolved(t));
      const routine = tasks.filter(t => !t.weighty);

      const details = el("details", "phase");
      details.open = (openPhase === phase);
      details.addEventListener("toggle", () => {
        if (details.open) { openPhase = phase; renderPhases(c); }
        else if (openPhase === phase) { openPhase = null; }
      });

      // summary row
      const sum = el("summary", "phase__summary");
      const icon = el("span", "phase__icon"); icon.innerHTML = PHASE_ART[phase] || "";
      sum.appendChild(icon);
      sum.appendChild(el("span", "phase__name", esc(PHASE_LABEL[phase].split("—")[0].trim())));
      const bar = el("span", "phase__bar");
      const fill = el("span"); fill.style.width = `${Math.round(100 * done / tasks.length)}%`;
      bar.appendChild(fill); sum.appendChild(bar);
      // quiet meta: decisions first (the thing that matters), then routine count
      const parts = [];
      if (decisions.length) parts.push(`${decisions.length} decision${decisions.length === 1 ? "" : "s"}`);
      if (routine.length) parts.push(`${routine.length} routine`);
      parts.push(`${done}/${tasks.length} done`);
      sum.appendChild(el("span", "phase__meta", parts.join(" · ")));
      sum.appendChild(chevron());
      details.appendChild(sum);

      // body (only rendered/visible when open)
      const body = el("div", "phase__body");
      // decisions get their own rows
      decisions.forEach(t => body.appendChild(renderDecision(t)));
      // any resolved weighty (show quietly so the record is complete)
      tasks.filter(t => t.weighty && c.isResolved(t)).forEach(t => body.appendChild(renderDecision(t)));
      // routine folded into one quiet group
      if (routine.length) body.appendChild(renderRoutineGroup(routine));
      details.appendChild(body);

      wrap.appendChild(details);
    }
  }

  function chevron() {
    const s = el("span", "phase__chevron");
    s.innerHTML = '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M6 4l4 4-4 4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>';
    return s;
  }

  // A decision row — the only kind that gets its own card. Minimal chrome:
  // title, who it's directed at, a deadline only when it's genuinely soon, and
  // the action. No "Decision"/"Drafted" chips — being here already says enough.
  function renderDecision(t) {
    const c = current;
    const row = el("article", "task task--decision");
    const top = el("div", "task__top");
    const left = el("div", "grow");
    left.appendChild(el("div", "task__title", esc(t.title)));
    left.appendChild(el("div", "task__target", `Directed at ${esc(t.target)}`));
    // deadline shown only when it actually matters (soon), reserving red for urgency
    if (t.deadlineDays != null && t.deadlineDays <= 7) {
      const soon = t.deadlineDays <= 2;
      const tags = el("div", "task__tags");
      tags.appendChild(el("span", `deadline${soon ? " deadline--soon" : ""}`,
        `${CLOCK} ${deadlineText(t.deadlineDays)}`));
      left.appendChild(tags);
    }
    top.appendChild(left);

    const actions = el("div", "task__actions");
    if (!c.isResolved(t)) {
      const b = el("button", "btn btn--ink btn--sm", "Decide");
      b.onclick = () => openEscalationFor(t.id);
      actions.appendChild(b);
    } else if (t.status === "approved") {
      const b = el("button", "btn btn--ghost-light btn--sm", "Mark sent");
      b.onclick = () => { c.markSent(t.id); persist(); renderDash(); toast("Marked as sent by you"); };
      actions.appendChild(b);
    } else if (t.status === "sent") {
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

  // Routine work stays quiet: one collapsed group, not a card per task.
  function renderRoutineGroup(routine) {
    const c = current;
    const pending = routine.filter(t => !c.isResolved(t));
    const details = el("details", "routine-group");
    const head = el("summary", "routine-group__head");
    const label = pending.length
      ? frag(`<b>${pending.length}</b> routine task${pending.length === 1 ? "" : "s"} prepared, batched for one approval`)
      : frag(`<b>${routine.length}</b> routine task${routine.length === 1 ? "" : "s"} — all approved`);
    head.appendChild(label);
    head.appendChild(chevron());
    details.appendChild(head);

    const list = el("div", "routine-group__list");
    routine.forEach(t => {
      const item = el("div", "routine-item");
      const dot = el("span", `dot dot--${t.status}`);
      item.appendChild(dot);
      item.appendChild(el("span", null, esc(t.title)));
      item.appendChild(el("span", "routine-item__target", esc(t.target)));
      list.appendChild(item);
    });
    details.appendChild(list);
    return details;
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
  let lastFocused = null;   // element to restore focus to when the modal closes

  function openModal() {
    lastFocused = document.activeElement;
    const scrim = $("scrim");
    scrim.hidden = false;
    scrim.classList.add("open");
    document.addEventListener("keydown", trapFocus, true);
  }

  function openEscalationFor(id) {
    // review a single decision, but keep the "most urgent first" queue behind it
    queue = current.pendingEscalations().map(t => t.id);
    queueIndex = Math.max(0, queue.indexOf(id));
    openModal();
    renderModal();
  }

  // Keep Tab focus inside the dialog while it is open.
  function trapFocus(e) {
    if (e.key !== "Tab") return;
    const scrim = $("scrim");
    if (scrim.hidden) return;
    const focusable = scrim.querySelectorAll(
      'button:not([disabled]), input, [href], [tabindex]:not([tabindex="-1"])');
    if (!focusable.length) return;
    const first = focusable[0], last = focusable[focusable.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
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
      dl.innerHTML = `${CLOCK} ${deadlineText(t.deadlineDays)}`;
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

  function closeModal() {
    const scrim = $("scrim");
    scrim.classList.remove("open");
    scrim.hidden = true;
    document.removeEventListener("keydown", trapFocus, true);
    if (lastFocused && typeof lastFocused.focus === "function") lastFocused.focus();
    lastFocused = null;
  }

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
      del.setAttribute("aria-label", `Delete the case for ${c.name}`);
      del.onclick = () => {
        // Two-step confirm — deleting a case is destructive with no undo.
        if (del.dataset.confirm === "1") { Store.remove(id); renderCases(); return; }
        del.dataset.confirm = "1";
        del.textContent = "Confirm delete";
        del.classList.add("btn--danger");
        clearTimeout(del._t);
        del._t = setTimeout(() => {
          del.dataset.confirm = ""; del.textContent = "Delete";
          del.classList.remove("btn--danger");
        }, 3500);
      };
      actions.appendChild(open); actions.appendChild(del);
      top.appendChild(actions);
      card.appendChild(top);
      list.appendChild(card);
    });
  }

  // ---------------------------------------------------------------- wiring
  $("btn-create").onclick = createCase;
  $("btn-new-nav").onclick = () => show("view-create");
  $("link-cases").onclick = (e) => { e.preventDefault(); renderCases(); show("view-cases"); };
  $("scrim").onclick = (e) => { if (e.target === $("scrim")) closeModal(); };
  $("m-close").onclick = closeModal;
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !$("scrim").hidden) closeModal();
  });

  // boot: last case if any, else create
  const ids = Store.ids();
  if (ids.length) { current = Store.load(ids[ids.length - 1]); renderDash(); show("view-dash"); }
  else { show("view-create"); }
})();
