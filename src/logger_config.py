"""Helpers para espelhar print/input no console e em arquivo de log."""

from __future__ import annotations

import builtins
from datetime import datetime
from pathlib import Path
from threading import Lock

_original_print = builtins.print
_original_input = builtins.input
_lock = Lock()


def _log_path() -> Path:
    base_dir = Path(__file__).resolve().parent.parent
    logs_dir = base_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir / f"execucao_{datetime.now():%Y%m%d}.log"


def _append_log(message: str) -> None:
    with _lock:
        with _log_path().open("a", encoding="utf-8") as f:
            f.write(message + "\n")


def print_and_log(*args, **kwargs):
    text = " ".join(str(arg) for arg in args)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _append_log(f"[{timestamp}] {text}")
    return _original_print(*args, **kwargs)


def input_and_log(prompt: str = "") -> str:
    resposta = _original_input(prompt)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _append_log(f"[{timestamp}] INPUT prompt={prompt!r} resposta={resposta!r}")
    return resposta
