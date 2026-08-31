# R6 recording package

Gate R6 stays open until a human records the MP4. Everything else is here.

| Piece | Where |
| --- | --- |
| Shot list, narration, timing | `submission/video-script.md` |
| Deterministic driver (runs each shot's command, pauses per shot) | `scripts/record-demo.sh` |
| Expected terminal output | `submission/expected-terminal-output.txt` |
| Claim gate (every spoken sentence must pass) | `tests/e2e/test_claim_lock.py` and `5-min-presentation.md` §2 |
| Artifacts shown on screen | `tests/golden/C01/`, `tests/golden/C04/ruling-packet.md`, `results/comparison.md`, `results/improvement-changelog.md`, `README.md` |

## Before pressing record

- [ ] Clean checkout at the submission commit; `git status` empty.
- [ ] `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` unset (the driver refuses otherwise).
- [ ] `make test` green; paste nothing from memory.
- [ ] `uv run pytest tests/e2e/test_claim_lock.py -v` green — a failing row means
      **cut that sentence**, never soften it.
- [ ] Run `scripts/record-demo.sh` once end-to-end without recording; diff what you
      see against `submission/expected-terminal-output.txt`. A mismatch means stop
      and find out why, not re-record until it looks right.
- [ ] Large terminal font, no notifications, no personal paths on screen.

## While recording

- [ ] Read every number off the screen, not from the script.
- [ ] The video records the deterministic replay path only. If a command stalls,
      cut to the recorded expected output and say it is a recorded deterministic
      replay — never imply a cached file is a live run.
- [ ] Name all six rubric categories in natural language (the script's shot
      headers carry them).
- [ ] Name one removed experiment and the highest-impact retained change (shots
      at 4:30).

## After recording

- [ ] Length is at most five minutes.
- [ ] Re-run the claim-lock test against the final cut's sentences.
- [ ] Only then mark R6 closed in `docs/prd-traceability.md`, README status, and
      `implementation-sequence.md` §18.
