# LiveRig Branching Strategy

Two parallel workstreams need to coexist without stepping on each other:

1. **Scalability refactor** — moving the controller off hardcoded 4-keyboard/8-patch/4-stem assumptions onto `rig_config.json`. Driven from this chat.
2. **Extensions SDK rig-setup tool** — a new configuration/setup tool built against Ableton's Extensions SDK. Driven from Claude Code.

## Branch layout

- `main` — always stable, always reflects what's actually running on the rig.
- `refactor/rig-config` — the scalability refactor. Owned by this chat.
- `feature/extensions-sdk-setup` — the Extensions SDK tool. Owned by Claude Code.

Both feature branches fork from `main` at the same commit (`a134b3e` or later, once `rig_config.json` schema lands — see Sequencing below).

## The shared dependency: rig_config.json

Both branches read `rig_config.json`. To avoid the two branches drifting on its shape:

- The schema (`rig_config.schema.json`) is the contract. It gets committed to `main` first, before either branch does substantive work.
- Neither branch may change the schema unilaterally. A schema change is a PR against `main`, reviewed in the chat/session that didn't propose it, then merged and rebased into both feature branches.
- Treat the schema like an API contract between two teams — because that's effectively what it is here.

## Sequencing

1. Commit `rig_config.schema.json` + `rig_config.example.json` to `main`. *(done by this task)*
2. Cut `refactor/rig-config` from `main`. This chat updates the Remote Script and patch snapshot logic to read keyboard/patch/stem counts from config instead of hardcoded constants.
3. Cut `feature/extensions-sdk-setup` from the same commit. Claude Code builds the setup tool to read/write configs conforming to the same schema.
4. Both branches can develop independently as long as neither touches the schema without the PR step above.
5. Merge order: `refactor/rig-config` merges to `main` first (it's the consumer the schema was designed around), then `feature/extensions-sdk-setup` rebases onto the updated `main` and merges second.

## Conflict zones to watch

- **Remote Script files** — only `refactor/rig-config` should touch these. The Extensions SDK tool should only ever *write* config files, never the Python Remote Script itself.
- **`rig_config.schema.json`** — shared contract, change via PR only (see above).
- **`rig_config.example.json`** — low risk, but update it whenever the schema changes so it never goes stale.

## Commit hygiene

- Keep commits scoped to one branch's concern. If a change touches both the schema and Remote Script logic, split it into a schema-PR commit plus a refactor-branch commit.
- Tag the commit where the schema lands on `main` (e.g. `schema-v1.0`) so both branches have an unambiguous fork point to rebase against later.
