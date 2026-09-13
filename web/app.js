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
    renderTrace(c);
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
      const isOpen = (openPhase === phase);

      const section = el("section", "phase" + (isOpen ? " open" : ""));

      // summary row — a real button for keyboard + screen readers
      const sum = el("div", "phase__summary");
      sum.setAttribute("role", "button");
      sum.tabIndex = 0;
      sum.setAttribute("aria-expanded", isOpen ? "true" : "false");
      const bodyId = `phase-body-${phase}`;
      sum.setAttribute("aria-controls", bodyId);
      const icon = el("span", "phase__icon"); icon.innerHTML = PHASE_ART[phase] || "";
      sum.appendChild(icon);
      sum.appendChild(el("span", "phase__name", esc(PHASE_LABEL[phase].split("—")[0].trim())));
      const bar = el("span", "phase__bar");
      const fill = el("span"); fill.style.width = `${Math.round(100 * done / tasks.length)}%`;
      bar.appendChild(fill); sum.appendChild(bar);
      const parts = [];
      if (decisions.length) parts.push(`${decisions.length} decision${decisions.length === 1 ? "" : "s"}`);
      if (routine.length) parts.push(`${routine.length} routine`);
      parts.push(`${done}/${tasks.length} done`);
      sum.appendChild(el("span", "phase__meta", parts.join(" · ")));
      sum.appendChild(chevron());
      section.appendChild(sum);

      // body (always in the DOM so it can animate; collapsed via grid-rows)
      const body = el("div", "phase__body"); body.id = bodyId;
      const inner = el("div", "phase__bodyInner");
      decisions.forEach(t => inner.appendChild(renderDecision(t)));
      tasks.filter(t => t.weighty && c.isResolved(t)).forEach(t => inner.appendChild(renderDecision(t)));
      if (routine.length) inner.appendChild(renderRoutineGroup(routine));
      body.appendChild(inner);
      section.appendChild(body);

      const toggle = () => {
        const nowOpen = !section.classList.contains("open");
        // accordion: close the others, open this one
        wrap.querySelectorAll(".phase.open").forEach(p => {
          if (p !== section) { p.classList.remove("open"); p.querySelector(".phase__summary").setAttribute("aria-expanded", "false"); }
        });
        section.classList.toggle("open", nowOpen);
        sum.setAttribute("aria-expanded", nowOpen ? "true" : "false");
        openPhase = nowOpen ? phase : null;
      };
      sum.addEventListener("click", toggle);
      sum.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); }
      });

      wrap.appendChild(section);
    }
  }

  function chevron() {
    const s = el("span", "phase__chevron");
    s.innerHTML = '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M6 4l4 4-4 4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>';
    return s;
  }

  // The agent's decision flow as boxes-and-arrows. Nodes come from buildTrace()
  // in data.js — the same policy the real Strands agent runs. Boxes fade in in
  // sequence so a viewer watches the agent "work"; weighty outcomes are
  // clickable and jump straight to that decision.
  let _traceTimers = [];
  function renderTrace(c, animate = true) {
    const wrap = $("trace");
    if (!wrap) return;
    _traceTimers.forEach(clearTimeout); _traceTimers = [];
    wrap.innerHTML = "";

    const nodes = window.Umash.buildTrace(c);
    const boxes = [];
    nodes.forEach((n) => {
      const node = el("div", "trace__node");
      let cls = "trace__box trace__box--" + n.kind;
      if (n.kind === "outcome") cls += n.weighty ? " is-weighty" : " is-routine";
      const box = el("div", cls);

      const toolLabel = { intake: "read", build_journey_plan: "build_journey_plan",
                          classify_consequence: "classify_consequence" }[n.tool] || n.tool;
      box.appendChild(el("div", "trace__tool", esc(toolLabel)));
      box.appendChild(el("div", "trace__label", esc(n.label)));
      if (n.detail) box.appendChild(el("div", "trace__detail", esc(n.detail)));

      // weighty outcomes that are still pending jump to the decision
      if (n.weighty && n.taskId) {
        box.dataset.taskId = n.taskId;
        if (!c.isResolved(c.get(n.taskId))) {
          box.classList.add("trace__box--clickable");
          box.setAttribute("role", "button");
          box.tabIndex = 0;
          const go = () => openEscalationFor(n.taskId);
          box.onclick = go;
          box.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(); } };
        }
      }

      node.appendChild(box);
      wrap.appendChild(node);
      boxes.push(box);
    });

    // stagger the fade-in (skip the animation if reduced-motion is set).
    // STEP_MS controls the pace — higher = the agent looks like it's thinking
    // through each step. Reduced-motion users get the whole trace at once.
    const STEP_MS = 420;
    const reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!animate || reduce) { boxes.forEach(b => b.classList.add("in")); return; }
    boxes.forEach((b, k) => {
      _traceTimers.push(setTimeout(() => {
        b.classList.add("in", "landing");
        // remove the brief "just landed" accent so only the newest box pulses
        _traceTimers.push(setTimeout(() => b.classList.remove("landing"), STEP_MS));
      }, STEP_MS * k));
    });
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
    const group = el("div", "routine-group");
    const head = el("div", "routine-group__head");
    head.setAttribute("role", "button");
    head.tabIndex = 0;
    head.setAttribute("aria-expanded", "false");
    const label = pending.length
      ? frag(`<b>${pending.length}</b> routine task${pending.length === 1 ? "" : "s"} prepared, batched for one approval`)
      : frag(`<b>${routine.length}</b> routine task${routine.length === 1 ? "" : "s"} — all approved`);
    head.appendChild(label);
    head.appendChild(chevron());
    group.appendChild(head);

    const body = el("div", "routine-group__body");
    const list = el("div", "routine-group__list");
    routine.forEach(t => {
      const item = el("div", "routine-item");
      item.appendChild(el("span", `dot dot--${t.status}`));
      item.appendChild(el("span", null, esc(t.title)));
      item.appendChild(el("span", "routine-item__target", esc(t.target)));
      list.appendChild(item);
    });
    body.appendChild(list);
    group.appendChild(body);

    const toggle = () => {
      const open = group.classList.toggle("open");
      head.setAttribute("aria-expanded", open ? "true" : "false");
    };
    head.addEventListener("click", toggle);
    head.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); }
    });
    return group;
  }

  // ---------------------------------------------------------------- batch
  function approveBatch() {
    const c = current;
    let n = 0;
    c.routine().forEach(t => { if (!c.isResolved(t)) { c.approve(t.id); n++; } });
    persist(); renderDash();
    toast(`${n} routine task${n === 1 ? "" : "s"} approved in one batch`);
  }

  // ---------------------------------------------- auto-run (hands-off demo)
  // Drives the REAL app end to end, no clicks: reveal the plan + trace, batch
  // routine quietly, then surface each weighty decision one at a time and record
  // a (clearly simulated) decision — pacing the whole thing to ~3 minutes.
  // It still only drafts and records; nothing is filed, paid, or sent. The
  // autonomy is in the coordination, exactly as the product promises.
  let _auto = { running: false, timers: [] };

  function autoCaption(text, pulse = true) {
    const cap = $("autorun-caption");
    if (!cap) return;
    cap.hidden = false;
    cap.innerHTML = "";
    if (pulse) cap.appendChild(el("span", "dot-pulse"));
    cap.appendChild(el("span", null, esc(text)));
  }

  function autoStop(finished) {
    _auto.timers.forEach(clearTimeout); _auto.timers = [];
    _auto.running = false;
    const btn = $("btn-autorun");
    if (btn) { btn.textContent = "▶ Auto-run"; btn.classList.remove("btn--danger"); btn.classList.add("btn--lime"); }
    if (!finished) { const cap = $("autorun-caption"); if (cap) cap.hidden = true; }
  }

  // a plausible, clearly-simulated decision per weighty task
  function simulatedDecision(t) {
    const title = t.title.toLowerCase();
    if (title.includes("organ") || title.includes("tissue"))
      return "Decline donation — honouring his stated wishes. (demo decision)";
    if (title.includes("hospital bill") || title.includes("release the body"))
      return "Yes — settle from the joint account so the body can be released. (demo decision)";
    if (title.includes("repatriate"))
      return "Repatriate to the UK, as the family wishes. (demo decision)";
    if (title.includes("benefit") || title.includes("claim"))
      return "Proceed with the claim; I have the documents. (demo decision)";
    if (title.includes("bank") || title.includes("succession") || title.includes("estate"))
      return "Begin succession; I'll act as executor. (demo decision)";
    return "Approved — go ahead. (demo decision)";
  }

  function schedule(fn, delay) {
    return new Promise((resolve) => {
      _auto.timers.push(setTimeout(() => { fn && fn(); resolve(); }, delay));
    });
  }

  async function autoRun() {
    if (_auto.running) { autoStop(false); renderDash(); return; }
    const c = current;
    if (!c) return;

    // reset to a clean, un-acted state so the run always starts fresh
    c.tasks.forEach(t => {
      t.status = "pending"; t.decision = ""; t.draft = "";
      t.history = [{ event: "added", at: Date.now() }];
    });
    c.routine().forEach(t => c.recordDraft(t.id));
    c.weighty().forEach(t => c.recordDraft(t.id));
    persist(); renderDash();

    _auto.running = true;
    const btn = $("btn-autorun");
    if (btn) { btn.textContent = "■ Stop"; btn.classList.remove("btn--lime"); btn.classList.add("btn--danger"); }

    // pacing: aim ~3 min. plan+trace ~10s, routine ~6s, then the decisions
    // share the rest, each getting a readable dwell.
    const weighty = c.pendingEscalations();
    autoCaption("Reading the situation and building the jurisdiction-aware plan…");
    renderTrace(c, true);                     // the boxes-and-arrows draw themselves
    await schedule(null, 8000);
    if (!_auto.running) return;

    autoCaption(`Preparing ${c.routine().length} routine tasks quietly, batching them into one approval…`);
    await schedule(() => { approveBatch(); }, 6000);
    if (!_auto.running) return;

    // per-decision dwell so the whole run lands near ~3 min. Each decision:
    // OPEN the modal (show it being made) → approve → CLOSE (see the tree
    // update + rest on the flow) → next. The open/close rhythm is the point.
    const total = weighty.length || 1;
    const perDecision = Math.max(9000, Math.round((180000 - 14000) / total));
    const OPEN_MS = Math.round(perDecision * 0.55);   // modal visible, reading tradeoffs
    const TYPE_MS = Math.round(perDecision * 0.15);   // decision "typed" then approved
    const TREE_MS = Math.round(perDecision * 0.30);   // modal closed, resting on the tree

    for (let i = 0; i < weighty.length; i++) {
      if (!_auto.running) return;
      const t = c.get(weighty[i].id);
      if (c.isResolved(t)) continue;

      // highlight the box in the tree first, so when the modal closes the eye
      // already knows which node just resolved
      const box = document.querySelector(`.trace__box[data-task-id="${t.id}"]`);
      if (box) {
        document.querySelectorAll(".trace__box--active").forEach(b => b.classList.remove("trace__box--active"));
        box.classList.add("trace__box--active");
        box.scrollIntoView({ behavior: "smooth", block: "center" });
      }

      // 1. OPEN the modal — show the decision being weighed
      autoCaption(`Decision ${i + 1} of ${weighty.length}: ${t.title} — surfacing the tradeoffs.`);
      openEscalationFor(t.id);
      await schedule(null, OPEN_MS);
      if (!_auto.running) return;

      // 2. "type" the decision, then approve through the real safety path
      const decision = simulatedDecision(t);
      const noteEl = $("m-note");
      if (noteEl) { noteEl.value = decision; noteEl.dispatchEvent(new Event("input")); }
      await schedule(() => {
        try { c.approve(t.id, decision); persist(); } catch (e) { /* invariant */ }
      }, TYPE_MS);
      if (!_auto.running) return;

      // 3. CLOSE the modal — reveal the tree, land the decision on the box
      closeModal();
      if (box) {
        box.classList.remove("trace__box--active");
        box.classList.add("trace__box--decided");
        if (!box.querySelector(".trace__decision")) {
          box.appendChild(el("div", "trace__decision", `✓ ${esc(decision)}`));
        }
        box.scrollIntoView({ behavior: "smooth", block: "center" });
      }
      autoCaption(`Recorded. ${weighty.length - (i + 1)} decision${weighty.length - (i + 1) === 1 ? "" : "s"} left. Umash filed nothing.`, false);

      // 4. rest on the tree before the next box opens
      await schedule(null, TREE_MS);
    }

    if (!_auto.running) return;
    renderDash();
    autoCaption("Every routine task batched, every weighty decision recorded. Umash drafted everything and filed nothing.", false);
    autoStop(true);
  }



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
  $("btn-new-nav").onclick = () => { autoStop(false); show("view-create"); };
  $("link-cases").onclick = (e) => { e.preventDefault(); autoStop(false); renderCases(); show("view-cases"); };
  const replay = $("btn-replay");
  if (replay) replay.onclick = () => { if (current) renderTrace(current, true); };
  const autoBtn = $("btn-autorun");
  if (autoBtn) autoBtn.onclick = () => autoRun();
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
