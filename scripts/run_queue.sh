#!/usr/bin/env bash
# run_queue.sh — strictly-sequential prover run queue for ONE worktree.
#
# Replaces the hand-rolled "chain launcher" scripts (night_launcher_*.sh,
# mee_hard_launcher_*.sh, d_lane_chain.sh). Those waited on `pgrep -f PATTERN`,
# which deadlocks when several launchers poll in lock-step and match each
# other's pgrep cmdlines (observed 2026-06-11). Here, waiting IS sequential
# execution in a single shell — no pattern-based process polling exists.
#
# Usage:
#   nohup bash scripts/run_queue.sh [options] QUEUE_FILE &
#
# QUEUE_FILE: one bash command per line; blank lines and '#' comments ignored.
#   Per-step env overrides go inline on the line, e.g.:
#     WHY3EC_SOCKET=/tmp/why3ec_a.sock uv run python -m eval_suite.run --suite tmp/a.json > tmp/a.log 2>&1
#     SHANNON_DISABLE_PROBE=1 WHY3EC_SOCKET=/tmp/why3ec_b.sock uv run python -m workflow.orchestrator ... > tmp/b.log 2>&1
#   Give every EasyCrypt-running step its own WHY3EC_SOCKET — parallel lanes
#   sharing /tmp/why3ec.sock is a known confound. Redirect each step's bulk
#   output to its own log; anything not redirected goes to the queue .out log.
#   The environment is inherited: run `eval "$(opam env --switch=easycrypt)"`
#   before launching, or put it on the queue line.
#
# Options:
#   --worktree DIR      cd here before everything (default: current dir).
#                       Run ONE queue per worktree: .ec_session_prover_tree_*
#                       dirs are per-worktree singletons.
#   --log FILE          progress log (default: QUEUE_FILE.out). Timestamped
#                       [run_queue] line per step start/exit.
#   --wait-pid PID      before step 1, wait for this PRE-EXISTING process to
#                       exit (poll kill -0; never a pgrep pattern). Only for
#                       runs the queue did not start itself.
#   --wait-pidfile F    like --wait-pid but read the PID from file F.
#   --poll SECS         PID-wait poll interval (default 30).
#   --settle SECS       sleep between steps to let the exited run's children
#                       wind down before the session wipe (default 0; the old
#                       launchers used 20-30).
#   --no-wipe           skip the stale .ec_session_prover_tree_* wipe that
#                       otherwise runs before every step.
#   --stop-on-error     abort the queue on the first nonzero step exit
#                       (default: log the rc and continue).
#
# Exit status: 0 if every step exited 0, else 1 (or the failing step's rc
# under --stop-on-error).
#
# The wipe uses `find -exec rm -rf`, which is a no-op on zero matches — unlike
# zsh `rm -rf .ec_session_prover_tree_*`, which aborts an && chain when the
# glob matches nothing.
#
# SIGHUP is ignored so the queue survives terminal close even without nohup
# (children that reset their own handlers may still need nohup).
#
# Tested by tests/test_run_queue.py. Documented in TESTING.md.

set -u

# Print the comment header above (everything up to the first non-# line).
usage() {
  awk 'NR > 1 { if ($0 !~ /^#/) exit; sub(/^# ?/, ""); print }' "$0"
}

die() {
  echo "run_queue: $*" >&2
  exit 2
}

WORKTREE=$(pwd)
LOG=""
WAIT_PID=""
POLL=30
SETTLE=0
WIPE=1
STOP_ON_ERROR=0

while [ $# -gt 0 ]; do
  case "$1" in
    --worktree)      [ $# -ge 2 ] || die "--worktree needs a value"; WORKTREE=$2; shift 2 ;;
    --log)           [ $# -ge 2 ] || die "--log needs a value"; LOG=$2; shift 2 ;;
    --wait-pid)      [ $# -ge 2 ] || die "--wait-pid needs a value"; WAIT_PID=$2; shift 2 ;;
    --wait-pidfile)  [ $# -ge 2 ] || die "--wait-pidfile needs a value"
                     [ -f "$2" ] || die "pidfile not found: $2"
                     WAIT_PID=$(tr -d '[:space:]' < "$2"); shift 2 ;;
    --poll)          [ $# -ge 2 ] || die "--poll needs a value"; POLL=$2; shift 2 ;;
    --settle)        [ $# -ge 2 ] || die "--settle needs a value"; SETTLE=$2; shift 2 ;;
    --no-wipe)       WIPE=0; shift ;;
    --stop-on-error) STOP_ON_ERROR=1; shift ;;
    -h|--help)       usage; exit 0 ;;
    --)              shift; break ;;
    -*)              die "unknown option: $1" ;;
    *)               break ;;
  esac
done

[ $# -eq 1 ] || { usage >&2; die "expected exactly one QUEUE_FILE"; }
QUEUE_FILE=$1
[ -f "$QUEUE_FILE" ] || die "queue file not found: $QUEUE_FILE"
case "$WAIT_PID" in *[!0-9]*) die "--wait-pid/--wait-pidfile must be numeric, got: $WAIT_PID" ;; esac

[ -n "$LOG" ] || LOG="${QUEUE_FILE}.out"

cd "$WORKTREE" || die "cannot cd to worktree: $WORKTREE"
trap '' HUP

log() {
  printf '[run_queue] %s %s\n' "$(date '+%Y-%m-%dT%H:%M:%S')" "$*" >> "$LOG"
}

wipe_sessions() {
  find "$WORKTREE" -maxdepth 1 -name '.ec_session_prover_tree_*' -exec rm -rf {} +
}

# Read the queue up front so edits to the file mid-run don't change the plan.
STEPS=()
while IFS= read -r line || [ -n "$line" ]; do
  case "$line" in
    ''|'#'*) continue ;;
  esac
  STEPS+=("$line")
done < "$QUEUE_FILE"

N=${#STEPS[@]}
[ "$N" -gt 0 ] || die "queue file has no runnable lines: $QUEUE_FILE"

log "queue start: $N step(s) from $QUEUE_FILE in $WORKTREE (pid $$)"

if [ -n "$WAIT_PID" ]; then
  log "waiting for pre-existing pid $WAIT_PID (poll ${POLL}s)"
  while kill -0 "$WAIT_PID" 2>/dev/null; do
    sleep "$POLL"
  done
  log "pid $WAIT_PID has exited"
fi

OVERALL_RC=0
I=0
for CMD in "${STEPS[@]}"; do
  I=$((I + 1))
  if [ "$I" -gt 1 ] && [ "$SETTLE" -gt 0 ]; then
    sleep "$SETTLE"
  fi
  if [ "$WIPE" -eq 1 ]; then
    wipe_sessions
    log "step $I/$N: wiped stale .ec_session_prover_tree_* dirs"
  fi
  log "step $I/$N START: $CMD"
  bash -c "$CMD" >> "$LOG" 2>&1
  RC=$?
  log "step $I/$N EXIT rc=$RC"
  if [ "$RC" -ne 0 ]; then
    OVERALL_RC=1
    if [ "$STOP_ON_ERROR" -eq 1 ]; then
      log "queue ABORTED at step $I/$N (--stop-on-error)"
      exit "$RC"
    fi
  fi
done

log "queue done: overall_rc=$OVERALL_RC"
exit "$OVERALL_RC"
