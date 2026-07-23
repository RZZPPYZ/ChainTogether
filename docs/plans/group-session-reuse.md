# Plan: Group Chat Session 复用模式重构

## Context

当前 group chat 实现（`server/group_manager.py`）每次 @-mention 都 `create_session(origin='group_reply')` 开一个新 child session 跑 turn，跑完靠 idle hook 归档。这导致：

1. **同一 agent 在群里被 @ N 次产生 N 个独立 child**，agent 没有跨 turn 私有记忆——它每次只看到 group transcript 快照，不知道"我上次跑到哪了/分析过什么"。这是功能性缺陷，不是优化项。
2. **归档 session 持续堆积**：archived=True 但物理不删，DB 长期增长。
3. **A2A chain walk 性能差**：每次 A2A fan-out 都要 `walk_parent_chain`，内存 miss 时 `load_sessions(include_archived=True)` 全表扫归档 session 建索引回查。
4. 偏离了 `delegations.py` 已经确立的设计哲学——delegation 也是"复用 child session、跨 turn 保留 transcript、事件+注入而非新开"。

### 目标

按宫下建议 + 用户确认的方向，把 group chat 改成 **(group × agent) 复用一个 long-lived session** 模式：

- 新增 `group_agent_sessions(group_id, agent_id, session_id)` 表，第一次 @ lazy 创建，后续复用。
- session 用 `origin='group_member'`，用 `--resume` 维持跨 turn 私有记忆。
- A2A 传球改成"给目标 session 的 start_message queue 投一条 a2a 消息"，复用 session_manager 已有的 busy→queue 机制串行化。
- 三层防无限传球：worklist-busy → in-memory spawner set（防环）→ depth cap=3（防线性深传球，保持不变）。
- `delete_group` 级联硬删 group + members + backing + (group×agent) 复用 sessions。
- 不做 schema migration：现有 `origin='group_reply'` 归档 session 保留不动，新策略只对新建复用 session 生效。

### 用户已确认的决策

- ✅ 改复用模式（参照宫下建议）
- ✅ depth cap 保持 3 不变
- ✅ schema 不迁移，新表冷启动
- ✅ A2A busy 时排队（用 start_message queue）
- ✅ A2A 上下文：复用 `--resume` 即可，augmented prompt 角色降级为"提供群上下文"

### 不在本次范围

- 流式 broadcast 改造（`group_agent_text` 走正式事件通道 / `replaces_stream` 显式标记）—— 宫下建议作为独立后续工作，本次不动。
- depth cap 调整 —— 用户明确保持 3。
- 现有 `origin='group_reply'` 归档 session 的物理清理 —— 不迁移。

---

## 关键设计

### 1. 新增 DB 表 + helper

**`server/database.py`** 在 schema 里加表（参照 `group_members` 风格，紧挨着 groups 表定义之后大约 `database.py:358-365`）：

```sql
CREATE TABLE IF NOT EXISTS group_agent_sessions (
    group_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    session_id TEXT NOT NULL,           -- the long-lived (group×agent) session
    created_at TEXT NOT NULL,
    PRIMARY KEY (group_id, agent_id),
    FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE,
    FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);
```

新增 helper（参照 `add_group_member` / `_group_members` 风格）：

- `async def upsert_group_agent_session(group_id, agent_id, session_id, created_at) -> None` — INSERT OR REPLACE。
- `async def get_group_agent_session(group_id, agent_id) -> str | None` — 返回 session_id 或 None。
- `async def list_group_agent_sessions(group_id) -> list[dict]` — 给 delete_group 级联用。
- `async def delete_group_agent_session(group_id, agent_id) -> None` — remove_member 时可选清理。

### 2. 新 origin: `'group_member'`

**`server/session_manager.py:1249`** `_AUTO_ARCHIVE_ORIGINS = ("schedule", "group_reply")` —— 保持不变，**不把 `'group_member'` 加进去**。这样复用 session 是 long-lived，不会被 idle hook 归档，跟 group 同生命周期。

harness 层 grep 确认对 origin 无依赖（`server/harness/` 下 `group_reply` / `origin ==` 0 命中），新增 origin 安全。

### 3. GroupManager 改造

**`server/group_manager.py`**：

#### 3.1 新增 `_get_or_create_member_session` helper

```python
async def _get_or_create_member_session(
    self, run: GroupRunState, agent: dict, group: dict,
) -> str:
    """Return the (group × agent) session id, lazily creating it on first @.

    The session is origin='group_member', parent_session_id=run.group_session_id,
    so it shows in the session tree under the group. Never auto-archived.
    """
    aid = agent["id"]
    existing = await self.db.get_group_agent_session(run.group_id, aid)
    if existing:
        # If evicted from memory (server restart), reload from DB.
        if self.session_manager and self.session_manager.get_session(existing) is None:
            await self.session_manager.load_session_from_db(existing)
        return existing
    child = await self.session_manager.create_session(
        agent_id=aid,
        name=f"{agent['name']} @ {group['name']}",
        origin="group_member",
        parent_session_id=run.group_session_id,
        backend=agent.get("backend") or "claude-code",
        credential_id=agent.get("credential_id"),
    )
    await self.db.upsert_group_agent_session(
        run.group_id, aid, child.id,
        datetime.now(timezone.utc).isoformat(),
    )
    return child.id
```

> 注：`load_session_from_db` 是否已存在需在实现时确认；如果没有就用现有的 `db.load_sessions` + 重建 Session 对象的路径，或参照 `delegations` 启动时的恢复逻辑（`session_manager.py:433-445` 处理 delegation origin 恢复的同类问题，可借鉴）。

#### 3.2 重写 `_run_mentioned_agent`

核心改动：

- **不再 create_session**：用 `_get_or_create_member_session` 拿到复用 session id。
- **不再传 spawner_session_id 当 parent_session_id**：复用 session 的 parent 永远是 group session。A2A 链不再通过 session parent 序列化（详见 §3.3）。
- **走 start_message 而非 send_message**：让 session_manager 的 queue 机制自动串行化（busy → `_pending_queue`）。
- **A2A spawner_agent_ids + depth 改成 in-memory 参数下传**，不再 walk_parent_chain。
- **保留 augmented prompt**：身份 + roster + 最近 40 条 transcript + direct_message_from 标记。Augmented prompt 角色从"代替记忆"降级为"提供群上下文"——agent 通过 `--resume` 自己的 JSONL 维持私有记忆，augmented prompt 只补群公共视角。
- **流式 + 最终 inject 不变**：`_collect_agent_reply` 继续流式 broadcast `group_agent_text` + 最终 `[agent-reply:Name]` inject。（流式契约改造不在本次范围）

```python
async def _run_mentioned_agent(
    self, run, agent, group, *,
    spawner_agent_ids: frozenset[str] = frozenset(),
    spawner_agent_name: str | None = None,
    depth: int = 1,                          # NEW: in-memory depth, 替代 chain walk
) -> None:
    aid = agent["id"]; aname = agent["name"]

    # Worklist busy guard (并发 @ 同一 agent 排队靠 start_message queue;
    # 但 worklist 仍然用于"前端 typing 提示"和"避免同一 agent 多个并发 turn
    # 在 group_manager 层重复 augmented prompt 构造")
    for e in run.worklist:
        if e.agent_id == aid:
            logger.info("Group %s: @%s already active, queued by session_mgr",
                        run.group_id, aname)
            # 不 skip —— 走 start_message 让 queue 接管
            # 但 typing 事件不重复 broadcast（已有 in-flight）
            ...
```

> **设计决策点（实现时拍板）**：worklist-busy 时是否仍构造 augmented prompt 并 start_message？
> - 选项 A：构造 augmented prompt 并 start_message（推荐）—— 让 session queue 接管，agent 跑完当前 turn 自动接下一条。需注意 augmented prompt 用的是当前群 transcript 快照，turn 跑完时 transcript 可能已经更新（其他 agent 也回复了），这是可接受的（agent 看"叫它那一刻"的快照）。
> - 选项 B：构造精简 prompt（只含 a2a 消息本身），依赖 `--resume` 让 agent 保留群上下文记忆。更纯净但 agent 可能丢失"群里刚发生了什么"的最新视角。
> 实现时默认走选项 A，与现有 augmented prompt 行为一致。

#### 3.3 重写 `_dispatch_a2a_mentions`：用 in-memory depth 替代 chain walk

```python
async def _dispatch_a2a_mentions(
    self, *, run, group, member_agents,
    spawner_agent_id, spawner_agent_name,
    spawner_agent_ids: frozenset[str],       # 链上 agent 集合
    depth: int,                              # 当前深度
    reply_text: str,
) -> None:
    mentioned = parse_mentions(reply_text)
    if not mentioned:
        return
    chain_agent_ids = spawner_agent_ids | {spawner_agent_id}

    for name in mentioned:
        target = self._resolve_agent_by_name(name, member_agents)
        if target is None: ...skip
        tid = target["id"]
        if tid == spawner_agent_id: ...self-skip
        if tid in chain_agent_ids: ...cycle-skip (log only)
        if depth + 1 > GROUP_A2A_DEPTH_CAP:
            await self._inject_agent_error(..., "Group A2A depth would exceed 3 hops")
            continue
        # 串行 dispatch — 不再 _check_a2a_chain / walk_parent_chain
        await self._run_mentioned_agent(
            run, target, group,
            spawner_agent_ids=chain_agent_ids,
            spawner_agent_name=spawner_agent_name,
            depth=depth + 1,
        )
```

- **删除 `_check_a2a_chain`** 和对 `walk_parent_chain` 的依赖。
- **`session_chain.py` 保持不变**：delegations 仍在用它，不删。
- 串行 dispatch（await 一个再下一个）保持不变。

#### 3.4 `delete_group` 级联硬删

```python
async def delete_group(self, group_id: str) -> bool:
    ...
    # 1. 拒绝有 in-flight turn 的 group
    run = self._runs.get(group_id)
    if run and run.worklist:
        raise GroupError("Cannot delete group with active agent turns")
    # 2. 拿到所有 (group×agent) session ids
    member_sessions = await self.db.list_group_agent_sessions(group_id)
    # 3. 真删 sessions（backing + member）
    if group and group.get("session_id"):
        await self._hard_delete_session(group["session_id"])
    for ms in member_sessions:
        await self._hard_delete_session(ms["session_id"])
    # 4. 删 group + group_members + group_agent_sessions（FK CASCADE 自动清后两个）
    result = await self.db.delete_group(group_id)
    self._runs.pop(group_id, None)
    return result

async def _hard_delete_session(self, session_id: str) -> None:
    """Hard-delete a session: remove from memory, delete DB row + JSONL file."""
    if self.session_manager:
        # 取消任何 in-flight task（理论上前面 worklist 检查已拦截）
        # 内存 pop
        self.session_manager.sessions.pop(session_id, None)
    if self.db:
        # 删 DB sessions 行（messages 表 FK CASCADE）
        await self.db.delete_session(session_id)
    # JSONL 文件清理（如果 db.delete_session 不连带删 JSONL，需补）
```

> **实现时确认点**：db 层是否已有 `delete_session`、是否连带删 JSONL 文件。如果没有，新加一个 helper（参照 `archive_session` 但真删）。

#### 3.5 `remove_member` 清理对应复用 session

```python
async def remove_member(self, group_id: str, agent_id: str) -> None:
    ...
    # 拒绝 remove 正在跑的 agent
    run = self._runs.get(group_id)
    if run:
        for entry in run.worklist:
            if entry.agent_id == agent_id:
                raise GroupError("Cannot remove an agent with an active turn")
    # 硬删该 agent 的复用 session
    sid = await self.db.get_group_agent_session(group_id, agent_id)
    if sid:
        await self._hard_delete_session(sid)
    await self.db.remove_group_member(group_id, agent_id)
```

### 4. 测试改造

#### 4.1 `tests/test_group_manager.py`（unit，~25 case，无需 harness）

- `TestParseMentions` / `TestGroupError` / `TestGroupManagerUnit` 几乎不变（只测纯函数和 CRUD）。
- 改针对 `_run_mentioned_agent` 的 mock 设置：原本 `sm.create_session = AsyncMock(return_value=child_session)`，新版改为先 `db.get_group_agent_session` 返回 None → `_get_or_create_member_session` 调 `create_session` → `db.upsert_group_agent_session`。第二次 @ 同一 agent 时 `db.get_group_agent_session` 返回已存在 session id，**断言 `create_session` 不再被调用**。

#### 4.2 `tests/test_group_manager_mention.py`（9 个 A2A case，重写最多）

- `TestRunMentionedAgent`（7 case，line 9-258）：基本保留，但 mock 改为复用 session 模式。
- `TestRunMentionedAgentA2A`（9 case，line 259+）—— **几乎全部重写**：
  - `_patch_walk` helper 删除（不再用 chain walk）。
  - cycle 测试改成"传递 `spawner_agent_ids={Alice}`，target=Alice → skip"。
  - depth cap 测试改成"传递 `depth=2`，target=新 agent → depth+1=3 触发 reject"。
  - serial drain 测试改成"两个 @ 串行 await"。
  - user-path 测试改为"depth=1 第一跳 → 子 call depth=2"。

#### 4.3 `tests/test_group_manager_backend_error.py`（3 case）保留逻辑，mock 适配复用 session。

#### 4.4 `tests/test_group_e2e.py`（3 case）基本不变，确认 user message + agent reply 注入 backing session 仍然正确。

#### 4.5 `tests/test_group_real_claude.py`（1 case）跑真实 claude，确认 `--resume` 在第二次 @ 时正确恢复私有记忆。**新增一个 case**：同群连续 @ 同一 agent 两次，第二次 reply 应能引用第一次的内容（验证私有记忆生效）。

### 5. 前端适配（`web/src/`）

理论上**前端无需改动**：

- 用户消息 + agent reply 仍然以 `inject_message` 到 backing session 的方式广播。
- 流式 `group_agent_text` + 最终 `[agent-reply:Name]` 契约不变。
- typing 事件契约不变。

唯一可能的视觉差异：sidebar 会出现 `(group×agent)` 复用 session 节点（如果 UI 把 child session 显示出来）。需检查 `SessionList.tsx` 是否过滤掉 `origin='group_member'` —— 如果显示出来对用户可能造成困惑。**实现时拍板**：要么在 sidebar 隐藏 `origin in ('group_member', 'group_reply')`，要么作为 group 的子节点显示。

---

## 关键文件清单

| 文件 | 改动 |
|------|------|
| `server/database.py` | +`group_agent_sessions` 表 schema；+4 个 helper（upsert/get/list/delete） |
| `server/group_manager.py` | 重写 `_run_mentioned_agent` / `_dispatch_a2a_mentions`；新增 `_get_or_create_member_session` / `_hard_delete_session`；改 `delete_group` / `remove_member`；**删** `_check_a2a_chain` |
| `server/session_manager.py` | （可能）加 `load_session_from_db` helper 用于 server 重启后恢复复用 session |
| `tests/test_group_manager.py` | 改 mock 适配复用模式 |
| `tests/test_group_manager_mention.py` | 重写 A2A 9 case（删 `_patch_walk`，改 in-memory depth） |
| `tests/test_group_manager_backend_error.py` | 适配复用 mock |
| `tests/test_group_e2e.py` | 基本不变 |
| `tests/test_group_real_claude.py` | 新增 `--resume` 私有记忆验证 case |
| `web/src/components/SessionList.tsx` | （可能）隐藏 `origin='group_member'` 的 session 节点 |
| `docs/plans/group-session-reuse.md` | 把本 plan 落到 plans 目录（CLAUDE.md 惯例） |

## 复用的现有能力（不新写）

- `SessionManager.start_message` 的 busy→queue 机制（`session_manager.py:1669-1702`）—— A2A 串行化靠它。
- `SessionManager.inject_message`（`session_manager.py:1605-1639`）—— backing session 写入靠它。
- `SessionManager.create_session` 的 `origin` + `parent_session_id` + `backend` + `credential_id` 参数（`session_manager.py:1050-1111`）—— 复用 session 创建靠它。
- `delegations.py:312-424` `follow_up_delegation` 的复用模式（`start_message(rec.delegation_id, …)`）—— 直接参照。
- `database.py` 现有 `groups` / `group_members` 表 + helper 风格 —— 新表保持一致。
- `group_manager.parse_mentions` / `_format_group_context` / `_build_augmented_prompt` / `_resolve_agent_by_name` / `_inject_agent_reply` / `_inject_agent_error` / `_broadcast_typing` / `_collect_agent_reply` —— **全部保留不动**。

## 验证

### 单元测试
```bash
.venv/bin/pytest tests/test_group_manager.py tests/test_group_manager_mention.py \
  tests/test_group_manager_backend_error.py tests/test_group_e2e.py -v
```

### Real-CLI（需要 claude 在 PATH）
```bash
.venv/bin/pytest tests/test_group_real_claude.py -v
```

### 全套回归
```bash
.venv/bin/pytest tests/ -v
```
特别关注 `tests/test_delegations.py` —— 不能因为 `group_manager` 不再用 `walk_parent_chain` 而误删或改 `session_chain.py`。

### 前端
```bash
cd web && bun run test
cd web && npx tsc --noEmit
cd web && bun run build
```

### 手动 E2E
1. 创建一个 3-agent 群（Alice/Bob/Carol）。
2. @Alice 问问题，等她回复。
3. 再 @Alice 问跟进问题，验证 Alice 第二次回复能引用第一次的内容（`--resume` 私有记忆生效）。
4. @Alice 让她 @Bob 帮忙，验证 A2A 传球仍工作。
5. Alice 回复里 @Bob @Carol，验证串行 dispatch 顺序。
6. 构造 A→B→C→D 链条（D 是第 4 个 agent），验证 depth cap reject 注入 `[agent-error:D]`。
7. 删除 group，验证 backing session + 3 个 (group×agent) session 都从 sidebar 和 DB 消失。

### 边界 case
- Server 重启后，已有的 group 第一次 @ 应该能从 DB 恢复 (group×agent) session。
- A2A 在目标 agent busy 时排队，turn 完成后自动接下一条（前端能看到 typing 持续 / 重新开始）。
- remove_member 一个正在跑 turn 的 agent 应被拒绝。