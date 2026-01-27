"""
Script principal para emissão de NFS-e
Lê configuração de config.json e gerencia o envio de NFS-e
"""

import json
import os
import sys
import time
import shutil
import logging
from datetime import datetime
from pathlib import Path
from nfse_simples import ClienteNFSeSimples

# Configurar logging
def _configurar_logging():
    """Configura logging com arquivo por dia"""
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
            pasta_logs = config.get("nfse", {}).get("caminho_logs", "./logs")
    except:
        pasta_logs = "./logs"

    if not os.path.isabs(pasta_logs):
        pasta_logs = os.path.abspath(pasta_logs)

    os.makedirs(pasta_logs, exist_ok=True)

    logger = logging.getLogger('nfse')
    logger.setLevel(logging.DEBUG)

    if logger.handlers:
        return logger

    # Console
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter('[%(asctime)s] [%(levelname)-8s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
    logger.addHandler(console)

    # Arquivo por dia
    data_hoje = datetime.now().strftime("%Y%m%d")
    arquivo = logging.FileHandler(os.path.join(pasta_logs, f'{data_hoje}.log'), encoding='utf-8')
    arquivo.setLevel(logging.DEBUG)
    arquivo.setFormatter(logging.Formatter('[%(asctime)s] [%(levelname)-8s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
    logger.addHandler(arquivo)

    return logger

logger = _configurar_logging()

# Wrapper para input que também loga
_input_original = input
def input_log(prompt=''):
    """Input com logging automático"""
    if prompt:
        logger.info(prompt.rstrip())
    resposta = _input_original(prompt)
    logger.info(f"[INPUT] {resposta}")
    return resposta
input = input_log


class GerenciadorNFSe:
    """Gerenciador de emissão e consulta de NFS-e"""

    def __init__(self, arquivo_config: str = "config.json"):
        """Inicializa o gerenciador com arquivo de configuração"""
        self.config = self._carregar_config(arquivo_config)
        self.cliente = None
        self._inicializar_cliente()

    def _carregar_config(self, arquivo_config: str) -> dict:
        """Carrega configurações do arquivo JSON"""
        try:
            with open(arquivo_config, 'r', encoding='utf-8') as f:
                config = json.load(f)
                logger.info(f"[OK] Configuração carregada de {arquivo_config}")
                return config
        except FileNotFoundError:
            logger.error(f" Arquivo de configuração não encontrado: {arquivo_config}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            logger.error(f" Erro ao ler JSON: {e}")
            sys.exit(1)

    def _inicializar_cliente(self):
        """Inicializa o cliente NFS-e com as configurações"""
        cert_config = self.config.get("certificado", {})
        certificado = cert_config.get("caminho_cert")
        chave = cert_config.get("caminho_chave")

        if not certificado:
            logger.info("[ERRO] Caminho do certificado não configurado em config.json")
            sys.exit(1)

        if not os.path.exists(certificado):
            logger.error(f" Certificado não encontrado: {certificado}")
            sys.exit(1)

        nfse_config = self.config.get("nfse", {})
        self.cliente = ClienteNFSeSimples(
            ambiente=self.config.get("ambiente", "homologacao"),
            certificado_path=certificado,
            chave_privada_path=chave if chave and os.path.exists(chave) else None,
            caminho_xml_enviados=nfse_config.get("caminho_xml_enviados", "./nfse_enviadas"),
            salvar_xml_assinado=nfse_config.get("salvar_xml_assinado", True),
            url_homologacao=self.config.get("url_homologacao"),
            url_producao=self.config.get("url_producao")
        )

        logger.info(f"[OK] Cliente configurado para {self.config.get('ambiente', 'homologacao')}")

    def emitir_nfse(self, arquivo_xml: str) -> bool:
        """
        Emite uma NFS-e

        Args:
            arquivo_xml: Caminho do arquivo XML da DPS

        Returns:
            True se sucesso, False caso contrário
        """
        logger.info("\n" + "="*60)
        logger.info("EMISSÃO DE NFS-e")
        logger.info("="*60)

        if not os.path.exists(arquivo_xml):
            logger.error(f" Arquivo não encontrado: {arquivo_xml}")
            return False

        logger.info(f"Arquivo: {arquivo_xml}")

        sucesso, resposta = self.cliente.emitir_nfse_xml(arquivo_xml)

        if sucesso:
            logger.info("\n[OK] NFS-e emitida com SUCESSO!")

            if "numero_nfse" in resposta:
                logger.info(f"  Número da NFS-e: {resposta['numero_nfse']}")

            if "chave_acesso" in resposta:
                logger.info(f"  Chave de Acesso: {resposta['chave_acesso']}")

            # Salvar XML da resposta
            if resposta.get("xml") and self.config.get("nfse", {}).get("salvar_xml_resposta"):
                pasta_saida = self.config.get("nfse", {}).get("caminho_xml_saida", "./nfse_emitidas")
                os.makedirs(pasta_saida, exist_ok=True)

                # Gerar timestamp com nanosegundos para evitar duplicatas mesmo em reenvios
                agora = datetime.now()
                timestamp = agora.strftime("%Y%m%d_%H%M%S")
                nanosegundos = time.time_ns() % 1_000_000_000
                timestamp_completo = f"{timestamp}_{nanosegundos:09d}"

                # Prioridade: ID completo > número DFS > número NFS-e > indefinido
                # Sempre com timestamp_completo para evitar sobrescrita
                id_nfse = resposta.get('id_nfse')
                numero_dfs = resposta.get('numero_dfs')
                numero_nfse = resposta.get('numero_nfse')

                if id_nfse:
                    nome_arquivo = os.path.join(pasta_saida, f"nfse_{id_nfse}_{timestamp_completo}.xml")
                elif numero_dfs:
                    nome_arquivo = os.path.join(pasta_saida, f"nfse_dfs{numero_dfs}_{timestamp_completo}.xml")
                elif numero_nfse:
                    nome_arquivo = os.path.join(pasta_saida, f"nfse_{numero_nfse}_{timestamp_completo}.xml")
                else:
                    nome_arquivo = os.path.join(pasta_saida, f"nfse_indefinido_{timestamp_completo}.xml")

                self.cliente.salvar_resposta_xml(resposta["xml"], nome_arquivo)

            return True
        else:
            logger.info("\n[ERRO] Erro na emissão:")
            erro = resposta.get("erro", resposta)
            if isinstance(erro, dict):
                for chave, valor in erro.items():
                    logger.info(f"  {chave}: {valor}")
            else:
                logger.info(f"  {erro}")
            return False

    def consultar_nfse(self, chave_acesso: str) -> bool:
        """
        Consulta uma NFS-e

        Args:
            chave_acesso: Chave de acesso da NFS-e

        Returns:
            True se sucesso, False caso contrário
        """
        logger.info("\n" + "="*60)
        logger.info("CONSULTA DE NFS-e")
        logger.info("="*60)
        logger.info(f"Chave de Acesso: {chave_acesso}")

        sucesso, resposta = self.cliente.consultar_nfse(chave_acesso)

        if sucesso:
            logger.info("\n[OK] NFS-e consultada com SUCESSO!")

            if resposta.get("xml"):
                # Salvar XML
                pasta_saida = self.config.get("nfse", {}).get("caminho_xml_saida", "./nfse_emitidas")
                os.makedirs(pasta_saida, exist_ok=True)

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                nome_arquivo = os.path.join(pasta_saida, f"nfse_consulta_{chave_acesso.replace(' ', '')}_{timestamp}.xml")

                self.cliente.salvar_resposta_xml(resposta["xml"], nome_arquivo)

            return True
        else:
            logger.info("\n[ERRO] Erro na consulta:")
            logger.info(f"  {resposta.get('erro')}")
            return False

    def cancelar_nfse(self, chave_acesso: str, arquivo_evento: str) -> bool:
        """
        Cancela uma NFS-e

        Args:
            chave_acesso: Chave de acesso da NFS-e
            arquivo_evento: Caminho do arquivo XML do evento de cancelamento

        Returns:
            True se sucesso, False caso contrário
        """
        logger.info("\n" + "="*60)
        logger.info("CANCELAMENTO DE NFS-e")
        logger.info("="*60)
        logger.info(f"Chave de Acesso: {chave_acesso}")
        logger.info(f"Arquivo do Evento: {arquivo_evento}")

        if not os.path.exists(arquivo_evento):
            logger.error(f" Arquivo de evento não encontrado: {arquivo_evento}")
            return False

        sucesso, resposta = self.cliente.cancelar_nfse(chave_acesso, arquivo_evento)

        if sucesso:
            logger.info("\n[OK] NFS-e cancelada com SUCESSO!")
            return True
        else:
            logger.info("\n[ERRO] Erro no cancelamento:")
            logger.info(f"  {resposta.get('erro')}")
            return False

    def emitir_lote(self, pasta_xml: str = None) -> None:
        """
        Emite NFS-e em lote (todos os XMLs de uma pasta)
        Move arquivos enviados com sucesso para pasta 'enviados'
        Move arquivos com erro para pasta 'erros'

        Args:
            pasta_xml: Caminho da pasta com XMLs (usa config se não informado)
        """
        if not pasta_xml:
            pasta_xml = self.config.get("nfse", {}).get("caminho_xml_entrada", ".")

        if not os.path.isdir(pasta_xml):
            logger.error(f" Pasta não encontrada: {pasta_xml}")
            return

        # Criar subpastas para organizar arquivos
        pasta_enviados = os.path.join(pasta_xml, "enviados")
        pasta_erros = os.path.join(pasta_xml, "erros")
        os.makedirs(pasta_enviados, exist_ok=True)
        os.makedirs(pasta_erros, exist_ok=True)

        arquivos_xml = list(Path(pasta_xml).glob("*.xml"))

        if not arquivos_xml:
            logger.error(f" Nenhum arquivo XML encontrado em: {pasta_xml}")
            return

        logger.info(f"\n{'='*60}")
        logger.info(f"EMISSÃO EM LOTE")
        logger.info(f"{'='*60}")
        logger.info(f"Total de arquivos: {len(arquivos_xml)}\n")

        sucesso_count = 0
        erro_count = 0

        for i, arquivo in enumerate(arquivos_xml, 1):
            logger.info(f"[{i}/{len(arquivos_xml)}] Processando: {arquivo.name}")

            if self.emitir_nfse(str(arquivo)):
                sucesso_count += 1
                # Mover arquivo para pasta 'enviados'
                try:
                    destino_enviados = os.path.join(pasta_enviados, arquivo.name)
                    shutil.move(str(arquivo), destino_enviados)
                    logger.info(f"  → Movido para: enviados/{arquivo.name}")
                except Exception as e:
                    logger.info(f"  [AVISO] Não foi possível mover arquivo: {e}")
            else:
                erro_count += 1
                # Mover arquivo para pasta 'erros'
                try:
                    destino_erros = os.path.join(pasta_erros, arquivo.name)
                    shutil.move(str(arquivo), destino_erros)
                    logger.info(f"  → Movido para: erros/{arquivo.name}")
                except Exception as e:
                    logger.info(f"  [AVISO] Não foi possível mover arquivo: {e}")

            logger.info()

        logger.info("="*60)
        logger.info(f"RESUMO: {sucesso_count} sucesso(s), {erro_count} erro(s)")
        logger.info(f"Arquivos processados movidos para: enviados/ e erros/")
        logger.info("="*60)


def menu_principal():
    """Exibe menu principal interativo"""
    gerenciador = GerenciadorNFSe()

    while True:
        logger.info("\n" + "="*60)
        logger.info("SISTEMA DE EMISSÃO DE NFS-e")
        logger.info("SANTANA DE PARNAÍBA - SIMPLISS")
        logger.info("="*60)
        logger.info("1. Emitir NFS-e (arquivo específico)")
        logger.info("2. Consultar NFS-e")
        logger.info("3. Cancelar NFS-e")
        logger.info("4. Emitir em lote (pasta)")
        logger.info("5. Sair")
        logger.info("-"*60)

        opcao = input("Escolha uma opção: ").strip()

        if opcao == "1":
            arquivo = input("Caminho do arquivo XML: ").strip()
            if arquivo:
                gerenciador.emitir_nfse(arquivo)

        elif opcao == "2":
            chave = input("Chave de Acesso (ex: 12 123456789 123456789 123456789): ").strip()
            if chave:
                gerenciador.consultar_nfse(chave)

        elif opcao == "3":
            chave = input("Chave de Acesso: ").strip()
            arquivo_evento = input("Caminho do arquivo de evento XML: ").strip()
            if chave and arquivo_evento:
                gerenciador.cancelar_nfse(chave, arquivo_evento)

        elif opcao == "4":
            pasta = input("Caminho da pasta (Enter para usar config.json): ").strip()
            gerenciador.emitir_lote(pasta if pasta else None)

        elif opcao == "5":
            logger.info("Encerrando...")
            break

        else:
            logger.info("[ERRO] Opção inválida!")


if __name__ == "__main__":
    # Se for passado argumento via linha de comando
    if len(sys.argv) > 1:
        comando = sys.argv[1]

        gerenciador = GerenciadorNFSe()

        if comando == "emitir" and len(sys.argv) > 2:
            gerenciador.emitir_nfse(sys.argv[2])

        elif comando == "consultar" and len(sys.argv) > 2:
            gerenciador.consultar_nfse(sys.argv[2])

        elif comando == "cancelar" and len(sys.argv) > 3:
            gerenciador.cancelar_nfse(sys.argv[2], sys.argv[3])

        elif comando == "lote":
            pasta = sys.argv[2] if len(sys.argv) > 2 else None
            gerenciador.emitir_lote(pasta)

        else:
            logger.info("Uso:")
            logger.info("  python main.py emitir <arquivo.xml>")
            logger.info("  python main.py consultar <chave_acesso>")
            logger.info("  python main.py cancelar <chave_acesso> <evento.xml>")
            logger.info("  python main.py lote [pasta]")
            logger.info("\nOu execute sem argumentos para menu interativo:")
            logger.info("  python main.py")

    else:
        # Menu interativo
        menu_principal()
