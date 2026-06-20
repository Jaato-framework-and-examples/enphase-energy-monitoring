# enphase_monitoring — jaato client peer-review

**Date:** 2026-06-20 · **Reviewer:** `enphase-review` peer
**Baseline:** current jaato at `../jaato`; source-of-truth `jaato-sdk-client/SKILL.md`
**Tools used:** `python -m jaato_sdk.doctor` (DOCTOR) and `shared.scaffold` (SCAFFOLD), both run against the *installed* framework so the findings can't drift.

Targets reviewed: `src/jaato_advisor.py`, the `.jaato/` workspace, `.env`. Supporting:
`src/jaato_agents_config.py`, `requirements.txt`, `docker/`.

## TL;DR

The client is an **old SDK shape (Feb 2026) and will not run** against the
current SDK. There are **7 hard API breaks** (each fails before any model output)
and the workspace carries **none of the assets a current jaato client is expected
to have** — no `.jaato/profiles/`, no `.jaato/agents/`, no real tools. The three
"specialized agents" exist only as a dead Python module the runtime never imports.

Environment itself is healthy: DOCTOR is green (daemon reachable, HOME matches,
`pass://` store shared, `zhipuai` provider present, `glm-4.7` is a valid model).
So the work is entirely in the client code + workspace assets, not the daemon.

---

## A. BROKEN vs current APIs (hard breaks — won't run)

Evidence: live signature introspection of the installed `jaato_sdk` + the
scaffold's known-good `new client` recipe.

| # | Where | Current API (evidence) | Result |
|---|-------|------------------------|--------|
| A1 | `jaato_advisor.py:94` `IPCRecoveryClient(socket_path=…, auto_start=…, env_file=…)` | `__init__(self, socket_path, *, client_type, …)` — `client_type` is **keyword-only and required** | `TypeError` at construction |
| A2 | imports (`:30`) | `ClientType` now lives in `jaato_sdk.events` (re-exported `from jaato_sdk import ClientType`); never imported here | `NameError`/can't fix A1 |
| A3 | `:125` `send_message` straight after `connect` | a session must exist first: `create_session(profile=…, agent=…)` returns the sid; advisor never calls it | no active session → send fails |
| A4 | `:450` `event.content` | `AgentOutputEvent` fields are `type, timestamp, agent_id, source, **text**, mode` — no `content` | `AttributeError` |
| A5 | `:119-129` / `:445-451` `async for event in client.events()` as the response stream, no break | `send_message()` now returns `None`; output arrives via **callbacks** (`subscribe(AGENT_OUTPUT,…)`), completion via `subscribe_once(SESSION_TERMINATED,…)`. The drain loop has no completion condition | **hangs forever** even if A1–A4 fixed |
| A6 | `:104` `await self.client.connect()` (no timeout) | `connect(timeout=5.0)` default; cold autostart is ~30-60s. Recipe uses `connect(timeout=120)` | autostart times out on a cold daemon |
| A7 | `JaatoClientWrapper` whole design | built on a generator-drain contract that no longer exists; current contract is callback-subscription + an `asyncio.Event` you `await` | wrapper is unsalvageable as-is |

Chosen client class: the recipe uses **`IPCClient(client_type=ClientType.API)`**
(API type keeps `signal_completion`). `IPCRecoveryClient` still imports but is for
reconnection-heavy clients and *also* now requires `client_type`; for this
advisor, `IPCClient` is the canonical choice.

**Canonical shape** (`jaato-scaffold new client`, compiles clean):
```python
from jaato_sdk import IPCClient, ClientType, EventType
client = IPCClient(SOCKET, client_type=ClientType.API, auto_start=True,
                   env_file=ENV_FILE, workspace_path=WORKSPACE)
await client.connect(timeout=120.0)
done = asyncio.Event()
client.subscribe(EventType.AGENT_OUTPUT, lambda ev: print(ev.text, end=""))
client.subscribe_once(EventType.SESSION_TERMINATED, lambda ev: done.set())
sid = await client.create_session(profile={"model": MODEL, "provider": PROVIDER})
await client.send_message(prompt)
await done.wait()
```

---

## B. STALE vs current best-practice (runs, but not a well-built client)

1. **No `.jaato/profiles/` at all.** SCAFFOLD `explain sets --workspace .` → *"no
   .jaato/profiles/ under ."*. Current shape is a **profile-set**: tier-1
   `_base_<agent>.yaml` (provider-agnostic, `inherits:`) + tier-2
   `<provider>_<model>/<agent>.yaml`, selected at runtime by `JAATO_PROFILE_SET`
   (read 44× in the framework; unset here). The advisor pins provider/model only
   via single-model env mode and declares no plugins / tool_scopes / gc /
   permissions / max_turns.

2. **`src/jaato_agents_config.py` is dead AND the wrong shape.** The runtime
   (`jaato_advisor.py`) never imports it — only a test and the Dockerfile copy it.
   So its 3 "specialized agents" never reach jaato. Even conceptually it is stale:
   - agent identity/system prompts now live in **`.jaato/agents/<name>.md`** markdown personas;
   - profile `system_instructions` is **DEPRECATED** in favour of those agents;
   - its dataclass fields map to nothing current: `temperature`/`max_tokens` →
     `plugin_configs.<provider>.api_params`, `tools` → profile `plugins` +
     `tool_scopes`, `memory_enabled` → not a knob.

3. **Tool names are imaginary.** `influxdb_query`, `fetch_pvpc_prices`,
   `calculate_savings`, `fetch_weather_forecast`, `check_user_preferences`, … are
   not real plugins or MCP tools (43 plugins are available; none wired). The
   advertised "tool use for external APIs" is non-functional.

4. **Multi-agent / memory / streaming claims are unimplemented.** The module
   docstring promises subagents, multi-agent reasoning, and a memory system; the
   code sends one prompt to one default session. Sub-agents today come from
   `create_session(agent=…)` per agent or a cascade — none present.

5. **`AI_USE_CHAT_FUNCTIONS=1` in `.env` is a dead knob** — 0 reads in the
   framework. Legacy from the Ollama era. (`JAATO_PROVIDER` / `MODEL_NAME` *are*
   correct and match the scaffold's canonical `.env`; `glm-4.7` is a valid
   zhipuai model — those are fine.)

6. **`sys.path.insert(.venv/lib/python3.12/site-packages)` (`:24-27`)** —
   hardcoded interpreter-version path; brittle. Run inside the venv / install the
   package instead. *(Conflicts with the no-hardcoded-path rule in CLAUDE.md.)*

7. **`ImportError → JAATO_SDK_AVAILABLE=False` fallback (`:29-34`)** masks SDK
   drift: the imports now *succeed* (names still exist) and the failure surfaces
   later as a confusing `TypeError`. A defensive fallback hiding the real break.
   *(Conflicts with the no-fool-defensive-programming rule in CLAUDE.md.)*

8. **`requirements.txt` pins `jaato-sdk==0.1.0` from TestPyPI** — predates the
   `client_type`/`create_session` API. The working SDK is local `../jaato/jaato-sdk`.

9. **InfluxDB readiness loop hardcodes host `"influxdb"` (`:302`)** — docker
   service name baked into the client, not env-driven. *(no-hardcoded rule.)*

10. **PVPC prices are static constants** (`PriceEstimator`, agent prompts) while
    docs claim live ESIOS API integration — misleading/stale.

---

## C. Prioritized adaptation punch-list

### P0 — restore basic function (client won't run without these)
1. Regenerate the entrypoint from `jaato-scaffold new client --provider zhipuai
   --model glm-4.7` and graft the InfluxDB fetch + prompt-builder onto it. This
   resolves A1–A7 in one move (correct `IPCClient`/`ClientType`, `create_session`,
   `connect(timeout=120)`, callback subscriptions, `event.text`, completion on
   `SESSION_TERMINATED`). Keep `EnergyContext`/`InfluxDBFetcher`/`PriceEstimator`.
2. Delete `JaatoClientWrapper` (its generator-drain contract no longer exists).
3. Gate runs on `python -m jaato_sdk.doctor --workspace . --env-file .env` (already green).

### P1 — make it a current, well-built jaato client
4. Create a **profile-set** under `.jaato/profiles/` (`jaato-scaffold new
   profile-set --set zhipuai_glm-4-7 --provider zhipuai --model glm-4.7 --agents
   price_analyst,solar_optimizer,appliance_scheduler`), move the three system
   prompts into `.jaato/agents/*.md`, set `JAATO_PROFILE_SET`, then
   `jaato-scaffold validate .`. Delete `src/jaato_agents_config.py` after migration.
5. Decide the tool story: either wire **real** tools (a small MCP server or
   plugins for InfluxDB/PVPC, declared via profile `plugins` + `tool_scopes`) or
   drop the tool/multi-agent claims from code + docs. Don't ship imaginary names.
6. Repin `requirements.txt` to the real SDK (local `../jaato/jaato-sdk` or the
   current published version); remove TestPyPI `0.1.0`.

### P2 — hygiene / root-cause cleanup
7. Remove `AI_USE_CHAT_FUNCTIONS` from `.env`; remove the `sys.path.insert` hack
   and the `ImportError` fallback (let a missing SDK fail loudly).
8. Env-drive the InfluxDB host (drop hardcoded `"influxdb"`).
9. Reconcile `docs/` + module docstrings with reality (ESIOS, memory, multi-agent).

---

---

## D. Implementation status — FULL rebuild applied (2026-06-20)

The "Full: current-patterns rebuild" path was implemented and validated end-to-end.

**Applied:**
- **`src/jaato_advisor.py` rewritten** on the scaffold `IPCClient` recipe:
  `IPCClient(client_type=ClientType.API)`, `connect(timeout=120)`,
  `create_session(profile=<name>, agent=<name>)` per specialist, callback
  subscriptions (`AGENT_OUTPUT`/`TURN_COMPLETED`/`ERROR`), `event.text`,
  `asyncio.Event` completion. `JaatoClientWrapper` deleted. Resolves A1–A7.
- **`.jaato/` profile-set authored:** `profiles/_base_<agent>.yaml` (tier-1) +
  `profiles/zhipuai_glm-4-7/<agent>.yaml` (tier-2, per-agent temp/max_tokens) +
  `agents/<agent>.md` personas (migrated from the deleted `jaato_agents_config.py`,
  imaginary-tool references removed). Selected via `JAATO_PROFILE_SET`.
- **Hygiene:** deleted `src/jaato_agents_config.py`; removed `AI_USE_CHAT_FUNCTIONS`
  (+ `.env`/docker envs), the `sys.path` hack, and the `ImportError` fallback;
  repinned `requirements.txt` to the real SDK (`-e ../jaato/jaato-sdk`, 0.14.6);
  env-drove the InfluxDB readiness host; dropped the dead Dockerfile COPY;
  rewrote `tests/test_jaato_advisor.py` to the new architecture.
- **InfluxDB read-path fix (pre-existing bug, not jaato-related):** the advisor's
  `InfluxDBFetcher` queried measurement `home_energy` / field `grid_consumption_w`,
  but the collector writes measurement `energy_readings` / field `home_consumption_w`
  (verified live) → the advisor always read zeros. Fixed both Flux queries to the
  real schema and derive the unmetered grid import/export from the
  consumption/production balance. Requires `INFLUXDB_TOKEN` in the advisor's env
  (already supplied via `docker/.env`; unauthenticated reads return empty, not an
  error). Verified live: consumption 1326W + a full 24h curve + a midday solar
  bell-curve peaking 2242W now reach the agents.

**Validation evidence (all run from the venv where jaato is installed — see Appendix):**
- `jaato-scaffold validate . --set zhipuai_glm-4-7` → *all profiles valid*.
- `jaato-doctor --workspace . --env-file .env` → 0 fail / 1 warn.
- Module imports cleanly against live SDK 0.14.6; `IPCClient` constructs with current kwargs.
- **Live multi-agent run works end-to-end:** across 4 back-to-back runs (12
  specialist calls) **11/12 succeeded** with full analyses (2.4k–6k chars each).
  The InfluxDB test bucket is empty, so agents reasoned over all-zero readings —
  and correctly flagged the missing data rather than inventing numbers.
- **Known intermittency (daemon-side, not a client defect):** ~1 specialist call
  per 3–4 runs fails transiently, surfacing as
  `RunnerCallError`/`ZhipuAIAPIKeyNotFoundError` or `ProfileNotFoundError` — a
  credential-resolution / profile-discovery warm-up race on the daemon. Most
  frequent on the first (cold) session of a run but observed on later sessions
  too. The same profile/agent/auth config succeeds on retry, and failures are
  surfaced cleanly by per-specialist ERROR handling (no crash). Root-cause fix
  belongs in `../jaato` (daemon warm-up), not this client; no blind client-side
  retry was added.

**Not done (deferred, P2.9):** reconcile `docs/` + `README`/`INDEX` prose (ESIOS,
memory, multi-agent claims, `jaato_agents_config` references) with the new reality.
Docker *deployment* of the local editable SDK + mounting `.jaato/profiles/` into the
container is a separate deployment task, not part of the client-pattern rebuild.

---

## Appendix — verification commands (all reproducible)

Run these from **the venv where jaato is installed** — the one with `jaato_sdk`
+ `jaato-server` installed (editable in this monorepo); the project `.venv` has
neither, and Bash subprocesses do not inherit a shell `activate`. Below, set
`JAATO_VENV` to that venv (in this environment it was `/tmp/jaato-test`):

```sh
JAATO_VENV=/path/to/your/jaato-venv   # e.g. the editable monorepo venv
```

Its `bin/` exposes the console shortcuts `jaato-doctor` / `jaato-scaffold`
(no `PYTHONPATH` needed):

- `"$JAATO_VENV"/bin/jaato-doctor --workspace . --env-file .env` → 0 fail / 1 warn.
- `"$JAATO_VENV"/bin/jaato-scaffold validate . --set zhipuai_glm-4-7` → *all profiles valid*.
- `"$JAATO_VENV"/bin/jaato-scaffold explain sets --workspace .` → `zhipuai_glm-4-7 → 3 agents`.
- `"$JAATO_VENV"/bin/jaato-scaffold explain provider zhipuai`
- `"$JAATO_VENV"/bin/python -c "import inspect,jaato_sdk.client as c; print(inspect.signature(c.IPCClient.__init__))"`
- Live: `"$JAATO_VENV"/bin/python src/jaato_advisor.py --analyze-once` (needs daemon + zhipuai auth).
