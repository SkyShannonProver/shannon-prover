# Manager-tool infrastructure ownership

The agent tools use one end-to-end path with one owner for each fact. Provider
configuration, the MCP child process, source confinement, turn serving, proof
semantics, and final proof outcome are deliberately separate boundaries.
Module boundaries follow process boundaries: everything the provider-spawned
child does lives in one file, everything the parent's loopback endpoint does in
another.

```text
ProofToolContractManifest
  owns the stable tool identity, envelope version, and profile intent
  manifest (a frozen dataclass; == is its whole identity)
        |
        v
ProviderLaunchAdapter (Claude or Codex)
  owns provider capabilities and invocation-specific launch syntax
        |
        v
proof_node_mcp_server (the provider-spawned child, one file)
  owns newline-JSON stdio framing, fail-closed JSON-RPC/MCP message order,
  the readiness ACK gate, and forwarding raw tool arguments
        |
        v
ProofToolEndpointServer (parent side)
  owns the token-authenticated loopback envelopes, the single armed launch
  registration, and all envelope validation
        |                           |
        | source navigation         | proof intent
        v                           v
EasyCryptSourceResource       ProofToolSession
  validates the canonical       owns call replay, turn serialization, turn
  proof-stripped task ledger,    budget, node memory, response rendering,
  library roots, and budgets     and the stop/unhealthy latch
                                    |
                                    v
ProofNodeManager
  owns one complete semantic turn: decode, admission/repair, execution,
  view refresh, exact post-state history binding, and compiler delivery
        |
        v
ReplSessionManager
  is the sole EasyCrypt session and proof-mutation owner
```

Only `workflow.agents.prover.run()` may publish final proof success after
offline EasyCrypt verification.  A `finish` intent produces a serving
directive (`STOP_REQUESTED`); it does not mean that the proof is closed or
verified.

## Single-owner facts

- `ProofToolContractManifest` is resolved once per node.  The same object is
  used by prompts, provider launch adapters, the MCP child, and manager
  admission.  Callers do not recreate server/tool names or profile intent
  sets.  Manifest identity is dataclass equality — the manifest travels
  parent -> child argv within one process tree on one machine, so there is
  no self-authenticating digest and no repeated re-validation.
- The MCP input schema is intentionally transport-permissive.  It accepts an
  object without requiring or enumerating fields so malformed submissions can
  reach manager-owned protocol repair.  The manager is the only semantic
  intent decoder and admission authority.
- Eval nodes may additionally advertise `search_easycrypt_source`,
  `read_easycrypt_source`, and `resolve_easycrypt_declaration`. Search performs
  bounded literal matching over the attested task files and configured theory
  roots and returns copy-ready paths and line numbers. Read takes one exact
  repository-relative `.ec`/`.eca` path and a bounded line range. Resolution
  sends one exact candidate identifier to EasyCrypt's native namespace printer;
  lexical matches are never promoted to typed facts. The parent validates the
  canonical proof-stripped preparation manifest, file digest, allowed roots,
  and output budgets. The provider-spawned MCP child never opens files, and
  source navigation never consumes or mutates a proof turn. Every fresh
  provider context and context respawn receives a compact source map with the
  prepared task paths (target first) and configured library root.
  Provider-native filesystem, shell, and generic resource tools remain disabled.
- Each provider invocation has a fresh launch identity.  The endpoint arms
  exactly one launch id at a time; arming a new invocation revokes the prior
  child.  The child is ready only after the MCP handshake and tool listing
  complete and its READY for the armed launch id is acknowledged.  Readiness
  failures print their cause to the child's stderr (which the provider
  captures) — debug logs are diagnostics, never readiness authority.
- Each tool call has a runtime-bound call identity minted by our own adapter
  (`launch_id:jsonrpc_id`, human-readable so audit logs match back to
  requests).  A repeated call id replays the exact cached response; a session
  that has latched unhealthy replays the unhealthy result instead of reviving
  a stale success.
- One absolute request deadline covers the complete atomic turn.  Inner
  manager/backend work must stop before loopback and provider deadlines.  If
  termination cannot be confirmed, the node becomes unhealthy and accepts no
  retry.
- Committed tactics cross the manager boundary only as an immutable,
  post-state-bound turn spine obtained once through `ReplSessionManager`.
  Infrastructure does not reread session files or infer proof closure from a
  tactic suffix.
- Provider-specific event decoders normalize raw streams.  A shared lifecycle
  guard validates canonical call identities, ordering, terminal cardinality,
  and process exit independently for each invocation.  Live and offline
  validation use the same decoder and guard.
- Fresh-context continuation (Layer 1) is provider-neutral: the watermark
  detector consumes Claude assistant-event usage or Codex `turn.completed`
  usage through one `observe_tokens` core, and a respawn clears the Codex
  thread id so the fresh generation starts cold.

## Serving states versus proof states

Serving control has exactly three outcomes:

```text
CONTINUE | STOP_REQUESTED | NODE_UNHEALTHY
```

These values control whether the proof-turn endpoint accepts another intent.
They do not project EasyCrypt lifecycle state.  EasyCrypt state remains in the
canonical manager view, and whole-run success remains in the verified
`ProverResult`.

## Retired paths

The current design has no second bridge parser, action-dictionary terminal
inference, provider-to-provider config translation, debug-log readiness scan,
unconditional Codex feature disable list, or provider-specific tool policy
used as a semantic fallback.  Compatibility is capability-based: required
provider capabilities fail before model launch, while optional feature flags
are emitted only when the installed provider advertises them.

Also retired (2026-08-19 lightweight pass): the manifest sha256
self-authentication and its five per-launch re-validations, the per-call
request-digest idempotency collision machine, the legacy Content-Length stdio
framing (no real client ever used it), client-side re-verification of
server-echoed identities on the loopback, and the separate
`mcp_protocol_session` module (merged into the child).
