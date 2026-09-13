# Agents for Humans: keep the safety-critical logic out of the model

*How Umash, a coordinator for families after a death, keeps the decisions that matter in plain Python the agent can't override. Built with the Strands Agents SDK on Amazon Bedrock.*

## The problem I was actually solving

When someone dies, the people left behind inherit a second job on the worst week of their life. Register the death. Choose a mortuary against its clock. Settle a hospital bill before the body is released, arrange the funeral, then months of banks, insurers, benefits, and closing accounts. The steps differ by country, and for families split across borders, repatriation adds a whole branch.

I wanted an agent that carries a family through that whole arc. But an agent that acts on your behalf during grief is exactly where "the AI did something unexpected" stops being a funny demo and becomes real harm. Settling a hospital bill, filing a benefit claim, agreeing to repatriate a body: these cost money, some are irreversible, some are time-critical. You can't let a language model decide, on its own phrasing, whether one of those needs a human.

So the design question wasn't how capable the agent could be. It was what the model must never be allowed to decide.

## The one rule

Umash runs on a single rule:

- **Routine, low-stakes, reversible** work (draft the registration letter, the employer notice, a subscription cancellation) is prepared quietly and **batched into one approval**.
- **Weighty** work (money leaving, a legal signature, anything irreversible or time-critical) is **escalated one at a time**, with the tradeoffs laid out, and is **never executed autonomously**.

The agent drafts, plans, and waits. It never files, pays, or books anything. Restraint is the whole product.

Where that rule lives is the part worth talking about.

## The split: model for judgment, code for safety

Umash is one Strands agent on Amazon Bedrock. The agent earns its place: it orders the journey, adapts its tone to a grieving reader, and decides what to say versus what to keep quiet. Language models are good at that.

But whether a task is weighty isn't the model's call. That lives in a deterministic policy layer, plain Python, no model, no network:

```
umash/policy/
  phases.py         # the four phases, in order
  jurisdictions.py  # KE / UK / US task packs as DATA + repatriation
  faith.py          # optional rites + burial-window urgency
  consequence.py    # ROUTINE vs WEIGHTY: the safety core
  casestate.py      # task lifecycle + the safety invariant
```

`consequence.py` classifies a task by matching narrow keyword sets: money, legal, irreversible, time-critical, benefit-claim. Any hit makes it weighty. Everything else is routine. It's deliberately boring code:

```python
def classify(task_text, deadline_days=None):
    t = (task_text or "").lower()
    weighty = _hit(_MONEY) or _hit(_LEGAL) or _hit(_IRREVERSIBLE) \
              or _hit(_TIME_CRITICAL) or _hit(_CLAIM)
    return Verdict(WEIGHTY if weighty else ROUTINE, ...)
```

A grieving person's need for a decision shouldn't depend on how a model happened to phrase things this time. That's the point of the determinism. The same input always produces the same escalation.

## The invariant that makes it safe

Classification alone isn't enough. The stronger guarantee lives in the case state machine: a weighty task can't move to approved without a recorded human decision. That's enforced in code, not left to the agent's good behavior:

```python
def approve(self, task_id, decision=""):
    t = self.get(task_id)
    if t.weighty and not (decision or t.decision):
        raise InvalidTransition(
            f"'{t.title}' is weighty and needs an explicit decision before approval")
    ...
```

There's no path, no prompt, no clever jailbreak that approves a hospital-bill release without a human decision on the record. The model doesn't hold that capability, so it can't give it away.

## Why this is also the security story

Every LLM can be prompt-injected. Umash reads free text about a death and drafts notices, so a malicious string could try to steer it. The usual reaction is to bolt on filters and hope.

Umash's real defense is architectural. Look at what the agent can actually do: six tools, `build_journey_plan`, `classify_phase`, `classify_consequence`, `draft_notice`, `schedule_followup`, `track_confirmation`. None of them file, pay, book, or send. The worst a fully hijacked model can do is produce a bad piece of text or a wrong plan. It can't take a real-world action, because no tool takes one, and it can't reclassify a weighty task as routine, because that isn't its decision.

That reframes the threat model. The blast radius of a successful injection is an awkward draft, not a drained account. I added an Amazon Bedrock Guardrail on top for defense in depth (PII redaction of decedent data, a denied topic for professional advice, prompt-attack filtering), but the guardrail is the second line. The architecture is the first.

## What the model still does, and why it's worth having

None of this makes the model decorative. It builds the phased, jurisdiction-aware, faith-aware plan. It orders forty-odd tasks into a sane sequence. It writes a registration notice that sounds human instead of like a form, and it works out that a Muslim family's funeral needs to lead everything because the burial window is about a day. That's real work, and the agent does it well. The deterministic layer tells the agent what's safe. The agent decides what's kind.

## Making the split visible

A safety argument you can't see is easy to disbelieve. So the web dashboard puts the plan on the left and the agent's decision flow on the right, as boxes and arrows. Every box is a real step it runs through its tools.

![The Umash dashboard: the phased plan on the left, the agent's decision flow on the right](screenshots/02-dashboard-trace.png)

You can read the whole rule off the picture. `build_journey_plan` takes the cross-border branch (Kenya to the UK, so add repatriation) and the faith branch (Muslim, so compress the funeral to about a day). Then `classify_consequence` runs on every task and forks. Thirty-four routine tasks collapse into a single batch node. Each weighty task becomes its own escalation: organ donation, settling the hospital bill to release the body, repatriate or bury.

Hit auto-run and the whole journey plays hands-off in about three minutes. The routine work batches silently. Each weighty decision opens for review, waits, records the decision, and closes so the flow moves on.

![A weighty decision surfaced one at a time, with the reason it was escalated and a draft that is explicitly not send-ready](screenshots/03-decision-modal.png)

Notice the draft. For a weighty task, Umash deliberately doesn't produce a send-ready notice. It says, in plain words, that this needs the human's decision first. The routine drafts are ready to send. The weighty ones aren't, by design.

## The payoff for a builder

Splitting judgment from safety gave me things I didn't expect:

- **The core runs with zero third-party dependencies and no AWS credentials.** Because the policy layer is plain Python, the whole product runs offline: the phased plan, the batch-vs-escalate logic, persistence. That's what CI exercises, and what a reviewer can try in seconds.
- **Coverage grows by editing data, not the agent.** Adding a country is a new task pack. Adding a tradition is a new faith pack. The agent never changes.
- **The web UI mirrors the same logic** in the browser, so the demo needs no backend and no model call, and it still enforces the identical safety invariant.

If you're building an agent that acts where mistakes are expensive, the lesson generalizes: make the model's job smaller and clearer, not bigger. Give it no tool that can cause the harm you're worried about, and put the "does a human need to see this" decision in code you can read, test, and trust. The agent is better for having less power. So is everyone who depends on it.

---

*Umash was built for the Agents for Humans hackathon with the Strands Agents SDK on Amazon Bedrock, deployable to Amazon Bedrock AgentCore. Source: github.com/lewisawe/umash.*
