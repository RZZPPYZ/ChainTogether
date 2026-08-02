---
schema_version: 1
id: F001
title: "Group Feature Lifecycle"
stage: done
state: done
priority: P1
owner: "codex"
reviewer: "f001_reviewer"
vision_guardian: "f001_vision_guardian"
origin_kind: "codex_conversation"
origin_group_id: ""
origin_message_seq: null
created_at: 2026-07-30
updated_at: 2026-08-02
related_features: ["F002"]
blocked_by: []
research_refs: ["docs/features/F001-group-feature-lifecycle/evidence/d14-skill-contract-audit.md", "docs/features/F001-group-feature-lifecycle/evidence/quality-report-2026-08-02.md"]
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
  2. 群组的当前 Feature 被持久关联；每个 Agent turn 都通过 D14 动态模板收到 Feature、stage、role、建议 skill、next step 和 artifact refs。
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
| R5 | D14 每轮提示当前 Feature，并让每个流程 skill 声明使用边界、产出和下一步 | operator follow-up | AC-9, AC-10 |

## Acceptance Criteria

- [x] AC-1: 新 Feature 可由模板创建到 `docs/features/Fxxx-slug/feature.md`。
- [x] AC-2: Feature validator 检查 ID、stage/state、章节、角色隔离和 done 真实性。
- [x] AC-3: `.chaintogether/skills/` 是唯一 skill 源，并有机器可读 catalog。
- [x] AC-4: 同步器可校验/生成 Claude Code 与 Codex provider skill 目录。
- [x] AC-5: 后端持久化 FeatureRun、事件和 invocation 关联。
- [x] AC-6: 群组的当前 Feature 跨消息持久化；每个 Agent turn 都通过注册的 D14 `update-workflow-sop` 动态模板注入 feature ID、stage、role、skill、next step 和 canonical doc。
- [x] AC-7: 控制面禁止 owner=reviewer、owner=guardian、reviewer=guardian。
- [x] AC-8: 新增行为具有单元测试，项目测试通过。
- [x] AC-9: 13 个 lifecycle skills 均显式包含 `Use when`、`Not for`、`Output` 和 `Next step`，且校验器强制检查。
- [x] AC-10: workflow 为每个 stage 提供 next step，并在 review 等多 skill 阶段按当前 Agent 角色给出建议 skill。

## Research and Decisions

- Research: Cat Café tutorial 13；Clowder `feat-lifecycle`、`development.yaml`、feature template、skill sync。
- Decisions: 四层架构——Feature Doc、Workflow、Skill、Gate/Validator；D14 是每轮从 group active FeatureRun 重新渲染的动态告示牌，而不是调度器。
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
- **Reviewer**: f001_reviewer
- **Base SHA**: `13253f3`
- **Reviewed HEAD**: `2982c8fdd64ea36ac5ff89c6fb93b339bb59d803`
- **Verdict**: approved
- **Evidence**: `evidence/review-verdict-2982c8f.md`

## Vision Gate

- **Guardian**: f001_vision_guardian
- **Merged revision**: `0c5482d95fc56ec6ab3b63382134c3e55d370905`
- **Verdict**: accepted
- **Journey evidence**: `evidence/vision-verdict-0c5482d.md`

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
| 2026-08-01 | Operator clarified D14 per-turn injection and skill contracts; returned to implementation | current Codex conversation |
| 2026-08-01 | D14 refinement returned to Quality | `evidence/quality-report-2026-08-01.md` |
| 2026-08-01 | Skill trigger contracts moved into discovery-visible descriptions; standalone next-Skill sections added | `evidence/d14-skill-contract-audit.md` |
| 2026-08-02 | Fresh Quality Gate passed; F001 entered independent Review | `evidence/quality-report-2026-08-02.md` |
| 2026-08-02 | Independent review requested changes for concurrent transitions, document-sync atomicity, and gate provenance; returned to implementation | `evidence/review-response-89b070f.md` |
| 2026-08-02 | Re-review of `2e91354` found outbox supersession, shared-bearer session impersonation, and Git fail-open paths; returned to implementation | `evidence/review-response-2e91354.md` |
| 2026-08-02 | Re-review of `de1502c` found gate/document TOCTOU, legacy pending migration, and capability argv exposure; returned to implementation | `evidence/review-response-de1502c.md` |
| 2026-08-02 | Re-review of `522a4fa` found database-boundary gate races and late stale outbox delivery; returned to implementation | `evidence/review-response-522a4fa.md` |
| 2026-08-02 | Independent review approved exact HEAD `2982c8f` with no P1/P2/P3 findings | `evidence/review-verdict-2982c8f.md` |
| 2026-08-02 | Approved tree merged to and pushed on `main` as `0c5482d` | `evidence/merge-evidence-0c5482d.md` |
| 2026-08-02 | Independent Vision Gate accepted the merged group-first journey | `evidence/vision-verdict-0c5482d.md` |
| 2026-08-02 | F001 canonical dossier and indexes synchronized; remaining autonomous `/feature` work separated as F002 | `evidence/closure-report.md` |
