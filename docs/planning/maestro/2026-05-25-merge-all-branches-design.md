Last Updated: 29-05-2026 (14:30)

---
title: "Merge All Local Branches to Master"
created: "2026-05-25T21:30:00Z"
status: "approved"
authors: ["TechLead"]
type: "design"
task_complexity: "simple"
---

# Merge All Local Branches to Master Design

## Objective
Merge all existing local branches into `master`, resolve any conflicts, and delete the branches after a successful merge.

## Scope
- Target branch: `master`
- Source branches: All local branches except `master` (currently: `merdeka`)

## Approach
1. Ensure `master` is clean and up to date.
2. For each local branch:
    - Attempt to merge into `master`.
    - If conflicts occur, resolve them using a "keep latest logic" or project standards.
    - Validate the project state after merge.
    - Delete the source branch.
