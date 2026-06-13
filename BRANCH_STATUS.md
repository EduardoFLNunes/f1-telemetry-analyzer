# Branch Status And Feature Alignment

Generated: 2026-06-08
Baseline: `origin/main` at `ae81b9f2`

Working tree note: the safe Racing Line update for selecting the fastest valid
lap as the reference has been ported into the local `main` worktree and is
pending commit.

This file is the current source of truth for branch cleanup decisions. It does
not delete or rename branches. Branches marked as `DISCONTINUED` should not be
used for new work unless they are intentionally restored.

## Main Line

| Branch | Status | Notes |
| --- | --- | --- |
| `main` | ACTIVE_MAIN | Local main is aligned with `origin/main`. |
| `origin/main` | ACTIVE_MAIN | Principal remote baseline. |

## Discontinued Flags

These branches have no unique work that should continue separately from the
current main line.

| Branch | Flag | Reason |
| --- | --- | --- |
| `origin` | DISCONTINUED_DUPLICATE_OF_MAIN | Local branch with the same commit and tree as `origin/main`. Do not use. |
| `devlop` | DISCONTINUED_MERGED_OR_ANCESTOR | All commits are already ancestors of `origin/main`; branch is behind main and has no unique commits. |
| `rebuild/track-view-from-main` | DISCONTINUED_MERGED_OR_ANCESTOR | All commits are already ancestors of `origin/main`; branch is behind main and has no unique commits. |

## Active Or Review Needed

These branches contain commits that are not fully integrated into
`origin/main`. Do not merge them directly without review because several were
created before the current main features and can delete or replace current
modules if merged naively.

| Branch | Relation to `origin/main` | Feature Area | Alignment Decision |
| --- | --- | --- | --- |
| `origin/feat/analise-comparativa` | behind 2, ahead 1 | Fastest valid lap for Racing Line, cognitive runtime, Race Coach | REVIEW. Port selected commits only if still desired. |
| `feat/analise-comparativa` | behind 2, ahead 2 | Adds local optimization, Physics Fast Lap, backend controls, technical manual artifacts | REVIEW. Diverged from remote feature branch and main. |
| `codex/integracao` | behind 4, ahead 1 | Ideal line overlay comparison | REVIEW/SUPERSEDED. Its commit is included in `feature/phase-12-desktop-packaging`, but not in main. |
| `feature/phase-12-desktop-packaging` | behind 4, ahead 4 | Desktop/Electron packaging, backend runner, controlled autostart, ideal line overlay | ACTIVE_WIP. Must be rebased or selectively ported onto current main because it predates recent main features. |
| `feature/kn5-track-geometry-provider` | behind 8, ahead 1 | KN5 track geometry provider recovery state | REVIEW_ARCHIVE. Old experimental geometry work. |
| `codex/pitlane-v2-safety-20260521-0115` | behind 8, ahead 3 | KN5 visual ribbon rendering and pitlane safety work | REVIEW_ARCHIVE. Consider cherry-picking only geometry pieces if still useful. |
| `recovery/restore-pre-cache-rollback` | behind 8, ahead 5 | Physical pit entry/exit geometry, debug pitlane tools | REVIEW_ARCHIVE. Local matches remote branch tip. |
| `origin/recovery/restore-pre-cache-rollback` | behind 8, ahead 5 | Remote copy of recovery pitlane work | REVIEW_ARCHIVE. Same feature family as local recovery branch. |
| `backup/pitlane-experiments-before-main-rollback` | behind 8, ahead 6 | Backup of pitlane experiments before rollback | REVIEW_ARCHIVE. Backup only unless specific files are needed. |
| `origin/master` | behind 12, ahead 4 | Legacy master history and backup folder changes | LEGACY_REVIEW. Not aligned with current architecture. |
| `origin/telemetria-ai` | behind 12, ahead 20 | Legacy AI module history | LEGACY_REVIEW. Separate old structure, not ready to merge into current main. |

## Features Confirmed In Current Main

The following feature areas are already present on `origin/main` and should be
treated as the principal implementation:

| Feature | Primary Files |
| --- | --- |
| Player telemetry pipeline | `backend/core/live/telemetry_runtime.py`, `frontend/src/store/useTelemetryStore.ts` |
| Opponents/AI telemetry pipeline | `backend/core/opponents/*`, `/api/live/opponents` |
| Comparative analysis by microsector | `backend/core/comparison_analysis.py`, `/api/live/comparison`, `frontend/src/components/LiveComparisonPanel.tsx` |
| Racing Line analysis | `backend/core/racing_line_analysis.py`, `/api/live/racing-line`, `frontend/src/components/RacingLineAnalysisPanel.tsx`, `frontend/src/components/map/RacingLineOverlay.jsx` |
| Racing Line fastest valid lap selection | `backend/core/racing_line_analysis.py`, `backend/tests/test_racing_line_analysis.py`, `frontend/src/components/RacingLineAnalysisPanel.tsx`, `frontend/src/types/racingLine.ts` |
| Car physics telemetry panel | `backend/core/car_physics.py`, `/api/live/player-physics`, `frontend/src/components/CarPhysicsDebugPanel.tsx` |
| Map Racing Line overlay controls | `frontend/src/components/map/TrackRenderer.jsx` |

## Known Unintegrated Feature Candidates

These are useful candidates, but they are not safely integrated into the main
line yet:

| Candidate | Source Branch | Risk |
| --- | --- | --- |
| Fastest valid lap as Racing Line source | `origin/feat/analise-comparativa` | PORTED_PENDING_COMMIT. Backend, tests, types, and compact Line panel UI were ported without Race Coach. |
| Race Coach / cognitive runtime | `origin/feat/analise-comparativa` | Needs UI and backend contract review. |
| Physics Fast Lap panel | `feat/analise-comparativa` | Local-only and includes generated output artifacts. |
| Desktop packaging / Electron shell | `feature/phase-12-desktop-packaging` | Current branch deletes or replaces main feature files if merged directly. Needs rebase/port. |
| Ideal line overlay comparison | `codex/integracao`, `feature/phase-12-desktop-packaging` | Potential overlap with current Racing Line implementation. |
| KN5/pitlane geometry recovery | pitlane/recovery branches | Old divergent branch family. Review files manually before porting. |

## Cleanup Recommendation

1. Keep `main` and `origin/main` as the only principal branches.
2. Treat `origin`, `devlop`, and `rebuild/track-view-from-main` as discontinued.
3. Do not direct-merge any branch listed as `REVIEW`, `ACTIVE_WIP`,
   `REVIEW_ARCHIVE`, or `LEGACY_REVIEW`.
4. For future work, create a fresh branch from `origin/main` and cherry-pick or
   manually port only the desired files/commits.
5. After review, archive or delete discontinued local branches with explicit
   approval.
