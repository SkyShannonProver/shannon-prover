# Tree-0.0 · turn 11 · probe_tactic

<!-- session 4b39f4e6-16b1-4e04-89ab-2fdac6da9759 · 2026-06-05T10:50:31.542Z -->

**Intent:** `probe_tactic`  
**Payload:** `byequiv (_: ={glob A} ==> ={DoubleQuery.bad} /\ (!DoubleQuery.bad{2} => ={res})) => //.`

---

Diagnose shows no committed error (the probe was read-only). My recollection is that EasyCrypt's `byequiv` *does* accept this abs-difference upto-bad form (it's the standard switching-lemma endgame), and the manager flagged the failure as possibly a probe-harness hiccup ("failed before EasyCrypt could validate"). Let me re-probe the same byequiv to distinguish a real shape rejection from a transient failure.
