#!/usr/bin/env bash
# replay_baseline_suite.sh — panel-regression harness over 4 diverse lemmas.
#
# Replays four recorded public run bundles through the CURRENT checkout with
# tools/panel_audit/replay_audit.py and writes per-turn panels + views under
# OUT_ROOT/<name>/. Byte-diff two runs of this suite (before/after a change,
# or twice on the same code) to prove the agent-facing surface is unchanged
# and deterministic:
#
#   bash tools/panel_audit/replay_baseline_suite.sh /tmp/panels_before
#   # ... apply your change ...
#   bash tools/panel_audit/replay_baseline_suite.sh /tmp/panels_after
#   diff -r /tmp/panels_before /tmp/panels_after \
#        --exclude=_run --exclude='*.log' && echo PANELS UNCHANGED
#
# The six lemmas cover deliberately different panel families:
#   PIR_correct  (PIR.ec)          correctness equiv, clean L4 run, 54 turns
#   cpa_ddh0     (elgamal.ec)      pRHL reduction, call-invariant menus, 14 turns
#   pr_G4        (cramer_shoup.ec) probability/phoare goal, byphoare routes,
#                                  STALLED outcome -> stall/recovery panels, 30 turns
#   schnorr_...  (SchnorrPK.ec)    sigma-protocol pRHL, 49 rejected commits ->
#                                  recover/undo/checkpoint flow, rnd + smt, 68 turns
#   step4_badi   (chacha_poly.ec)  up-to-bad episode reasoning (the latch
#                                  cluster) + rcondt surgery; L1-native intent
#                                  stream (blind commits, no probes), 53 turns
#   CTXT_security (MEE-CBC/RCPA_CMA.ec) clone-heavy .eca project; eager/swap
#                                  loop transforms, security composition, 25 turns
#
# Requires the EasyCrypt opam switch and an unsandboxed shell (why3server
# needs nice()). Each replay gets its own WHY3EC_SOCKET.
#
# IMPORTANT: run BOTH sides of a comparison from equally-clean checkouts
# (e.g. detached-HEAD worktrees). Some route-health suggestions scan the
# target .ec SOURCE on disk, so an uncommitted corpus edit shows up as a
# view diff that has nothing to do with your code change (learned the hard
# way: a dirty chacha_poly.ec flipped a lookup-symbol suggestion).
set -euo pipefail

OUT_ROOT=${1:?usage: replay_baseline_suite.sh OUT_ROOT}
cd "$(dirname "$0")/../.."
PY=${PYTHON:-.venv/bin/python}

run() { # name bundle tree file lemma
  local name=$1 bundle=$2 tree=$3 file=$4 lemma=$5
  echo "[suite] $name ..."
  WHY3EC_SOCKET="/tmp/why3ec_suite_${name}.sock" "$PY" tools/panel_audit/replay_audit.py \
    --bundle "$bundle" --tree "$tree" --file "$file" --lemma "$lemma" \
    --include-dir easycrypt-src/theories \
    --out-dir "$OUT_ROOT/$name" > "$OUT_ROOT/$name.log" 2>&1
  echo "[suite] $name rc=$?"
}

mkdir -p "$OUT_ROOT"
run pir agent_view_runs/PIR_correct/2026-06-10_1742_PIR_correct__b9952510-dirty \
    Tree_0_0 eval/examples/PIR.ec PIR_correct
run ddh agent_view_runs/cpa_ddh0/2026-06-08_1737_cpa_ddh0__c855adb2-dirty \
    Tree_0_0 eval/examples/elgamal.ec cpa_ddh0
run prg4 agent_view_runs/pr_G4/2026-06-03_1122_pr_G4__8a68a61 \
    Tree_0_0 eval/examples/cramer-shoup/cramer_shoup.ec pr_G4
run schnorr agent_view_runs/schnorr_proof_of_knowledge_shvzk/2026-06-09_1149_schnorr_proof_of_knowledge_shvzk__4e14c792-dirty \
    Tree_0_0 eval/examples/SchnorrPK.ec schnorr_proof_of_knowledge_shvzk
run badi agent_view_runs/step4_badi/2026-06-09_1431_step4_badi__45fe210c-dirty \
    Tree_0_0 eval/examples/ChaChaPoly/chacha_poly.ec step4_badi
run ctxt agent_view_runs/CTXT_security/2026-06-10_2135_CTXT_security__685f509d2 \
    Tree_0_0 eval/examples/MEE-CBC/RCPA_CMA.ec CTXT_security
echo "[suite] done -> $OUT_ROOT"
