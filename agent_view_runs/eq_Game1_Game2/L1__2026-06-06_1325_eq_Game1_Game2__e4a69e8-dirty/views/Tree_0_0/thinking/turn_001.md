# Tree-0.0 · turn 1 · commit_tactic

<!-- session 4f351901-44e8-41bc-99e4-ea22ad2aa3a3 · 2026-06-06T20:29:48.268Z -->

**Intent:** `commit_tactic`  
**Payload:** `proc.`

---

I've read the goal and the source. Let me understand the proof obligation:

- `Game1.main ~ Game2.main : ={glob A} ==> ={glob Log, res} /\ Game1.r{1} = Game2.r{2}`
- The only difference: Game1 sets `c <- (f pk r, h +^ (b?m0:m1))`, Game2 sets `c <- (f pk r, h)`, where `h <$ dptxt` (full/uniform). Classic one-time-pad: change of variable `h ↦ h +^ x` on the right.

Let me get advice before committing the proof.

Advice confirms the plan with one key fix: split at `seq 4 4` and handle `r` with explicit `rnd`. Let me start.
