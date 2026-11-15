# Specifications

Feature specifications for **beastforge**, following the GitHub Spec Kit
convention: one numbered directory per feature.

This directory is not the requirements or conventions corpus. Reusable
cross-project rules live in the project's corpus, and any generated
baseline is written outside `specs/`.

## What lives here

```
specs/
├── README.md
└── NNN-feature-slug/
    ├── spec.md          # what and why (no tech stack)
    ├── plan.md          # how: architecture, libraries, file layout
    ├── tasks.md         # dependency-ordered work items
    ├── research.md      # optional decisions and unknowns
    ├── data-model.md    # optional entities and invariants
    ├── contracts/       # optional interface contracts
    └── checklists/      # requirements-quality gates
```

Feature directories are numbered (`001`, `002`, …) and use a kebab-case
slug. The active feature is recorded in `.specify/feature.json`. This
README is project-local; Spec Kit does not generate it. See the Spec Kit
documentation (https://github.com/github/spec-kit) for the tooling.

## Lifecycle

A completed feature directory is a historical record. When behavior
changes, create a new numbered directory instead of rewriting the old
spec. Link related ADRs and backlog notes instead of copying them.

## Index

| Spec | Title | Status |
|------|-------|--------|
| [001](001-procedural-creature-generator/spec.md) | Procedural 3D Creature Generator | Implemented |
