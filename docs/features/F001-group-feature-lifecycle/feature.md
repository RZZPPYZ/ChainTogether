---
schema_version: 1
id: F001
title: "Group Feature Lifecycle"
stage: quality
state: active
priority: P1
owner: "codex"
reviewer: ""
vision_guardian: ""
origin_kind: "codex_conversation"
origin_group_id: ""
origin_message_seq: null
created_at: 2026-07-30
updated_at: 2026-07-30
related_features: []
blocked_by: []
research_refs: []
decision_refs: []
plan_refs: ["docs/features/F001-group-feature-lifecycle/plan.md"]
pr_refs: []
---

# F001: Group Feature Lifecycle

## Why

> Operator: "从立项到交付的完整过程……看是否可以单独抽象成单独的 skills！然后 feature doc 需要规范化管理，skill 也是。"

ChainTogether 的群组已经能可靠传球，但没有跨消息、跨 Agent、跨 worktree 和 PR 的长期 Feature 状态。需要让 Claude Code 与 Codex 围绕同一 Feature Doc、workflow 和 gate 协作。

## Current State

- 群组只持久化单次 `group_invocation` 的 custody 状态。
- `docs/features/` 没有统一 ID、frontmatter、AC 或 evidence schema。
- Persona Library 会导入单个 `SKILL.md`，但不是 workflow skill registry。
- Claude Code 与 Codex 没有项目级 canonical skill source。

## Scope

- In scope: Feature dossier、workflow、skill catalog、首批 lifecycle skills、校验和 provider 同步、FeatureRun 后端、群组上下文关联。
- Out of scope: 完整 Feature Dashboard、自动语义判断、自动执行 GitHub merge。

## User Journey

- **Scope unit**: feature
- **Actor**: operator and group agents
- **Entry**: operator 在群里提出需求并创建/关联 FeatureRun。
- **Flow**:
  1. 系统创建 canonical Feature dossier。
  2. 群组 Agent 收到当前 stage、role、skill、artifact refs。
  3. Gate 只允许满足证据与角色约束的 transition。
  4. Feature 经 discovery、delivery、vision acceptance 后关闭。
- **Terminal state**: FeatureRun 和 Feature Doc 均为 `done`，证据可追溯。
- **Success evidence**: validator、后端单元测试、群组动态上下文测试。

## Requirements

| ID | Requirement | Source | AC |
|---|---|---|---|
| R1 | 规范化 Feature dossier 和状态 | operator quote | AC-1, AC-2 |
| R2 | Claude/Codex 共用 canonical skills | operator quote | AC-3, AC-4 |
| R3 | 群组调用关联长期 FeatureRun | group-first clarification | AC-5, AC-6 |
| R4 | Reviewer 与愿景守护角色隔离 | tutorial + operator context | AC-7 |

## Acceptance Criteria

- [x] AC-1: 新 Feature 可由模板创建到 `docs/features/Fxxx-slug/feature.md`。
- [x] AC-2: Feature validator 检查 ID、stage/state、章节、角色隔离和 done 真实性。
- [x] AC-3: `.chaintogether/skills/` 是唯一 skill 源，并有机器可读 catalog。
- [x] AC-4: 同步器可校验/生成 Claude Code 与 Codex provider skill 目录。
- [x] AC-5: 后端持久化 FeatureRun、事件和 invocation 关联。
- [x] AC-6: 群组 Agent turn 注入 feature ID、stage、role、skill 和 canonical doc。
- [x] AC-7: 控制面禁止 owner=reviewer、owner=guardian、reviewer=guardian。
- [x] AC-8: 新增行为具有单元测试，项目测试通过。

## Research and Decisions

- Research: Cat Café tutorial 13；Clowder `feat-lifecycle`、`development.yaml`、feature template、skill sync。
- Decisions: 四层架构——Feature Doc、Workflow、Skill、Gate/Validator。
- Rejected alternatives: 单个超长 lifecycle skill；把 Feature 状态复用为 group custody；分别维护 Claude/Codex 两套 skill 内容。

## Architecture Ownership

- **Owner**: Feature workflow control plane
- **Boundary**: FeatureRun 管长期状态；GroupInvocation 管单次消息 custody。
- **Extension points**: workflow registry、skill registry、provider sync、group D-layer directive。
- **Map delta**: `docs/architecture.md` and `docs/feature-lifecycle.md` updated

## Design Gate

- **Verdict**: approved
- **Feature Doc revision**: initial
- **Evidence**: operator explicitly approved creating a branch and implementing the proposed design.

## Delivery

- **Plan**: `docs/features/F001-group-feature-lifecycle/plan.md`
- **Worktree**: current repository worktree
- **Branch**: `codex/group-feature-lifecycle`

## Review Provenance

- **Author**: codex
- **Reviewer**:
- **Base SHA**: `13253f3`
- **Reviewed HEAD**:
- **Verdict**: pending

## Vision Gate

- **Guardian**:
- **Merged revision**:
- **Verdict**: pending
- **Journey evidence**:

## Risks and Open Questions

| ID | Type | Item | Owner | Status |
|---|---|---|---|---|
| RISK-1 | technical | YAML is parsed as a constrained JSON/YAML subset without adding a runtime dependency. | author | active |
| OQ-1 | product | Feature Dashboard UI is deferred to a separate feature. | operator | decided |

## Timeline

| Date | Event | Evidence |
|---|---|---|
| 2026-07-30 | Discovery and design approved | current Codex conversation |
| 2026-07-30 | Implementation started | branch `codex/group-feature-lifecycle` |
| 2026-07-30 | Quality evidence captured; independent review pending | `evidence/quality-report.md` |
