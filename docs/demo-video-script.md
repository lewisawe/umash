# Umash — demo video script (target: under 5 minutes)

_Local, gitignored notes. For recording the Devpost submission video._

**Track:** Everyday Agents. The judging video must show the project working
end-to-end and cover (1) the problem, (2) who it's for, (3) why it matters.

**Format:** screen recording + voiceover. No need to be on camera. Record a
backup take. Keep the cursor calm; let the auto-run carry the middle.

**Setup before recording:**
- `python3 -m http.server -d web 8000`, open `http://localhost:8000/app.html`
  in a clean browser window (clear localStorage so you start empty).
- Have the Nairobi -> UK, Muslim case ready to build.
- Optional: a terminal with `python demo.py` ready, and the live AgentCore
  runtime reachable, for the "it's real" beat.

---

## Beat sheet

### 0:00–0:35 — The problem (who it's for, why it matters)
> "When someone dies, the people left behind inherit a second job on the worst
> week of their life. Register the death. Choose a mortuary against its clock.
> Settle a hospital bill before the body is released. Then months of banks,
> insurers, benefits, closing accounts. One family spent four months just
> finding the accounts. This is for the family member doing that admin while
> grieving — not a funeral director, not a lawyer. The person making the calls."

Show: the landing page (`index.html`), scroll once, calm.

### 0:35–1:00 — What Umash is, and the one rule
> "Umash is one agent, built with the Strands Agents SDK on Amazon Bedrock, that
> carries a family through the whole arc. Its one rule is the Everyday Agents
> brief almost word for word: run quietly in the background, and only surface
> when there's a real decision to make."

Show: click "Open a case." Fill the intake — my father, died Kenya, rest UK,
Muslim. Click "Build the plan."

### 1:00–1:35 — The plan + the decision flow (the agentic proof)
> "It builds a phased, jurisdiction-aware plan — Kenya to the UK, so it adds the
> repatriation branch. It's Muslim, so it pulls the funeral to a one-day window
> and adds the rites. On the right is the agent's decision flow: every box is a
> real step it runs through its tools. Build the plan. Then a routine-versus-
> weighty call on every task."

Show: the side-by-side. Let the boxes-and-arrows trace animate in. Point (cursor)
at the Cross-border? and Faith set? branches, then classify_consequence
splitting into "Routine -> batch (34)" and the escalations.

### 1:35–3:30 — Auto-run: the whole journey, hands-off
> "Here's the whole thing running on its own."

Show: click **▶ Auto-run**. Narrate lightly over it:
> "The 34 routine tasks — the registration letter, the employer notice, a
> subscription — are prepared quietly and batched into a single approval. It
> doesn't nag you with each one. Then the weighty decisions come one at a time,
> most urgent first. Organ donation. Settling the hospital bill to release the
> body. Repatriate to the UK, or bury in Kenya. Each opens with the tradeoffs
> laid out, waits for a human, records the decision, and closes — and the tree
> shows the journey filling in behind it."

Let it play. The open/close rhythm and the caption line do the work. Don't talk
over every decision; go quiet and let a couple land.

> "Notice what it never does: it never files, pays, or books anything. It drafts
> and waits. Restraint is the point."

### 3:30–4:15 — Why this is safe (the differentiator)
> "That restraint isn't a promise in a prompt — it's the architecture. Whether a
> task is weighty isn't the model's call; it's decided in plain Python the agent
> can't override. And the agent holds no tool that can file, pay, or send. So a
> prompt injection's worst case is an awkward draft, never a drained account. An
> Amazon Bedrock Guardrail redacts the decedent's PII on top of that."

Show (pick one):
- the `umash/policy/consequence.py` + `casestate.py` invariant on screen, or
- a quick terminal `python demo.py` against the real Bedrock agent so the tool
  calls are visibly real (10–15s), or
- the guardrail redacting "Nairobi"/"UK" to {ADDRESS} in the model's reasoning.

### 4:15–4:45 — Close
> "It's jurisdiction-aware for Kenya, the UK, and the US, faith-aware for five
> traditions, and every one of those is data — adding a country or a tradition
> never touches the agent. The core runs with zero third-party dependencies and
> no AWS credentials, and it's deployable to Amazon Bedrock AgentCore. Umash:
> the afterward, handled with care."

Show: end state — "You've done everything for now." Then the repo / live link.

---

## Recording tips
- Do a dry run once; the auto-run pacing is ~3 min, so start it and trim.
- If auto-run is too slow/fast for the cut, adjust OPEN_MS/TREE_MS in `app.js`.
- Capture a backup take in case the live demo hiccups.
- Keep total under 5:00. If tight, compress the safety beat (3:30–4:15).

## Must-say checklist (judging criteria)
- [ ] The problem (0:00)
- [ ] Who it's for — the grieving next of kin (0:00)
- [ ] Why it matters — nearly everyone does this someday (0:00)
- [ ] Working end-to-end demo (auto-run, 1:35–3:30)
- [ ] Uses Strands Agents SDK on Bedrock (0:35, 3:30)
- [ ] Never files/pays/books — the safety story (3:30)
