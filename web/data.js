/* ============================================================================
   Umash — client data layer
   A faithful browser port of the Python policy layer:
     - jurisdiction packs (KE/UK/US + cross-border repatriation)
     - deterministic consequence classification (routine vs weighty)
     - case state machine with the SAFETY INVARIANT:
         a weighty task cannot be approved without a recorded human decision.
   No framework. Persists to localStorage so a case survives a refresh,
   mirroring ~/.umash/cases/ in the CLI.
   ========================================================================== */

// ---------------------------------------------------------------- phases
const PHASE_ORDER = ["immediate", "funeral", "admin"];
const PHASE_LABEL = {
  immediate: "Immediate — hours to days",
  funeral:   "Funeral — days to a week",
  admin:     "Admin & estate — weeks to months",
};

// ------------------------------------------------- consequence signals
// (mirrors umash/policy/consequence.py — escalation is about the DECISION)
const SIGNALS = {
  money:       ["settle the bill", "hospital bill", "pay ", "deposit", "wire", "transfer funds", "release funds", "payout"],
  legal:       ["sign for", "authorize", "authorise", "power of attorney", "probate", "estate filing", "estate succession", "begin estate", "succession", "affidavit", "notarize", "executor"],
  irreversible:["release the body", "sign for the body", "repatriate vs", "repatriate to", "cremate", "post-mortem", "autopsy", "close the account permanently", "donate organs"],
  timecritical:["time-critical", "before release", "expires"],
  claim:       ["survivor benefit", "benefit claim", "insurance claim", "claim nssf", "life-insurance benefit"],
};

function classify(text) {
  const t = (text || "").toLowerCase();
  const reasons = [];
  let weighty = false;
  for (const [label, kws] of Object.entries(SIGNALS)) {
    for (const kw of kws) {
      if (t.includes(kw)) { reasons.push(`${label}: “${kw.trim()}”`); weighty = true; break; }
    }
  }
  return weighty
    ? { weighty: true, reasons }
    : { weighty: false, reasons: ["no decision signals — routine"] };
}

// ------------------------------------------------- jurisdiction packs
// (mirrors umash/policy/jurisdictions.py)
const PACKS = {
  KE: [
    ["Obtain medical cause-of-death / burial permit", "immediate", "hospital / attending doctor", 2],
    ["Register the death (Huduma Centre / Civil Registration)", "immediate", "Civil Registration Dept", 6],
    ["Settle the hospital bill to release the body", "immediate", "hospital billing", 2],
    ["Choose mortuary and confirm holding period + daily cost", "immediate", "mortuary", 3],
    ["Engage a funeral director", "immediate", "funeral director", null],
    ["Notify employer and next of kin", "immediate", "employer / family", null],
    ["Arrange burial permit and venue", "funeral", "county / church", null],
    ["Publish obituary / death notice", "funeral", "newspaper / community", null],
    ["Coordinate funeral contributions (harambee / M-Pesa)", "funeral", "family & community", null],
    ["Claim NSSF / pension survivor benefit", "admin", "NSSF / pension", 30],
    ["Notify NHIF and close cover", "admin", "NHIF", null],
    ["Notify banks and start succession", "admin", "bank(s)", null],
    ["Cancel utilities and subscriptions", "admin", "utilities / subs", null],
    ["Begin estate succession (if assets)", "admin", "court / lawyer", null],
  ],
  UK: [
    ["Get the Medical Certificate of Cause of Death", "immediate", "hospital / GP", 2],
    ["Register the death (Register Office)", "immediate", "Register Office", 5],
    ["Use ‘Tell Us Once’ to notify govt departments", "immediate", "GOV.UK Tell Us Once", null],
    ["Engage a funeral director", "immediate", "funeral director", null],
    ["Arrange the funeral / cremation", "funeral", "funeral director", null],
    ["Publish obituary / notice", "funeral", "newspaper", null],
    ["Notify banks, pensions, insurers", "admin", "financial institutions", null],
    ["Value the estate and check probate need", "admin", "HMRC / probate", null],
    ["Cancel utilities and subscriptions", "admin", "utilities / subs", null],
  ],
  US: [
    ["Obtain the death certificate (order several copies)", "immediate", "funeral home / vital records", 5],
    ["Engage a funeral home", "immediate", "funeral home", null],
    ["Notify Social Security Administration", "immediate", "SSA", null],
    ["Arrange the funeral / burial / cremation", "funeral", "funeral home", null],
    ["Publish obituary", "funeral", "newspaper", null],
    ["File any survivor / life-insurance benefit claim", "admin", "SSA / insurer", 30],
    ["Notify banks, brokerages, creditors", "admin", "financial institutions", null],
    ["Open probate if required", "admin", "probate court", null],
    ["Cancel utilities and subscriptions", "admin", "utilities / subs", null],
  ],
};

const JURISDICTION_NAME = { KE: "Kenya", UK: "United Kingdom", US: "United States" };

function repatriationTasks(diedIn, restIn) {
  return [
    [`Decide: repatriate to ${restIn} vs bury/cremate in ${diedIn}`, "immediate", "family decision", 3],
    ["Obtain embalming certificate to ICAO standards for air transport", "immediate", "funeral director", 4],
    [`Get consular / embassy paperwork for transfer to ${restIn}`, "immediate", "embassy / high commission", 5],
    ["Arrange air cargo for repatriation of remains", "immediate", "airline cargo", null],
  ];
}

function tasksFor(diedIn, restIn) {
  let tasks = (PACKS[diedIn] || []).slice();
  if (restIn && restIn !== diedIn) {
    tasks = repatriationTasks(diedIn, restIn).concat(tasks);
  }
  return tasks;
}

// -------------------------------------------------------- draft text
// (mirrors umash/policy/drafting.py)
function buildDraft(target, task, name, weighty, reasons) {
  if (weighty) {
    const buckets = [...new Set(reasons.map(r => r.split(":")[0]))].join(", ");
    return `[NEEDS YOUR DECISION FIRST — not to be sent until you approve]\n\n` +
           `Re: ${name}\n\n` +
           `This concerns: ${task}. Because it involves ${buckets}, Umash has ` +
           `not drafted a send-ready notice. Here is what it would say once you ` +
           `decide how to proceed, ${target}.`;
  }
  const cap = task.charAt(0).toUpperCase() + task.slice(1);
  return `To ${target},\n\n` +
         `I am writing about ${name}, who has passed away. ${cap}. Please let ` +
         `me know what you need from me to complete this, and I will provide it.\n\n` +
         `Thank you for your understanding at this difficult time.`;
}

// ------------------------------------------------- case state machine
// (mirrors umash/policy/casestate.py)
const RESOLVED = new Set(["approved", "sent", "confirmed", "declined"]);

class InvalidTransition extends Error {}

function slug(title, taken) {
  let base = title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 48) || "task";
  let id = base, n = 2;
  while (taken.has(id)) { id = `${base}-${n}`; n++; }
  return id;
}

class CaseState {
  constructor(caseId, diedIn, restIn, name) {
    this.caseId = caseId;
    this.diedIn = (diedIn || "").toUpperCase();
    this.restIn = (restIn || diedIn || "").toUpperCase();
    this.name = name || "the deceased";
    this.crossBorder = this.restIn !== this.diedIn;
    this.tasks = [];   // ordered list
  }

  static build(caseId, diedIn, restIn, name) {
    const cs = new CaseState(caseId, diedIn, restIn, name);
    const taken = new Set();
    for (const [title, phase, target, dl] of tasksFor(cs.diedIn, cs.restIn)) {
      const v = classify(title);
      const id = slug(title, taken); taken.add(id);
      cs.tasks.push({
        id, title, phase, target,
        weighty: v.weighty, reasons: v.reasons,
        deadlineDays: dl, status: "pending",
        draft: "", decision: "",
        history: [{ event: "added", at: Date.now() }],
      });
    }
    return cs;
  }

  get(id) { const t = this.tasks.find(t => t.id === id); if (!t) throw new Error(id); return t; }
  routine()  { return this.tasks.filter(t => !t.weighty); }
  weighty()  { return this.tasks.filter(t => t.weighty); }
  isResolved(t) { return RESOLVED.has(t.status); }

  pendingEscalations() {
    return this.weighty().filter(t => !this.isResolved(t))
      .sort((a, b) => (a.deadlineDays ?? 1e6) - (b.deadlineDays ?? 1e6));
  }

  recordDraft(id) {
    const t = this.get(id);
    if (!t.draft) t.draft = buildDraft(t.target, t.title, this.name, t.weighty, t.reasons);
    if (t.status === "pending") { t.status = "drafted"; t.history.push({ event: "drafted", at: Date.now() }); }
    return t;
  }

  // SAFETY INVARIANT enforced here, in the data layer — not in the view.
  approve(id, decision = "") {
    const t = this.get(id);
    if (t.weighty && !(decision || t.decision)) {
      throw new InvalidTransition(`“${t.title}” is weighty and needs an explicit decision before approval`);
    }
    if (decision) t.decision = decision;
    t.status = "approved";
    t.history.push({ event: decision ? `approved: ${decision}` : "approved", at: Date.now() });
    return t;
  }

  decline(id, reason = "") {
    const t = this.get(id);
    t.decision = reason; t.status = "declined";
    t.history.push({ event: reason ? `declined: ${reason}` : "declined", at: Date.now() });
    return t;
  }

  markSent(id) {
    const t = this.get(id);
    if (!["approved", "drafted"].includes(t.status)) {
      throw new InvalidTransition(`“${t.title}” must be approved before it can be sent`);
    }
    t.status = "sent"; t.history.push({ event: "sent by human", at: Date.now() });
    return t;
  }

  confirm(id) {
    const t = this.get(id);
    t.status = "confirmed"; t.history.push({ event: "confirmed by institution", at: Date.now() });
    return t;
  }

  summary() {
    const by = {};
    for (const t of this.tasks) by[t.status] = (by[t.status] || 0) + 1;
    return {
      total: this.tasks.length,
      routine: this.routine().length,
      weighty: this.weighty().length,
      resolved: this.tasks.filter(t => this.isResolved(t)).length,
      pendingEscalations: this.pendingEscalations().length,
      byStatus: by,
    };
  }

  // --- persistence (localStorage stand-in for ~/.umash/cases/) ---------
  toJSON() {
    return { caseId: this.caseId, diedIn: this.diedIn, restIn: this.restIn,
             name: this.name, tasks: this.tasks };
  }
  static fromJSON(d) {
    const cs = new CaseState(d.caseId, d.diedIn, d.restIn, d.name);
    cs.tasks = d.tasks || [];
    return cs;
  }
}

const STORE_KEY = "umash.cases.v1";
const Store = {
  all() { try { return JSON.parse(localStorage.getItem(STORE_KEY)) || {}; } catch { return {}; } },
  save(cs) { const a = this.all(); a[cs.caseId] = cs.toJSON(); localStorage.setItem(STORE_KEY, JSON.stringify(a)); },
  load(id) { const d = this.all()[id]; return d ? CaseState.fromJSON(d) : null; },
  remove(id) { const a = this.all(); delete a[id]; localStorage.setItem(STORE_KEY, JSON.stringify(a)); },
  ids() { return Object.keys(this.all()); },
};

window.Umash = { CaseState, Store, classify, PHASE_ORDER, PHASE_LABEL, JURISDICTION_NAME, InvalidTransition };
