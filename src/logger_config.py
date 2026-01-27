"""
Logging simples: print + salva em arquivo por dia
Lê caminho dos logs do config.json (ou padrão: logs/)
"""

import os
import json
import builtins
from datetime import datetime

# Guardar referência original do print ANTES de modificar
_print_original = builtins.print

# Cache da pasta de logs
_pasta_logs_cache = None


def _obter_pasta_logs():
    """Obtém caminho da pasta de logs do config.json ou usa padrão"""
    global _pasta_logs_cache

    if _pasta_logs_cache:
        return _pasta_logs_cache

    # Tentar ler do config.json
    try:
        caminho_config = os.path.join(os.path.dirname(__file__), "config.json")
        with open(caminho_config, 'r', encoding='utf-8') as f:
            config = json.load(f)
            pasta_logs = config.get("nfse", {}).get("caminho_logs", "logs")
    except Exception:
        # Fallback: usar pasta padrão
        pasta_logs = "logs"

    # Se é caminho relativo, tornar relativo à raiz do projeto
    if not os.path.isabs(pasta_logs):
        pasta_logs = os.path.join(os.path.dirname(__file__), "..", pasta_logs)

    # Normalizar caminho
    pasta_logs = os.path.abspath(pasta_logs)

    # Criar pasta se não existir
    os.makedirs(pasta_logs, exist_ok=True)

    _pasta_logs_cache = pasta_logs
    return pasta_logs


def print_and_log(*args, **kwargs):
    """Print normal + salva em arquivo de log (YYYYMMDD.log)"""
    # Print normal no console usando a referência original
    _print_original(*args, **kwargs)

    # Obter caminho da pasta de logs
    pasta_logs = _obter_pasta_logs()

    # Arquivo de log por dia
    data_hoje = datetime.now().strftime("%Y%m%d")
    arquivo_log = os.path.join(pasta_logs, f"{data_hoje}.log")

    # Gravar mensagem em arquivo
    try:
        hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sep = kwargs.get('sep', ' ')
        mensagem = sep.join(str(arg) for arg in args)
        linha = f"[{hora}] {mensagem}\n"

        with open(arquivo_log, 'a', encoding='utf-8') as f:
            f.write(linha)
    except Exception:
        pass  # Silencioso se não conseguir escrever
