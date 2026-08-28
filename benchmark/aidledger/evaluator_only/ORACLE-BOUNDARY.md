# Oracle boundary

**Nothing in this directory may be read by product code, at any time, for any reason.**

This tree holds evaluator-only material: expected decision states, expected blast-radius
assertions, and case classifications. An agent or product module that reads it is not
measuring anything — it is reading the answer key.

## How the boundary is enforced

The primary boundary is a **process boundary**, not a string check:

1. The evaluation process launches `proofbench review` as a subprocess with a benchmark
   view that excludes this directory. The subprocess is given no oracle path and no oracle
   file descriptor.
2. The subprocess writes its decision and public artifacts, then exits.
3. Only then does the evaluator read anything here, and only through
   `proofbench.evaluation`.

Defence in depth, none of which is the primary control:

- `proofbench.intake.paths` raises `OracleBoundaryError` for any declared path naming or
  resolving into `evaluator_only`, including through a symlink;
- an AST test asserts that no module outside `proofbench.evaluation` imports the oracle
  loader;
- a string grep in CI covers what the AST test cannot see.

The existence of a `decision.json` file is **not** authorisation to read this directory.
Product code could write that file itself.

## Consequence of a breach

A run with oracle access before its decision closed is an integrity failure. It is recorded
as such and stays in the result set (PRD section 8.3). It is not deleted, not retried, and
not quietly excluded from the metric.
