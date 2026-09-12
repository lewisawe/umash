/* ============================================================================
   Umash — client data layer
   A faithful browser port of the Python policy layer:
     - four phases (immediate / funeral / admin / aftercare)
     - full-journey jurisdiction packs (KE/UK/US) + cross-border repatriation
     - deterministic consequence classification (routine vs weighty)
     - optional faith/culture urgency + rites
     - case state machine with the SAFETY INVARIANT:
         a weighty task cannot be approved without a recorded human decision.
   No framework. Persists to localStorage so a case survives a refresh,
   mirroring ~/.umash/cases/ in the CLI. Kept in lockstep with umash/policy/*.
   ========================================================================== */

// ---------------------------------------------------------------- phases
const PHASE_ORDER = ["immediate", "funeral", "admin", "aftercare"];
const PHASE_LABEL = {
  immediate: "Immediate — moment of death to days",
  funeral:   "Funeral — days to a week",
  admin:     "Admin & estate — weeks to months",
  aftercare: "Aftercare — months to a year+",
};

// ------------------------------------------------- consequence signals
// (mirrors umash/policy/consequence.py — escalation is about the DECISION)
const SIGNALS = {
  money:       ["settle the bill", "hospital bill", "pay ", "deposit", "wire", "transfer funds", "release funds", "payout"],
  legal:       ["sign for", "authorize", "authorise", "power of attorney", "probate", "estate filing", "estate succession", "begin estate", "succession", "affidavit", "notarize", "executor", "title transfer", "transfer title", "transfer property title", "transfer the house", "retitle"],
  irreversible:["release the body", "sign for the body", "repatriate vs", "repatriate to", "cremate", "post-mortem", "autopsy", "close the account permanently", "donate organs", "organ or tissue donation", "organ donation", "tissue donation"],
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

// ------------------------------------------------- shared task blocks
// (mirrors _stage0() and _aftercare_common() in jurisdictions.py)
// task tuple = [title, phase, target, deadlineDays]
const STAGE0 = () => [
  ["Get a legal pronouncement of death", "immediate", "attending doctor / coroner", 1],
  ["Decide on organ or tissue donation", "immediate", "hospital / donor registry", 1],
  ["Locate the will and any recorded funeral wishes", "immediate", "family / solicitor / safe", 2],
  ["Arrange immediate care for dependents and pets", "immediate", "family / neighbours", 1],
  ["Secure the home and belongings of the deceased", "immediate", "family", 2],
];

const AFTERCARE = () => [
  ["Close or memorialize digital and social media accounts", "aftercare", "online platforms", null],
  ["Cancel or transfer the phone and internet accounts", "aftercare", "telecom / ISP", null],
  ["Transfer or sell the vehicle (title transfer)", "aftercare", "vehicle registry", null],
  ["Transfer property title / update the home", "aftercare", "land registry / lawyer", null],
  ["Distribute personal effects and heirlooms", "aftercare", "family", null],
  ["Arrange a headstone or memorial marker", "aftercare", "monument mason", null],
  ["Plan the memorial or anniversary observance", "aftercare", "family / community", null],
  ["Find grief and bereavement support", "aftercare", "counsellor / support group", null],
  ["Update your own will and beneficiaries", "aftercare", "your solicitor", null],
];

// ------------------------------------------------- jurisdiction packs
const PACKS = {
  KE: [
    ...STAGE0(),
    ["Obtain medical cause-of-death / burial permit", "immediate", "hospital / attending doctor", 2],
    ["Register the death (Huduma Centre / Civil Registration)", "immediate", "Civil Registration Dept", 6],
    ["Settle the hospital bill to release the body", "immediate", "hospital billing", 2],
    ["Choose mortuary and confirm holding period + daily cost", "immediate", "mortuary", 3],
    ["Engage a funeral director", "immediate", "funeral director", null],
    ["Notify employer and next of kin", "immediate", "employer / family", null],
    ["Choose burial or cremation per the family’s wishes", "funeral", "family", 3],
    ["Arrange burial permit and venue", "funeral", "county / church", null],
    ["Confirm an officiant and the order of service", "funeral", "church / celebrant", null],
    ["Select a casket and flowers", "funeral", "funeral director", null],
    ["Arrange the hearse and transport of remains", "funeral", "funeral director", null],
    ["Publish obituary / death notice", "funeral", "newspaper / community", null],
    ["Coordinate funeral contributions (harambee / M-Pesa)", "funeral", "family & community", null],
    ["Arrange catering and the after-service gathering", "funeral", "caterer / venue", null],
    ["Claim NSSF / pension survivor benefit", "admin", "NSSF / pension", 30],
    ["Notify NHIF and close cover", "admin", "NHIF", null],
    ["Notify banks and start succession", "admin", "bank(s)", null],
    ["Notify creditors and check which debts survive", "admin", "lenders / SACCOs", null],
    ["Cancel utilities and subscriptions", "admin", "utilities / subs", null],
    ["Redirect the deceased’s mail", "admin", "Posta Kenya", null],
    ["Begin estate succession (if assets)", "admin", "court / lawyer", null],
    ...AFTERCARE(),
  ],
  UK: [
    ...STAGE0(),
    ["Get the Medical Certificate of Cause of Death", "immediate", "hospital / GP", 2],
    ["Register the death (Register Office)", "immediate", "Register Office", 5],
    ["Use ‘Tell Us Once’ to notify govt departments", "immediate", "GOV.UK Tell Us Once", null],
    ["Engage a funeral director", "immediate", "funeral director", null],
    ["Choose burial or cremation per the family’s wishes", "funeral", "family", 3],
    ["Arrange the funeral / cremation and venue", "funeral", "funeral director", null],
    ["Confirm an officiant and the order of service", "funeral", "celebrant / church", null],
    ["Select a casket or urn and flowers", "funeral", "funeral director", null],
    ["Publish obituary / notice", "funeral", "newspaper", null],
    ["Arrange catering and the wake / reception", "funeral", "venue / caterer", null],
    ["Notify banks, pensions, insurers", "admin", "financial institutions", null],
    ["Value the estate and check probate need", "admin", "HMRC / probate", null],
    ["File the final tax position with HMRC", "admin", "HMRC", null],
    ["Notify creditors and check which debts survive", "admin", "lenders", null],
    ["Cancel utilities and subscriptions", "admin", "utilities / subs", null],
    ["Redirect the deceased’s mail (Royal Mail)", "admin", "Royal Mail", null],
    ...AFTERCARE(),
  ],
  US: [
    ...STAGE0(),
    ["Obtain the death certificate (order several copies)", "immediate", "funeral home / vital records", 5],
    ["Engage a funeral home", "immediate", "funeral home", null],
    ["Notify Social Security Administration", "immediate", "SSA", null],
    ["Choose burial or cremation per the family’s wishes", "funeral", "family", 3],
    ["Arrange the funeral / burial / cremation and venue", "funeral", "funeral home", null],
    ["Confirm an officiant and the order of service", "funeral", "celebrant / clergy", null],
    ["Select a casket or urn and flowers", "funeral", "funeral home", null],
    ["Publish obituary", "funeral", "newspaper", null],
    ["Arrange catering and the reception", "funeral", "venue / caterer", null],
    ["File any survivor / life-insurance benefit claim", "admin", "SSA / insurer", 30],
    ["Notify banks, brokerages, creditors", "admin", "financial institutions", null],
    ["Open probate if required", "admin", "probate court", null],
    ["File the final tax return with the IRS", "admin", "IRS", null],
    ["Cancel utilities and subscriptions", "admin", "utilities / subs", null],
    ["Redirect the deceased’s mail (USPS)", "admin", "USPS", null],
    ...AFTERCARE(),
  ],
};

const JURISDICTION_NAME = { KE: "Kenya", UK: "United Kingdom", US: "United States" };

// ------------------------------------------------- faith packs
// (mirrors umash/policy/faith.py)
const FAITHS = {
  muslim: { label: "Muslim", window: 1, rites: [
    ["Arrange ghusl (ritual washing) and shrouding (kafan)", "funeral", "family / mosque", 1],
    ["Arrange Salat al-Janazah (funeral prayer)", "funeral", "imam / mosque", 1],
    ["Arrange prompt burial facing the qibla", "funeral", "burial ground", 1],
  ]},
  jewish: { label: "Jewish", window: 1, rites: [
    ["Contact the Chevra Kadisha for taharah (ritual purification)", "funeral", "burial society", 1],
    ["Arrange shmira (watching) until burial", "funeral", "community", 1],
    ["Arrange prompt burial and prepare for shiva", "funeral", "synagogue / family", 1],
  ]},
  hindu: { label: "Hindu", window: 2, rites: [
    ["Arrange the antyesti (last rites) and cremation", "funeral", "priest / crematorium", 2],
    ["Arrange for the chief mourner and rituals", "funeral", "family / priest", 2],
  ]},
  christian: { label: "Christian", window: null, rites: [
    ["Arrange a wake / vigil and the funeral service", "funeral", "church / clergy", null],
  ]},
  secular: { label: "Secular / none", window: null, rites: [] },
};

function repatriationTasks(diedIn, restIn) {
  return [
    [`Decide: repatriate to ${restIn} vs bury/cremate in ${diedIn}`, "immediate", "family decision", 3],
    ["Obtain embalming certificate to ICAO standards for air transport", "immediate", "funeral director", 4],
    [`Get consular / embassy paperwork for transfer to ${restIn}`, "immediate", "embassy / high commission", 5],
    ["Arrange air cargo for repatriation of remains", "immediate", "airline cargo", null],
  ];
}

function applyFaith(tasks, faith) {
  if (!faith || !FAITHS[faith]) return tasks;
  const pack = FAITHS[faith];
  // compress funeral-phase deadlines to the customary window
  let adjusted = tasks.map(([title, phase, target, dl]) => {
    if (pack.window != null && phase === "funeral" && (dl == null || dl > pack.window)) {
      return [title, phase, target, pack.window];
    }
    return [title, phase, target, dl];
  });
  if (!pack.rites.length) return adjusted;
  // insert rites just before the first funeral task
  const i = adjusted.findIndex(([, phase]) => phase === "funeral");
  if (i < 0) return adjusted.concat(pack.rites);
  return adjusted.slice(0, i).concat(pack.rites, adjusted.slice(i));
}

function tasksFor(diedIn, restIn, faith) {
  let tasks = (PACKS[diedIn] || []).slice();
  if (restIn && restIn !== diedIn) tasks = repatriationTasks(diedIn, restIn).concat(tasks);
  if (faith) tasks = applyFaith(tasks, faith);
  return tasks;
}

// -------------------------------------------------------- draft text
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
const RESOLVED = new Set(["approved", "sent", "confirmed", "declined"]);
class InvalidTransition extends Error {}

function slug(title, taken) {
  let base = title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 48) || "task";
  let id = base, n = 2;
  while (taken.has(id)) { id = `${base}-${n}`; n++; }
  return id;
}

class CaseState {
  constructor(caseId, diedIn, restIn, name, faith) {
    this.caseId = caseId;
    this.diedIn = (diedIn || "").toUpperCase();
    this.restIn = (restIn || diedIn || "").toUpperCase();
    this.name = name || "the deceased";
    this.faith = faith || null;
    this.crossBorder = this.restIn !== this.diedIn;
    this.tasks = [];
  }

  static build(caseId, diedIn, restIn, name, faith) {
    const cs = new CaseState(caseId, diedIn, restIn, name, faith);
    const taken = new Set();
    for (const [title, phase, target, dl] of tasksFor(cs.diedIn, cs.restIn, cs.faith)) {
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

  toJSON() {
    return { caseId: this.caseId, diedIn: this.diedIn, restIn: this.restIn,
             name: this.name, faith: this.faith, tasks: this.tasks };
  }
  static fromJSON(d) {
    const cs = new CaseState(d.caseId, d.diedIn, d.restIn, d.name, d.faith);
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

window.Umash = { CaseState, Store, classify, tasksFor, applyFaith,
                 PHASE_ORDER, PHASE_LABEL, JURISDICTION_NAME, FAITHS, InvalidTransition };
