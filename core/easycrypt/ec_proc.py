"""Single owner of the ``easycrypt -emacs`` command line + interactive spawn.

Every EC subprocess used to hand-build ``["easycrypt", "-emacs", ...]`` with its
own ``-I`` / ``-server`` wiring. There were five byte-identical (modulo the why3
socket source) copies across ``ec_daemon`` (persistent + two ephemeral),
``ec_warm_prober`` and ``session_runtime`` — so a change to the why3 wiring or a
new launch flag had to be made in five places, and they drifted (audit §8 #8,
and the documented shared-``/tmp/why3ec.sock`` confound). Centralizing the argv
here keeps the include flags + why3 wiring identical everywhere and gives one
place to evolve how EasyCrypt is launched.

Pure stdlib + no sibling imports, so it loads both as ``core.easycrypt.ec_proc``
(package import) and as a bare ``ec_proc`` (when ``ec_daemon.py`` runs as a
script with ``core/easycrypt`` on ``sys.path``).

The legacy ``repl.py`` pexpect lineage is intentionally NOT routed through here:
it is a deprecated, isolated path with its own (abspath) include handling used
in three places, and it spawns via ``pexpect`` rather than ``subprocess``.
"""

from __future__ import annotations

import os
import subprocess
from typing import Iterable, Optional, Sequence

DEFAULT_WHY3_SOCKET = "/tmp/why3ec.sock"


def why3_socket_from_env() -> str:
    """The why3server socket for this run.

    ``prover.run`` sets a per-run ``WHY3EC_SOCKET`` (so concurrent eval arms do
    not share one server — the L1-vs-L4 timing confound); absent that, the
    historical default.
    """
    return os.environ.get("WHY3EC_SOCKET", DEFAULT_WHY3_SOCKET)


def emacs_command(
    include_dirs: Optional[Iterable[str]] = None,
    why3_socket: Optional[str] = None,
    *,
    extra_args: Sequence[str] = (),
) -> list[str]:
    """Canonical ``easycrypt -emacs`` argv.

    Adds ``-server <socket>`` iff ``why3_socket`` is given AND exists on disk —
    matching EasyCrypt's connect-or-self-start behaviour, so a stale/absent
    socket never turns into a hard ``-server`` connect failure — then ``-I
    <dir>`` per include dir, then any ``extra_args``.
    """
    cmd = ["easycrypt", "-emacs"]
    if why3_socket and os.path.exists(why3_socket):
        cmd.extend(["-server", why3_socket])
    for d in include_dirs or ():
        cmd.extend(["-I", str(d)])
    cmd.extend(extra_args)
    return cmd


def spawn_emacs_pipe(
    include_dirs: Optional[Iterable[str]] = None,
    why3_socket: Optional[str] = None,
    *,
    env: Optional[dict] = None,
) -> subprocess.Popen:
    """Spawn an interactive ``easycrypt -emacs`` over stdin/stdout PIPEs.

    The shape the daemon (persistent + ephemeral) and the warm prober all share:
    binary stdio, stderr folded into stdout, unbuffered. ``env`` should carry the
    opam switch (see ``ec_env.get_ec_env``).
    """
    return subprocess.Popen(
        emacs_command(include_dirs, why3_socket),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        bufsize=0,
    )
