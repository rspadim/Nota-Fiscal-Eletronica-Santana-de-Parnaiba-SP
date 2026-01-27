"""
Configuração centralizada de logging
Console com data/hora + arquivo de log por dia
"""

import os
import builtins
from datetime import datetime


class PrintAndLog:
    """Substitui print() padrão: mostra com data/hora + salva em log"""

    def __init__(self, nome: str = "nfse"):
        self.nome = nome
        self.pasta_logs = os.path.join(os.path.dirname(__file__), "..", "logs")
        os.makedirs(self.pasta_logs, exist_ok=True)

    def _obter_arquivo_log(self) -> str:
        """Retorna caminho do arquivo de log do dia (YYYYMMDD.log)"""
        data_hoje = datetime.now().strftime("%Y%m%d")
        return os.path.join(self.pasta_logs, f"{data_hoje}.log")

    def _escrever_arquivo(self, mensagem: str):
        """Escreve mensagem em arquivo de log com data/hora completa"""
        try:
            hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            linha = f"[{hora}] {mensagem}\n"

            with open(self._obter_arquivo_log(), 'a', encoding='utf-8') as f:
                f.write(linha)
        except Exception:
            pass  # Silencioso se não conseguir escrever log

    def __call__(self, *args, **kwargs) -> None:
        """Funciona como print() padrão mas adiciona data/hora e salva em log"""
        # Se não houver argumentos, é só quebra de linha
        if not args:
            builtins.print()
            self._escrever_arquivo("")
            return

        # Converter argumentos para string como print() faz
        sep = kwargs.get('sep', ' ')
        mensagem = sep.join(str(arg) for arg in args)

        # Adicionar data/hora na esquerda
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        mensagem_com_hora = f"[{timestamp}] {mensagem}"

        # Mostrar no console
        builtins.print(mensagem_com_hora, **{k: v for k, v in kwargs.items() if k != 'sep'})

        # Salvar no arquivo (sem a hora para não duplicar)
        self._escrever_arquivo(mensagem)


# Criar instância global
print_and_log = PrintAndLog("nfse")
