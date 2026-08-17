---
description: Prove an EasyCrypt lemma with Shannon Prover
argument-hint: <LemmaName>
allowed-tools: Bash, Grep, Glob, Read, Write, Edit
---

Read `.agents/skills/prove/SKILL.md` completely and follow it as the canonical
Shannon Prover launcher workflow. Use `$ARGUMENTS` as its invocation text and
bind the proof-node backend to `claude`; this command never launches Codex.
Use the ordinary in-place proof workflow: do not add `--eval-mode`, create an
eval suite, copy the source project, or strip the target proof.

Do not maintain or invent a second Claude-specific proof workflow here. If the
canonical skill is missing or unreadable, report that repository error instead
of falling back to a duplicated procedure.
