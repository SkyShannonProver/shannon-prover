# Tree-0.0 · turn 46 · commit_tactic

<!-- session a8006092-a9db-4441-9330-0fc2cd05aaf8 · 2026-06-10T21:30:26.375Z -->

**Intent:** `commit_tactic`  
**Payload:** `move: hdec; rewrite /dec /get /genpoly1305 /=; smt().`

---

Membership done. The remaining equation is exactly the decryption-success condition from `hdec`. Let me unfold `dec`/`get`/`genpoly1305` in `hdec` and discharge via `smt`.
