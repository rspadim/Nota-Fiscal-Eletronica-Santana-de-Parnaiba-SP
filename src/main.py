"""
Script principal para emissão de NFS-e
Lê configuração de config.json e gerencia o envio de NFS-e
"""

import json
import os
import sys
import time
import shutil
from datetime import datetime
from pathlib import Path
from nfse_simples import ClienteNFSeSimples


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
                print(f"[OK] Configuração carregada de {arquivo_config}")
                return config
        except FileNotFoundError:
            print(f"[ERRO] Arquivo de configuração não encontrado: {arquivo_config}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"[ERRO] Erro ao ler JSON: {e}")
            sys.exit(1)

    def _inicializar_cliente(self):
        """Inicializa o cliente NFS-e com as configurações"""
        cert_config = self.config.get("certificado", {})
        certificado = cert_config.get("caminho_cert")
        chave = cert_config.get("caminho_chave")

        if not certificado:
            print("[ERRO] Caminho do certificado não configurado em config.json")
            sys.exit(1)

        if not os.path.exists(certificado):
            print(f"[ERRO] Certificado não encontrado: {certificado}")
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

        print(f"[OK] Cliente configurado para {self.config.get('ambiente', 'homologacao')}")

    def emitir_nfse(self, arquivo_xml: str) -> bool:
        """
        Emite uma NFS-e

        Args:
            arquivo_xml: Caminho do arquivo XML da DPS

        Returns:
            True se sucesso, False caso contrário
        """
        print("\n" + "="*60)
        print("EMISSÃO DE NFS-e")
        print("="*60)

        if not os.path.exists(arquivo_xml):
            print(f"[ERRO] Arquivo não encontrado: {arquivo_xml}")
            return False

        print(f"Arquivo: {arquivo_xml}")

        sucesso, resposta = self.cliente.emitir_nfse_xml(arquivo_xml)

        if sucesso:
            print("\n[OK] NFS-e emitida com SUCESSO!")

            if "numero_nfse" in resposta:
                print(f"  Número da NFS-e: {resposta['numero_nfse']}")

            if "chave_acesso" in resposta:
                print(f"  Chave de Acesso: {resposta['chave_acesso']}")

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
            print("\n[ERRO] Erro na emissão:")
            erro = resposta.get("erro", resposta)
            if isinstance(erro, dict):
                for chave, valor in erro.items():
                    print(f"  {chave}: {valor}")
            else:
                print(f"  {erro}")
            return False

    def consultar_nfse(self, chave_acesso: str) -> bool:
        """
        Consulta uma NFS-e

        Args:
            chave_acesso: Chave de acesso da NFS-e

        Returns:
            True se sucesso, False caso contrário
        """
        print("\n" + "="*60)
        print("CONSULTA DE NFS-e")
        print("="*60)
        print(f"Chave de Acesso: {chave_acesso}")

        sucesso, resposta = self.cliente.consultar_nfse(chave_acesso)

        if sucesso:
            print("\n[OK] NFS-e consultada com SUCESSO!")

            if resposta.get("xml"):
                # Salvar XML
                pasta_saida = self.config.get("nfse", {}).get("caminho_xml_saida", "./nfse_emitidas")
                os.makedirs(pasta_saida, exist_ok=True)

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                nome_arquivo = os.path.join(pasta_saida, f"nfse_consulta_{chave_acesso.replace(' ', '')}_{timestamp}.xml")

                self.cliente.salvar_resposta_xml(resposta["xml"], nome_arquivo)

            return True
        else:
            print("\n[ERRO] Erro na consulta:")
            print(f"  {resposta.get('erro')}")
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
        print("\n" + "="*60)
        print("CANCELAMENTO DE NFS-e")
        print("="*60)
        print(f"Chave de Acesso: {chave_acesso}")
        print(f"Arquivo do Evento: {arquivo_evento}")

        if not os.path.exists(arquivo_evento):
            print(f"[ERRO] Arquivo de evento não encontrado: {arquivo_evento}")
            return False

        sucesso, resposta = self.cliente.cancelar_nfse(chave_acesso, arquivo_evento)

        if sucesso:
            print("\n[OK] NFS-e cancelada com SUCESSO!")
            return True
        else:
            print("\n[ERRO] Erro no cancelamento:")
            print(f"  {resposta.get('erro')}")
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
            print(f"[ERRO] Pasta não encontrada: {pasta_xml}")
            return

        # Criar subpastas para organizar arquivos
        pasta_enviados = os.path.join(pasta_xml, "enviados")
        pasta_erros = os.path.join(pasta_xml, "erros")
        os.makedirs(pasta_enviados, exist_ok=True)
        os.makedirs(pasta_erros, exist_ok=True)

        arquivos_xml = list(Path(pasta_xml).glob("*.xml"))

        if not arquivos_xml:
            print(f"[ERRO] Nenhum arquivo XML encontrado em: {pasta_xml}")
            return

        print(f"\n{'='*60}")
        print(f"EMISSÃO EM LOTE")
        print(f"{'='*60}")
        print(f"Total de arquivos: {len(arquivos_xml)}\n")

        sucesso_count = 0
        erro_count = 0

        for i, arquivo in enumerate(arquivos_xml, 1):
            print(f"[{i}/{len(arquivos_xml)}] Processando: {arquivo.name}")

            if self.emitir_nfse(str(arquivo)):
                sucesso_count += 1
                # Mover arquivo para pasta 'enviados'
                try:
                    destino_enviados = os.path.join(pasta_enviados, arquivo.name)
                    shutil.move(str(arquivo), destino_enviados)
                    print(f"  → Movido para: enviados/{arquivo.name}")
                except Exception as e:
                    print(f"  [AVISO] Não foi possível mover arquivo: {e}")
            else:
                erro_count += 1
                # Mover arquivo para pasta 'erros'
                try:
                    destino_erros = os.path.join(pasta_erros, arquivo.name)
                    shutil.move(str(arquivo), destino_erros)
                    print(f"  → Movido para: erros/{arquivo.name}")
                except Exception as e:
                    print(f"  [AVISO] Não foi possível mover arquivo: {e}")

            print()

        print("="*60)
        print(f"RESUMO: {sucesso_count} sucesso(s), {erro_count} erro(s)")
        print(f"Arquivos processados movidos para: enviados/ e erros/")
        print("="*60)


def menu_principal():
    """Exibe menu principal interativo"""
    gerenciador = GerenciadorNFSe()

    while True:
        print("\n" + "="*60)
        print("SISTEMA DE EMISSÃO DE NFS-e")
        print("SANTANA DE PARNAÍBA - SIMPLISS")
        print("="*60)
        print("1. Emitir NFS-e (arquivo específico)")
        print("2. Consultar NFS-e")
        print("3. Cancelar NFS-e")
        print("4. Emitir em lote (pasta)")
        print("5. Sair")
        print("-"*60)

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
            print("Encerrando...")
            break

        else:
            print("[ERRO] Opção inválida!")


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
            print("Uso:")
            print("  python main.py emitir <arquivo.xml>")
            print("  python main.py consultar <chave_acesso>")
            print("  python main.py cancelar <chave_acesso> <evento.xml>")
            print("  python main.py lote [pasta]")
            print("\nOu execute sem argumentos para menu interativo:")
            print("  python main.py")

    else:
        # Menu interativo
        menu_principal()
