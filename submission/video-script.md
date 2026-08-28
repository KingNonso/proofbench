# Five-minute video: recording script

Shot by shot, keyed to files that exist. Every number below was read from
`results/summary.json` or a committed certificate — none is from memory.

`tests/e2e/test_claim_lock.py` is the claim-lock table executed. If it passes,
every sentence here is permitted. If a row fails, **cut the sentence** rather than
softening it.

## Before recording

```bash
make test                        # 264 pass, ~2m
uv run pytest tests/e2e/test_claim_lock.py -v
make evaluate                    # read the counts off the screen, do not recall them
open tests/golden/C01/certificate.html
open tests/golden/C04/ruling-packet.md
```

Large terminal font. No notifications, no provider keys, no personal paths on
screen.

---

## 0:00–0:30 — Problem and user value *(15 pts)*

**Screen.** `benchmark/aidledger/cases/C01/candidate.sql` beside
`benchmark/aidledger/cases/C01/visible_tests/001_schema_shape.sql`.

> A coding agent hands a staff platform engineer this migration. It adds a column
> to the payments table by recreating it — create, copy, swap, restore the grants.
> The final schema is exactly right. The test in CI passes.
>
> Row-level security was an attribute of the table that got dropped. It is gone,
> and nothing in the diff says so.

Point at the `GRANT` lines, then at the absence below them.

---

## 0:30–1:00 — The baseline *(sets up Measured Improvement)*

**Screen.** `make evaluate`.

> The baseline is what teams do today: run the checks already in CI, and merge if
> they pass. On twelve pre-registered migrations — nine of them unsafe — it lets
> **nine out of nine** through.
>
> Not because the tests are bad. Because every one of those nine passes its own
> visible test. That is the premise of the benchmark, and there is a test
> asserting it.

Read `9/9` off the screen.

---

## 1:00–1:35 — Architecture *(Agent Solution, 30 pts)*

**Screen.** `tests/golden/C01/trajectory.md`, the Stages block.

> Three agents with narrow jobs. The Contract Analyst separates what the evidence
> supports from what it doesn't. The Test Designer picks worlds from a fixed
> catalog. The Remediation Engineer proposes a fix only after something is blocked.
>
> None of them can decide anything, and that is enforced by the schemas rather than
> the prompts. The contract has no field for a verdict. The world plan has no field
> that could hold a command. Typed Python runs the PostgreSQL worlds and applies
> the decision.

---

## 1:35–2:35 — One real execution *(the heart of it)*

**Screen.** `tests/golden/C01/trajectory.md`, the Timeline.

> Line four: the analyst records an assumption it could not cite evidence for —
> *recreating a table preserves its row-level security policies*.
>
> Line eight: that assumption picks the tenant isolation world.
>
> Line nine: the visible test passes.
>
> Line eleven: the world fails.

**Switch to** `tests/golden/C01/certificate.html`, first screen.

> `BLOCKED`, on `INV-RLS-001`. The blast radius is confirmed rather than asserted:
> the application role, scoped to Northwind, read **two** Southgate payment rows.
> Those are the actual row keys, and each cites the check that observed it.
>
> The Remediation Engineer restores the policies. That correction passes the same
> world on a clean database — and the decision stays `BLOCKED`, because the
> decision is about the migration that was submitted.

---

## 2:35–3:00 — The human boundary

**Screen.** `tests/golden/C04/ruling-packet.md`.

> C04 backfills a missing currency with USD. Every amount is preserved, every
> constraint holds. No check can fail, because the answer was never in the
> database.
>
> ProofBench asks. Here is the exact question, the two affected rows split by
> organisation, both readings, and what each costs if it's wrong.
>
> The answer becomes an executable constraint. Rule "all USD" and the migration
> goes through. Rule "currency varied by organisation" and it's blocked. It's a
> question, not a veto — and neither answer can override a failure the database
> already demonstrated.

---

## 3:00–3:30 — The finished artifact *(End-to-End Quality, 20 pts)*

**Screen.** `certificate.html`, scroll once.

> The engineer gets one document. State, change, decisive invariant, confirmed
> blast radius, next action, and the replay command — all above the fold. JSON,
> Markdown and HTML come from one typed record, so they cannot disagree.
>
> The detail sections carry the worlds, the correction, the trajectory, the
> environment, and the known limits — including what this run did *not* check.

---

## 3:30–4:05 — Measured improvement *(15 pts)*

**Screen.** `results/comparison.md`.

> Twelve pre-registered cases: nine unsafe, one needing domain authority, two safe
> controls so that rejecting everything cannot win.
>
> Baseline: **nine of nine** unsafe migrations merged. ProofBench: **zero of
> nine**. Both accept both safe controls.

Read both cells aloud, then:

> One thing this does not claim. The direct-review *agent* baseline is
> implemented and has not been run — it needs a provider key, and writing its
> answers myself would make the comparison meaningless. The report says so in the
> report.

---

## 4:05–4:30 — Reproducibility *(15 pts)*

**Screen.** `REPRODUCTION.md`, then `make replay`.

> Clean checkout, five commands, **194 seconds**, no key. Not because I didn't set
> one — the provider SDK isn't installed on that path at all, and CI asserts it.
>
> Twelve golden certificates, all reproduced. Change one byte of a candidate and
> replay fails and names the file.

---

## 4:30–4:50 — What changed, and what I removed

**Screen.** `results/improvement-changelog.md`, the "Removed" section.

> The change that mattered most is that there are seven worlds, not one. Each of
> the nine unsafe migrations is caught by a different one. Remove any single world
> and the escape rate goes from zero to one.
>
> The experiment I removed: the lock world originally held a conflicting lock and
> asserted a timeout. It failed the *correct* migration, because every ALTER TABLE
> blocks behind an open reader. I replaced the stopwatch with a fact — a table
> rewrite changes the relation's filenode.

---

## 4:50–5:00 — Hot take *(5 pts)*

**Screen.** The three-row table in `README.md` under "Hot take".

> Migration correctness is a property of the deployment timeline, not the final
> schema. Three recorded cases pass every check you can run at an instant and
> fail across an interval — a rollout, an interruption, a rollback.
>
> The lesson I'd carry: when a check has to run over an interval, find the fact
> the database can state about that interval instead of timing it. I learned that
> by getting it wrong first.

Stop. No thank-you, no feature list.

---

## If a command stalls

Cut to the recorded terminal output from the submission commit, show the matching
run id in the certificate, and say it is a recorded deterministic replay. Do not
imply a cached file is a live run.
