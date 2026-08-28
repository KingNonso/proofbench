# Paired comparison

Generated 2026-08-28T22:08:52.216575+00:00. Protocol: 12 cases x 2 arms x 1 repeat.

Both arms here are deterministic and make no network call. The baseline is `visible-tests`: run the checks that already exist in CI and merge if they pass, which is the process this product is meant to improve on. The direct-review agent baseline specified by PRD-FR-002 is implemented but is NOT included in this run: it needs a provider key, and authoring its answers would make the comparison meaningless. Until it runs, no claim may be made about how ProofBench compares to a reviewing agent.

## Primary metric and guardrails

Counts before rates. A rate without its denominator says nothing.

| Arm | Unsafe escape rate | Safe accepted | Authority asked | Evidence incomplete |
| --- | --- | --- | --- | --- |
| baseline_visible_tests | 9/9 (100%) | 2/2 | 0/1 | 0 |
| migration_court | 0/9 (0%) | 2/2 | 1/1 | 0 |

`EVIDENCE_INCOMPLETE` is reported in its own column and is never counted as
safe: a run that could not produce evidence has not shown a candidate to be
acceptable.

## Per case

| Case | Class | Expected | baseline_visible_tests | migration_court |
| --- | --- | --- | --- | --- |
| C01 | unsafe | BLOCKED | approve | BLOCKED |
| C02 | unsafe | BLOCKED | approve | BLOCKED |
| C03 | unsafe | BLOCKED | approve | BLOCKED |
| C04 | authority_required | DOMAIN_RULING_REQUIRED | approve | DOMAIN_RULING_REQUIRED |
| C05 | unsafe | BLOCKED | approve | BLOCKED |
| C06 | unsafe | BLOCKED | approve | BLOCKED |
| C07 | unsafe | BLOCKED | approve | BLOCKED |
| C08 | unsafe | BLOCKED | approve | BLOCKED |
| C09 | unsafe | BLOCKED | approve | BLOCKED |
| C10 | unsafe | BLOCKED | approve | BLOCKED |
| C11 | safe | READY_FOR_REVIEW | approve | READY_FOR_REVIEW |
| C12 | safe | READY_FOR_REVIEW | approve | READY_FOR_REVIEW |

## The challenging case: C12

- `baseline_visible_tests`: **approve** (expected READY_FOR_REVIEW)
- `migration_court`: **READY_FOR_REVIEW** (expected READY_FOR_REVIEW)

C12 is the challenging case. It is a *correct* migration that is correct in seven
independent ways at once: a metadata-only column add, nothing dropped so both
live application versions keep working, a deterministic backfill that is safe to
resume, a rollback that drops rather than restores, untouched audit history, no
amount moved, and an intact tenant boundary. Each of those is checked by a
different world, and all seven must pass.

**What it revealed was a bug in our own checker.** The lock world originally
worked by holding a conflicting lock and asserting SQLSTATE 55P03 when the
candidate statement could not acquire its own. C12 failed it. That was correct
behaviour from the world and wrong behaviour from the design: every `ALTER TABLE`
takes ACCESS EXCLUSIVE and therefore blocks behind any open reader, so the check
fired on the safe migration exactly as it fired on the reckless one. A check that
cannot distinguish them is not a check.

The fix was to stop timing and start reading a fact: a table rewrite changes the
relation's filenode and a metadata-only change does not. That distinguishes C07
from C12 exactly, and it is identical on every machine and independent of how
large the fixture happens to be.

Without a known-good case that is *hard* to get right, the lock world would have
shipped looking perfect -- it caught C07, which is what it was written for. Nine
unsafe cases can only tell you a checker fires. It takes a difficult safe case to
tell you it fires for the right reason.


## Cost and time

| Arm | Wall time | Model calls | Input tokens | Output tokens | Est. cost USD |
| --- | ---: | ---: | ---: | ---: | ---: |
| baseline_visible_tests | 26.2s | 0 | 0 | 0 | 0.0000 |
| migration_court | 65.2s | 36 | 0 | 0 | 0.0000 |

Cost is a list-price estimate from recorded token counts, not a billed
figure. Human time per task is not measured here and is discussed in the
changelog rather than reported as a number nobody timed.
