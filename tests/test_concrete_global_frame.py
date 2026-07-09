"""Tests for the concrete-global touched frame extractor (step4_badi ground truth).

The flattened oracle programs below mirror what a speculative `inline*` of the
step4_badi enc/dec oracle obligation produces; the expected frame is the one the
agent reconstructed by hand (run 2026-05-30, turn_020):
  ={UFCMA_l.lbad1, UFCMA.cbad1, Mem.lc, BNR.lenc, BNR.ndec, RO.m, ROout.m, ROF.m}
"""
from __future__ import annotations

import sys
from pathlib import Path

import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.analysis.ec_concrete_global_frame import (  # noqa: E402
    module_write_map, write_map_for_goal)


UNIVERSE = [
    "UFCMA_l.lbad1", "UFCMA.cbad1", "UFCMA.log", "Mem.lc", "Mem.k",
    "BNR.lenc", "BNR.ndec", "UFCMA_li.badi", "UFCMA_li.cbadi", "UFCMA_li.i",
]
# flattened enc+dec oracle body, left (UFCMA_l) — writes + RO map touches
_LEFT = """
  BNR.lenc <- p.`1 :: BNR.lenc;
  BNR.ndec <- BNR.ndec + 1;
  Mem.lc <- c :: Mem.lc;
  t0 <$ dpoly_out;
  RO.m.[x] <- t0;
  ROout.m.[y] <- z;
  ROF.m.[w] <- v;
  if (UFCMA.cbad1 < qenc) {
    UFCMA_l.lbad1 <- UFCMA_l.lbad1 ++ map (fun t => (t0, t)) lt;
    UFCMA.cbad1 <- UFCMA.cbad1 + 1;
  }
"""
# right (UFCMA_li) — same, plus the indexed bad-event state (the relational diff)
_RIGHT = """
  BNR.lenc <- p.`1 :: BNR.lenc;
  BNR.ndec <- BNR.ndec + 1;
  Mem.lc <- c :: Mem.lc;
  t0 <$ dpoly_out;
  RO.m.[x] <- t0;
  ROout.m.[y] <- z;
  ROF.m.[w] <- v;
  if (UFCMA.cbad1 < qenc) {
    if (size UFCMA_l.lbad1 <= UFCMA_li.i) {
      t1 <$ dpoly_out;
      if (UFCMA_li.cbadi < 1) {
        UFCMA_li.badi <- UFCMA_li.badi || t1 = ti;
        UFCMA_li.cbadi <- UFCMA_li.cbadi + 1;
      }
    }
    UFCMA_l.lbad1 <- UFCMA_l.lbad1 ++ map (fun t => (t0, t)) lt;
    UFCMA.cbad1 <- UFCMA.cbad1 + 1;
  }
"""


# --- static write-map (source-scan) -----------------------------------------
#
# Mirrors step4_badi's structure: UFCMA owns cbad1/log; UFCMA_l owns lbad1 and
# writes it bare; UFCMA_li owns badi/cbadi/i, writes its own bad-state AND the
# shared UFCMA_l.lbad1; BNR owns lenc/ndec. `Mem.lc` is read but written only in
# a cloned theory (absent from these bodies). `i`/`ns` appear as proc-locals too.
_SRC = """
local module UFCMA (ROin:RO) = {
  var cbad1 : int
  var log   : (nonce, stuff) fmap
  proc f() = { cbad1 <- 0; }
}.
local module UFCMA_l = {
  var lbad1 : (tag * tag) list
  proc set_bad1(lt) = {
    var t;
    t <$ dpoly_out;
    if (UFCMA.cbad1 < qenc) {
      lbad1 <- lbad1 ++ map (fun t' => (t, t')) lt;
      UFCMA.cbad1 <- UFCMA.cbad1 + 1;
      UFCMA.log.[n] <- v;
    }
  }
}.
local module UFCMA_li = {
  var badi  : bool
  var cbadi : int
  var i     : int
  proc set_bad1i(ti) = {
    var t2;
    t2 <$ dpoly_out;
    badi  <- badi || t2 = ti;
    cbadi <- cbadi + 1;
    return t2;
  }
  proc set_bad1(lt) = {
    var t, ns;
    ns <- 0;
    t <$ dpoly_out;
    if (size UFCMA_l.lbad1 <= i) { t <@ set_bad1i(nth witness lt (i - size UFCMA_l.lbad1)); }
    UFCMA_l.lbad1 <- UFCMA_l.lbad1 ++ map (fun t' => (t, t')) lt;
    UFCMA.cbad1 <- UFCMA.cbad1 + 1;
    UFCMA.log.[n] <- v;
  }
  proc init(i0) = { cbadi <- 0; badi <- false; i <- i0; UFCMA_l.lbad1 <- []; }
}.
module BNR (O:CCA_Oracles) = {
  var lenc : nonce list
  var ndec : int
  proc enc(p) = { var c; c <- witness; lenc <- p.`1 :: lenc; }
  proc dec(c) = { ndec <- ndec + 1; }
}.
"""


def test_write_map_resolves_bare_own_var_and_shared_writes() -> None:
    wm = module_write_map([_SRC])
    bf = wm["by_field"]
    # bare `lbad1 <- ...` inside UFCMA_l resolves to UFCMA_l.lbad1; UFCMA_li writes
    # it too (the cross-module shared mutation the agent spends 400s confirming).
    assert set(bf.get("UFCMA_l.lbad1", [])) == {"UFCMA_l", "UFCMA_li"}
    # badi/cbadi/i are UFCMA_li's own state, written bare -> resolved to UFCMA_li.*
    assert bf.get("UFCMA_li.badi") == ["UFCMA_li"]
    assert bf.get("UFCMA_li.cbadi") == ["UFCMA_li"]
    assert bf.get("UFCMA_li.i") == ["UFCMA_li"]
    # qualified writes captured
    assert "UFCMA_l" in bf.get("UFCMA.cbad1", []) and "UFCMA_li" in bf.get("UFCMA.cbad1", [])
    assert "UFCMA_li" in bf.get("UFCMA.log", [])


def test_write_map_excludes_proc_locals() -> None:
    wm = module_write_map([_SRC])
    bf = wm["by_field"]
    # `ns`, `t`, `t2`, `c` are proc-locals (shadow / not module state) -> never framed
    for local in ("UFCMA_li.ns", "UFCMA_li.t", "UFCMA_li.t2", "BNR.c"):
        assert local not in bf
    # owners table must not claim a proc-local as state
    assert "ns" not in wm["owners"]
    assert "t2" not in wm["owners"]


def test_write_map_for_goal_flags_clone_owned_as_preserved() -> None:
    g = write_map_for_goal(
        [_SRC],
        field_universe=["UFCMA_l.lbad1", "UFCMA.cbad1", "Mem.lc", "UFCMA_li.badi"],
        focus_modules=["UFCMA_l", "UFCMA_li"],
    )
    by_field = {row["field"]: row for row in g["fields"]}
    # Mem.lc never written in these bodies -> reported preserved/read-only (the
    # exact answer to "where does Mem.lc get updated"), not omitted.
    assert by_field["Mem.lc"]["written_by"] == []
    assert "read-only" in by_field["Mem.lc"]["status"]
    assert by_field["UFCMA_l.lbad1"]["status"] == "mutated"
    # divergent module write-sets expose the badi/cbadi/i diff mechanically
    dmw = {r["module"]: set(r["writes"]) for r in g["divergent_module_writes"]}
    diff = dmw["UFCMA_li"] - dmw["UFCMA_l"]
    assert {"UFCMA_li.badi", "UFCMA_li.cbadi", "UFCMA_li.i"} <= diff


def test_write_map_for_goal_drops_submodule_refs() -> None:
    # `UFCMA_l.O` is the oracle MODULE passed at the frontier (uppercase last
    # segment), not state — it must not appear as a "clone-owned field".
    g = write_map_for_goal(
        [_SRC],
        field_universe=["UFCMA_l.lbad1", "UFCMA_l.O", "UFCMA_li.O"],
        focus_modules=["UFCMA_l", "UFCMA_li"],
    )
    surfaced = {row["field"] for row in g["fields"]}
    assert "UFCMA_l.O" not in surfaced and "UFCMA_li.O" not in surfaced
    assert "UFCMA_l.lbad1" in surfaced


if __name__ == "__main__":
    test_frame_matches_hand_reconstructed_set()
    test_asymmetric_right_only_state_excluded_from_frame()
    test_does_not_over_include_untouched_universe_fields()
    test_ro_map_candidates_from_aliases()
    test_write_map_resolves_bare_own_var_and_shared_writes()
    test_write_map_excludes_proc_locals()
    test_write_map_for_goal_flags_clone_owned_as_preserved()
    test_write_map_for_goal_drops_submodule_refs()
    print("PASS test_concrete_global_frame")
