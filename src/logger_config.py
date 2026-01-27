"""
Logging simples: print + salva em arquivo por dia
"""

import os
import builtins
from datetime import datetime


def print_and_log(*args, **kwargs):
    """Print normal + salva em arquivo de log (YYYYMMDD.log)"""
    # Print normal no console
    builtins.print(*args, **kwargs)

    # Preparar pasta de logs
    pasta_logs = os.path.join(os.path.dirname(__file__), "..", "logs")
    os.makedirs(pasta_logs, exist_ok=True)

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
