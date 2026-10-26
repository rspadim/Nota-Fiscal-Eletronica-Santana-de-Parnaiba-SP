"""Helpers para espelhar print/input no console e em arquivo de log.

Grava um arquivo por dia (`logs/execucao_AAAAMMDD.log`) e remove os arquivos
mais antigos que a retencao configurada (30 dias por padrao).
"""

from __future__ import annotations

import builtins
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock

_original_print = builtins.print
_original_input = builtins.input
_lock = Lock()

RETENCAO_DIAS = 30
_PADRAO_LOG = re.compile(r"^execucao_(\d{8})\.log$")

_limpeza_feita = False
_pasta_configurada: Path | None = None
_retencao_dias = RETENCAO_DIAS


def configurar(pasta: str | None = None, retencao_dias: int | None = None) -> None:
    """Aplica a configuracao de log vinda do config.json."""
    global _pasta_configurada, _retencao_dias, _limpeza_feita

    if pasta:
        _pasta_configurada = Path(pasta).expanduser().resolve()
    if retencao_dias is not None:
        try:
            _retencao_dias = max(1, int(retencao_dias))
        except (TypeError, ValueError):
            _retencao_dias = RETENCAO_DIAS
    _limpeza_feita = False


def _base_dir() -> Path:
    """
    Pasta base dos logs.

    Ordem: pasta configurada no config.json > junto do .exe (se gravavel) >
    ~/.local/state/nfse-santana (Linux, quando /opt e somente leitura) >
    raiz do projeto (execucao via codigo-fonte).
    """
    if getattr(sys, "frozen", False):
        if os.name == "nt":
            # Windows: ao lado do .exe (instalado no perfil do usuario)
            return Path(sys.executable).resolve().parent
        # Linux: por usuario, mesmo que /opt esteja gravavel
        return Path(Path.home(), ".local", "state", "nfse-santana")
    return Path(__file__).resolve().parent.parent


def _dir_logs() -> Path:
    logs_dir = _pasta_configurada or (_base_dir() / "logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


def _log_path(quando: datetime | None = None, pasta: Path | None = None) -> Path:
    """Caminho do log do dia (um arquivo por dia)."""
    quando = quando or datetime.now()
    destino = Path(pasta) if pasta else _dir_logs()
    destino.mkdir(parents=True, exist_ok=True)
    return destino / f"execucao_{quando:%Y%m%d}.log"


def limpar_logs_antigos(
    pasta: Path | None = None,
    dias: int | None = None,
    agora: datetime | None = None,
) -> int:
    """
    Remove logs mais antigos que `dias`, pela data no nome do arquivo.

    Returns:
        Quantidade de arquivos removidos.
    """
    destino = Path(pasta) if pasta else _dir_logs()
    if not destino.is_dir():
        return 0

    agora = agora or datetime.now()
    limite = (agora - timedelta(days=dias or _retencao_dias)).date()
    removidos = 0

    for arquivo in destino.glob("execucao_*.log"):
        encontrado = _PADRAO_LOG.match(arquivo.name)
        if not encontrado:
            continue
        try:
            data = datetime.strptime(encontrado.group(1), "%Y%m%d").date()
        except ValueError:
            continue
        if data < limite:
            try:
                arquivo.unlink()
                removidos += 1
            except OSError:
                # arquivo aberto em outro processo: tenta na proxima execucao
                pass

    return removidos


def _append_log(message: str) -> None:
    global _limpeza_feita

    with _lock:
        if not _limpeza_feita:
            limpar_logs_antigos()
            _limpeza_feita = True
        with _log_path().open("a", encoding="utf-8") as arquivo:
            arquivo.write(message + "\n")


def print_and_log(*args, **kwargs):
    text = " ".join(str(arg) for arg in args)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _append_log(f"[{timestamp}] {text}")
    return _original_print(*args, **kwargs)


def input_and_log(prompt: str = "") -> str:
    """
    input() com log. Se a entrada terminar (Ctrl+Z/Ctrl+D, pipe vazio ou
    duplo clique no .exe sem console), devolve '' em vez de derrubar o programa.
    """
    try:
        resposta = _original_input(prompt)
    except (EOFError, KeyboardInterrupt):
        _append_log(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] INPUT encerrado pelo usuario")
        # sem entrada (pipe vazio, Ctrl+Z ou janela fechada): encerra limpo,
        # sem traceback e sem entrar em loop no menu
        raise SystemExit(0)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _append_log(f"[{timestamp}] INPUT prompt={prompt!r} resposta={resposta!r}")
    return resposta
