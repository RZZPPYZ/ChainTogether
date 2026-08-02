# F002 Orchestration Design

## Lifecycle-bearing object census

| Object | Owner | Durable state | Terminal or recovery rule |
|---|---|---|---|
| UI command draft | GroupChatView | browser component state plus stable `request_key` for one submit | Clear on accepted start; retain exact text on failure. |
| FeatureStart | FeatureDeliveryManager/DB | `preparing`, `doc_pending`, `dispatch_pending`, `running`, `blocked`, `done` | A retry with the same key resumes the same run; recovery advances checkpoints. |
| FeatureRun | F001 FeatureManager | canonical lifecycle stage/state/revision and role IDs | Remains the only product lifecycle state machine; `done` clears active pointer. |
| Group active pointer | F001/DB | one selected FeatureRun per group | Claimed with `INSERT ... ON CONFLICT DO NOTHING`; losing starts roll back. |
| Feature Doc outbox | F001/DB | exact create/update image and disk baseline mode | Create-only or update delivery is idempotent; conflict fails closed. |
| Role assignment | FeatureRun | owner/reviewer/guardian IDs | Three distinct live group members; operator can patch before the affected protected action. |
| FeatureDispatch | FeatureDeliveryManager/DB | revision, purpose, generation, target, lease, invocation ID, state | One pending/leased/active dispatch per run; stale revision is superseded; dead/failed is retryable. |
| GroupInvocation | GroupManager | one depth-bounded A2A custody segment linked to FeatureRun/dispatch | Each successor dispatch creates a new depth-zero invocation; terminal callback releases the dispatch. |
| Group-agent Session | SessionManager/DB | group, agent, Session ID, ephemeral capability in live process | Server derives actor; missing Session/role membership blocks dispatch/transition. |
| Feature MCP process | Harness assembly | stateless stdio child with Session env | Calls Session-bound REST only; no direct DB access. |

## Required actor matrix

| Action/stage | Required actor | Successor |
|---|---|---|
| discovery, design, planning, implementation, quality | owner | next stage owner |
| quality -> review | owner | review-preparation owner |
| `request_review` within review | owner | reviewer |
| review -> implementation (`request_changes`) | reviewer | owner |
| review -> merge (`approved`) | reviewer | owner |
| merge -> acceptance | owner | vision guardian |
| acceptance -> discovery/implementation/closure | vision guardian | owner for gap/closure |
| closure -> done | owner | none |
| status | any live member Session in the Feature group | reports required actor |
| role patch | authenticated operator UI/API, not MCP | recompute pending target or block active dispatch |

F002 strengthens owner-stage authorization where F001 previously treated the
owner as guidance. Review and Vision rules retain their existing hard gates.

## FeatureStart state/events

| State | Event | Guard | Next/effect |
|---|---|---|---|
| none | start | valid requirement, >=3 live members, no active pointer claim | one DB transaction inserts full FeatureRun/roles/event, active pointer, start row, create-only doc outbox, initial dispatch -> `doc_pending` |
| `doc_pending` | doc delivered | exact path absent or exact desired image already present | `dispatch_pending` |
| `doc_pending` | disk conflict/failure | cannot safely create image | `blocked`, preserve run and retry key |
| `dispatch_pending` | invocation launched | target still live/assigned and no active invocation | `running` |
| `running` | FeatureRun done | closure evidence accepted | `done` |
| any nonterminal | retry same request key | group and requirement hash match | return/resume same run; never create another |

The database transaction, not the filesystem, is the commit point. The
create-only document outbox lets a crash leave a recoverable pending image,
not an unowned file. Feature ID allocation and active-pointer claim occur under
the Feature write transaction; a uniqueness loser rolls back all rows.

## FeatureDispatch state/events

| State | Event | Guard | Next/effect |
|---|---|---|---|
| none | stage transition committed | target stage has successor actor | insert revision-bound `pending` dispatch in same transition transaction |
| none | owner requests independent review | run is review at exact revision; packet/evidence valid | insert `review_request` dispatch to reviewer |
| none | operator resumes | no pending/leased/active dispatch and no live linked invocation | insert next generation `resume` dispatch |
| `pending` | lease | lease absent/expired; observed run revision still current | `leased` |
| `leased` | invocation reserve/inject/launch | deterministic dispatch marker/ID; target live | `active`, persist invocation ID |
| `leased` | stale revision/role | FeatureRun or assignment changed | `superseded`, recompute from current run |
| `active` | invocation resolved/completed | terminal GroupInvocation | `completed`; wait for transition-created successor or explicit resume |
| `active` | invocation dead/failed/blocked | no accepted successor transition | `failed`; status exposes retry/blocker; resume may create next generation |
| `leased` | process crash | lease expires | another worker resumes same deterministic dispatch |

The group message contains a deterministic `[feature-dispatch:<id>]` marker.
Launch checks both the dispatch row and existing invocation/message marker so a
retry can finish a partially launched dispatch without injecting a second user
message. A pending successor waits until the current invocation is terminal;
the MCP tells the current Agent to end its turn after a successful transition
or `request_review`.

## Numbered invariants

1. F001 FeatureRun is the only lifecycle stage/state authority; dispatch never
   advances a stage.
2. At most one group active-pointer claim wins a concurrent start transaction.
3. One request key maps to one FeatureRun; retries cannot change its group or
   requirement hash.
4. Owner, reviewer, and guardian are distinct live, non-archived group members
   at assignment and are revalidated before protected action/dispatch.
5. Stable fallback order is `(joined_at, agent_id)`; a valid non-archived group
   default Agent is owner, otherwise the first row wins.
6. At most one FeatureDispatch is pending, leased, or active for a FeatureRun.
7. Every dispatch is bound to exact FeatureRun `updated_at`, stage, purpose,
   target role, and generation. A stale binding can only be superseded.
8. Every launched successor GroupInvocation is linked to its FeatureRun and
   dispatch and begins at A2A depth zero.
9. Actor identity comes only from the capability-bound live group-agent
   Session. MCP does not accept caller-supplied agent/group/role authority.
10. MCP transition calls exactly the F001 transition service and cannot update
    lifecycle tables directly.
11. Protected Review/Vision evidence and Git provenance remain fail-closed;
    owner-stage edges additionally require the assigned owner.
12. A role loss blocks the affected dispatch or edge. Only authenticated
    operator role patching can reassign; no Agent self-reassigns through MCP.
13. Successful closure leaves no active group pointer or pending/active
    dispatch, and status reports terminal truth.
14. `/feature` merge authorization applies only after green Quality, Review,
    and Merge Gates and repository policy; force/policy bypass is never implied.

## Adversarial matrix

| Scenario | Expected evidence |
|---|---|
| Two different start keys race | one active-pointer transaction commits; loser returns existing run; one doc and initial dispatch |
| Same start key retries at every checkpoint | same run/roles/path; checkpoint advances idempotently; no duplicate message/invocation |
| Crash after DB start before doc | reconciler delivers create-only image, then dispatches |
| Crash after message injection before invocation checkpoint | deterministic marker is found and launch resumes without second message |
| Two resumes race | one dispatch generation wins; both responses identify it |
| Transition and resume race | transition revision wins; old resume is rejected/superseded; successor targets new stage |
| Old leased worker wakes late | revision/lease CAS fails; it cannot launch or overwrite new target |
| Server restarts with running invocation | GroupManager marks it dead; dispatch becomes failed; resume recomputes target from current FeatureRun |
| Owner fixes after Review request_changes | reviewer transition creates fresh owner invocation at depth zero; later review uses another new invocation |
| Assigned Agent removed/archived/backend unavailable | dispatch/edge blocks with exact role; operator patches roles or restores Agent, then resumes |
| Wrong Session/capability/group/run calls status or transition | 403/409; no dispatch, event, doc, or FeatureRun mutation |
| Owner attempts self-review or reviewer attempts Vision | existing F001 gate rejects; no successor dispatch is inserted |
| Feature MCP omitted from stored Agent selection | still present because it is mandatory core assembly, not a selectable connector |
| Merge Gate red/protected policy denies merge | Feature remains merge/blocked; no force or policy override |

## Operator authorization decision

The operator explicitly requested that one `/feature` sentence continue
"直至交付". F002 interprets that command as run-scoped authorization for the
assigned Agents to modify the selected repository, commit, push the feature
branch, open/update a PR when repository policy uses one, and merge only after
the F001 Quality, independent Review, and Merge Gates are green. It is not
authorization to force-push, bypass branch protection/CI, deploy to production,
change unrelated systems, or invent a missing value decision. Those conditions
produce an explicit blocker.
