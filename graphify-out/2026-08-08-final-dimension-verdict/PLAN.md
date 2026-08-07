# Final dimension verdict display

## Goal

Keep every dimension's PASS/FAIL status consistent with the final score after
guideline deductions, and show the exact triggered guideline deductions in the
same row, including medical-safety gates.

## Changes

1. Derive the displayed verdict from `dimension_scores` (medical safety passes
   only at 5; other dimensions pass at 3 or above).
2. Merge deduction details from structured `guideline_scores` with legacy
   `score_deductions`, deduplicating identical messages.
3. Recover the displayed original score from the dimension verdict when an old
   medical-safety result stored its post-gate score in `dimension_raw_scores`.
4. Add regression tests for ordinary and medical-safety guideline deductions.
