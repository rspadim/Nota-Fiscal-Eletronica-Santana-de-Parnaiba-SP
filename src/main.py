"""
Script principal para emissão de NFS-e
Lê configuração de config.json e gerencia o envio de NFS-e
"""

import builtins
import getpass
import json
import os
import re
import shutil
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET

import logger_config
from logger_config import input_and_log, print_and_log
from nfse_pdf import (
    PortalError,
    PortalSimpliss,
    extrair_notas_xml,
    identificar_dps,
)
from nfse_simples import ClienteNFSeSimples

# Substitui print() e input() padrão (com data/hora + salva em arquivo)
builtins.print = print_and_log
builtins.input = input_and_log


class GerenciadorNFSe:
    """Gerenciador de emissão e consulta de NFS-e"""

    def __init__(self, arquivo_config: str = "config.json", dry_run: bool = False):
        """Inicializa o gerenciador com arquivo de configuração"""
        self.dry_run = dry_run
        if arquivo_config == "config.json" and getattr(sys, "frozen", False):
            arquivo_config = self._localizar_config_instalado(arquivo_config)
        self._caminho_config = os.path.abspath(arquivo_config)
        self.config = self._carregar_config(arquivo_config)
        self.cliente = None
        self._inicializar_cliente()

    @staticmethod
    def _localizar_config_instalado(padrao: str = "config.json") -> str:
        """
        Procura o config.json nos lugares usados pelos pacotes.

        Ordem: pasta atual > junto do executavel (Windows/.exe) >
        ~/.config/nfse-santana (Linux, instalado via .deb) > /etc/nfse-santana.
        """
        candidatos = [Path.cwd() / padrao]
        if getattr(sys, "frozen", False):
            candidatos.append(Path(sys.executable).resolve().parent / padrao)
        candidatos.append(Path.home() / ".config" / "nfse-santana" / padrao)
        candidatos.append(Path("/etc/nfse-santana") / padrao)

        for candidato in candidatos:
            if candidato.is_file():
                return str(candidato)
        return padrao

    @staticmethod
    def _aguardar_saida() -> None:
        """
        No .exe do Windows a janela fecharia na hora; espera o usuario ler.

        No Linux o programa roda no terminal, entao nao precisa parar.
        """
        if getattr(sys, "frozen", False) and os.name == "nt":
            try:
                input("Pressione Enter para fechar...")
            except (EOFError, KeyboardInterrupt, SystemExit):
                pass

    def _carregar_config(self, arquivo_config: str) -> dict:
        """Carrega configurações do arquivo JSON"""
        try:
            caminho_config = os.path.abspath(arquivo_config)
            with open(caminho_config, 'r', encoding='utf-8') as f:
                config = json.load(f)
                print(f"[OK] Configuração carregada de {arquivo_config}")
                self._normalizar_caminhos_config(config, os.path.dirname(caminho_config))
                self._configurar_logs(config)
                return config
        except FileNotFoundError:
            print(f"[ERRO] Arquivo de configuração não encontrado: {caminho_config}")
            print("  Copie config.json.exemplo para config.json e preencha os dados.")
            self._aguardar_saida()
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"[ERRO] Erro ao ler JSON: {e}")
            print(f"  Corrija o arquivo: {caminho_config}")
            self._aguardar_saida()
            sys.exit(1)

    @staticmethod
    def _configurar_logs(config: dict) -> None:
        """Aplica pasta e retencao dos logs a partir do config.json."""
        log_config = config.get("log", {}) or {}
        nfse_config = config.get("nfse", {}) or {}
        pasta = log_config.get("pasta") or nfse_config.get("caminho_logs")
        retencao = log_config.get("retencao_dias", 30)
        logger_config.configurar(pasta=pasta, retencao_dias=retencao)

    @staticmethod
    def _resolver_caminho(caminho: str, base_dir: str) -> str:
        """Resolve caminho relativo do config para absoluto, com normalização."""
        if not caminho:
            return caminho
        if os.path.isabs(caminho):
            return os.path.normpath(caminho)
        return os.path.normpath(os.path.abspath(os.path.join(base_dir, caminho)))

    def _normalizar_caminhos_config(self, config: dict, base_dir: str) -> None:
        """Normaliza em memória os caminhos configuráveis para evitar ambiguidades de cwd."""
        cert_config = config.get("certificado", {})
        if isinstance(cert_config, dict):
            for chave in ("caminho_cert", "caminho_chave"):
                valor = cert_config.get(chave)
                if isinstance(valor, str):
                    cert_config[chave] = self._resolver_caminho(valor, base_dir)

        nfse_config = config.get("nfse", {})
        if isinstance(nfse_config, dict):
            for chave in ("caminho_xml_entrada", "caminho_xml_enviados", "caminho_xml_saida", "caminho_logs"):
                valor = nfse_config.get(chave)
                if isinstance(valor, str):
                    nfse_config[chave] = self._resolver_caminho(valor, base_dir)

    def _inicializar_cliente(self):
        """Inicializa o cliente NFS-e com as configurações"""
        cert_config = self.config.get("certificado", {})
        certificado = cert_config.get("caminho_cert")
        chave = cert_config.get("caminho_chave")

        if not certificado:
            print("[ERRO] Caminho do certificado não configurado em config.json")
            print("  Preencha 'certificado.caminho_cert' no config.json.")
            self._aguardar_saida()
            sys.exit(1)

        if not os.path.exists(certificado):
            print(f"[ERRO] Certificado não encontrado: {certificado}")
            print("  Ajuste 'certificado.caminho_cert' no config.json.")
            self._aguardar_saida()
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

        self._print_caminhos_ativos()
        print(f"[OK] Cliente configurado para {self.config.get('ambiente', 'homologacao')}")

    def _print_caminhos_ativos(self) -> None:
        """Exibe caminhos efetivos usados pela aplicação."""
        nfse_config = self.config.get("nfse", {})
        cert_config = self.config.get("certificado", {})

        print("-" * 60)
        print("[INFO] Caminhos em uso")
        print(f"  config: {self._caminho_config}")
        print(f"  cwd: {os.getcwd()}")
        print(f"  certificado: {cert_config.get('caminho_cert', '')}")
        print(f"  chave_privada: {cert_config.get('caminho_chave', '')}")
        print(f"  xml_entrada: {nfse_config.get('caminho_xml_entrada', '')}")
        print(f"  xml_enviados: {nfse_config.get('caminho_xml_enviados', '')}")
        print(f"  xml_saida: {nfse_config.get('caminho_xml_saida', '')}")
        print(f"  logs: {nfse_config.get('caminho_logs', '')}")
        print("-" * 60)

    def emitir_nfse(self, arquivo_xml: str, interativo: bool = True) -> bool:
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

        if self._avisar_duplicidade(arquivo_xml) and interativo:
            resposta = input("Continuar mesmo assim? [s/N]: ").strip().lower()
            if resposta != "s":
                print("[INFO] Emissao cancelada pelo usuario.")
                return False

        if self.dry_run:
            self._simulacao(f"emitiria a NFS-e de {os.path.basename(arquivo_xml)}")
            return True

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

    def cancelamento_assistido(self, arquivo_nfse: str = None) -> bool:
        """
        Cancelamento assistido de NFS-e
        Lê o XML da NFS-e, coleta motivo, gera evento, confirma e envia

        Args:
            arquivo_nfse: Caminho do XML da NFS-e (opcional, pergunta se não informado)

        Returns:
            True se sucesso, False caso contrário
        """
        print("\n" + "="*60)
        print("CANCELAMENTO ASSISTIDO DE NFS-e")
        print("="*60)

        # 1. Obter caminho do XML da NFS-e
        if not arquivo_nfse:
            arquivo_nfse = input("Caminho do XML da NFS-e: ").strip()
        if not arquivo_nfse:
            print("[ERRO] Nenhum arquivo informado.")
            return False

        if not os.path.exists(arquivo_nfse):
            print(f"[ERRO] Arquivo não encontrado: {arquivo_nfse}")
            return False

        # 2. Ler e parsear o XML da NFS-e
        try:
            with open(arquivo_nfse, 'r', encoding='utf-8') as f:
                xml_nfse = f.read()

            ns = 'http://www.sped.fazenda.gov.br/nfse'
            root = ET.fromstring(xml_nfse)

            inf_nfse = root.find(f'.//{{{ns}}}infNFSe')
            if inf_nfse is None:
                print("[ERRO] Elemento infNFSe não encontrado no XML")
                return False

            # Extrair chave de acesso (atributo Id)
            chave_completa = inf_nfse.get('Id', '')
            if not chave_completa.startswith('NFS'):
                print("[ERRO] ID da NFS-e não começa com 'NFS'")
                return False
            chave_acesso = chave_completa[3:].zfill(50)  # Remove "NFS" e completa para 50 dígitos (XSD)

            # Extrair dados relevantes
            n_nfse = root.findtext(f'.//{{{ns}}}nNFSe', '')
            n_dfse = root.findtext(f'.//{{{ns}}}nDFSe', '')
            tp_amb = root.findtext(f'.//{{{ns}}}tpAmb', '1')
            cnpj_emit = root.findtext(f'.//{{{ns}}}emit/{{{ns}}}CNPJ', '')
            x_nome_emit = root.findtext(f'.//{{{ns}}}emit/{{{ns}}}xNome', '')
            v_bc = root.findtext(f'.//{{{ns}}}valores/{{{ns}}}vBC', '')
            v_issqn = root.findtext(f'.//{{{ns}}}valores/{{{ns}}}vISSQN', '')
            v_liq = root.findtext(f'.//{{{ns}}}valores/{{{ns}}}vLiq', '')

        except ET.ParseError as e:
            print(f"[ERRO] XML inválido: {e}")
            return False
        except Exception as e:
            print(f"[ERRO] Ao ler XML: {e}")
            return False

        # 3. Mostrar dados da NFS-e
        print("\n" + "-"*60)
        print("DADOS DA NFS-e:")
        print(f"  Chave de Acesso: {chave_acesso}")
        print(f"  NFS-e Nº:        {n_nfse}")
        print(f"  DFS-e Nº:        {n_dfse}")
        print(f"  Ambiente:        {'Produção' if tp_amb == '1' else 'Homologação'}")
        print(f"  Emitente:        {x_nome_emit}")
        print(f"  CNPJ:            {cnpj_emit}")
        print(f"  Valor BC:        R$ {v_bc}")
        print(f"  ISSQN:           R$ {v_issqn}")
        print(f"  Valor Líquido:   R$ {v_liq}")
        print("-"*60)

        # 4. Coletar motivo do cancelamento
        print("\nMOTIVO DO CANCELAMENTO:")
        print("  1 - Erro na Emissão")
        print("  2 - Serviço não Prestado")
        print("  9 - Outros")

        while True:
            cod_motivo = input("Código do motivo (1/2/9): ").strip()
            if cod_motivo in ('1', '2', '9'):
                break
            print("[ERRO] Código inválido. Use 1, 2 ou 9.")

        motivos_tipo = {'1': 'Erro na Emissão', '2': 'Serviço não Prestado', '9': 'Outros'}
        print(f"  → {motivos_tipo[cod_motivo]}")

        while True:
            x_motivo = input("Descrição do motivo (mínimo 15 caracteres): ").strip()
            if len(x_motivo) >= 15:
                break
            print(f"[ERRO] Muito curto ({len(x_motivo)} caracteres). Mínimo 15.")

        # 5. Gerar XML do evento
        agora = datetime.now()
        dh_evento = agora.strftime("%Y-%m-%dT%H:%M:%S-03:00")

        id_pedido = f"PRE{chave_acesso}101101"

        xml_evento = f"""<pedRegEvento xmlns="http://www.sped.fazenda.gov.br/nfse" versao="1.01">
  <infPedReg Id="{id_pedido}">
    <tpAmb>{tp_amb}</tpAmb>
    <verAplic>Spadim_v1.0</verAplic>
    <dhEvento>{dh_evento}</dhEvento>
    <CNPJAutor>{cnpj_emit}</CNPJAutor>
    <chNFSe>{chave_acesso}</chNFSe>
    <e101101>
      <xDesc>Cancelamento de NFS-e</xDesc>
      <cMotivo>{cod_motivo}</cMotivo>
      <xMotivo>{x_motivo}</xMotivo>
    </e101101>
  </infPedReg>
</pedRegEvento>"""

        # 6. Confirmar
        print("\n" + "="*60)
        print("CONFIRMAÇÃO DO CANCELAMENTO")
        print("="*60)
        print(f"  NFS-e:       Nº {n_nfse} (DFS-e {n_dfse})")
        print(f"  Chave:       {chave_acesso}")
        print(f"  Valor:       R$ {v_liq}")
        print(f"  Motivo:      {motivos_tipo[cod_motivo]}")
        print(f"  Descrição:   {x_motivo}")
        print(f"  Ambiente:    {'Produção' if tp_amb == '1' else 'Homologação'}")
        print("="*60)

        confirmacao = input("\nConfirma o cancelamento? (S/N): ").strip().upper()
        if confirmacao != 'S':
            print("[INFO] Cancelamento abortado pelo usuário.")
            return False

        # 7. Enviar cancelamento
        print("\n[INFO] Enviando cancelamento...")
        sucesso, resposta = self.cliente.cancelar_nfse(chave_acesso, xml_evento, assinar=True)

        if sucesso:
            print("\n[OK] NFS-e CANCELADA com SUCESSO!")

            if resposta.get("xml"):
                pasta_saida = self.config.get("nfse", {}).get("caminho_xml_saida", "./nfse_emitidas")
                os.makedirs(pasta_saida, exist_ok=True)
                timestamp = agora.strftime("%Y%m%d_%H%M%S")
                nome_arquivo = os.path.join(pasta_saida, f"cancelamento_{n_nfse}_{timestamp}.xml")
                self.cliente.salvar_resposta_xml(resposta["xml"], nome_arquivo)

            return True
        else:
            print("\n[ERRO] Erro no cancelamento:")
            erro = resposta.get("erro", resposta)
            if isinstance(erro, dict):
                for chave, valor in erro.items():
                    print(f"  {chave}: {valor}")
            else:
                print(f"  {erro}")
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
        if not self.dry_run:
            os.makedirs(pasta_enviados, exist_ok=True)
            os.makedirs(pasta_erros, exist_ok=True)

        arquivos_xml = list(Path(pasta_xml).glob("*.xml"))

        if not arquivos_xml:
            print(f"[ERRO] Nenhum arquivo XML encontrado em: {pasta_xml}")
            return

        print(f"\n{'='*60}")
        print("EMISSÃO EM LOTE")
        print(f"{'='*60}")
        print(f"Total de arquivos: {len(arquivos_xml)}\n")

        sucesso_count = 0
        erro_count = 0

        for i, arquivo in enumerate(arquivos_xml, 1):
            print(f"[{i}/{len(arquivos_xml)}] Processando: {arquivo.name}")

            if self.emitir_nfse(str(arquivo), interativo=False):
                sucesso_count += 1
                if self.dry_run:
                    print(f"  [SIMULACAO] manteria {arquivo.name} (nao move para enviados/)")
                    print()
                    continue
                # Mover arquivo para pasta 'enviados'
                try:
                    destino_enviados = os.path.join(pasta_enviados, arquivo.name)
                    shutil.move(str(arquivo), destino_enviados)
                    print(f"  → Movido para: enviados/{arquivo.name}")
                except Exception as e:
                    print(f"  [AVISO] Não foi possível mover arquivo: {e}")
            else:
                erro_count += 1
                if self.dry_run:
                    print(f"  [SIMULACAO] manteria {arquivo.name} (nao move para erros/)")
                    print()
                    continue
                # Mover arquivo para pasta 'erros'
                try:
                    destino_erros = os.path.join(pasta_erros, arquivo.name)
                    shutil.move(str(arquivo), destino_erros)
                    print(f"  → Movido para: erros/{arquivo.name}")
                except Exception as e:
                    print(f"  [AVISO] Não foi possível mover arquivo: {e}")

            print()

        print("="*60)
        titulo = "RESUMO (SIMULACAO)" if self.dry_run else "RESUMO"
        print(f"{titulo}: {sucesso_count} sucesso(s), {erro_count} erro(s)")
        if self.dry_run:
            print("Nenhum arquivo foi movido (modo simulacao).")
        else:
            print("Arquivos processados movidos para: enviados/ e erros/")
        print("="*60)

    @staticmethod
    def _extrair_zip(arquivo_zip: str, pasta_destino: str) -> int:
        """
        Extrai o conteúdo de um ZIP para pasta_destino.

        - Ignora pastas e arquivos de sistema (__MACOSX, .DS_Store, Thumbs.db)
        - Impede path traversal (zip slip)
        - Preserva a estrutura interna de subpastas

        Returns:
            Quantidade de arquivos extraídos
        """
        ignorados = {"__MACOSX", ".DS_Store", "Thumbs.db", "desktop.ini"}
        total = 0
        raiz_destino = os.path.abspath(pasta_destino)

        with zipfile.ZipFile(arquivo_zip) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue

                nome = info.filename.replace("\\", "/")
                partes = [p for p in nome.split("/") if p not in ("", ".")]
                if not partes or partes[0] == "__MACOSX" or partes[-1] in ignorados:
                    continue

                caminho_absoluto = nome.startswith("/") or (len(partes[0]) > 1 and partes[0][1] == ":")
                if ".." in partes or caminho_absoluto:
                    print(f"  [AVISO] Entrada suspeita ignorada: {info.filename}")
                    continue

                destino = os.path.join(pasta_destino, *partes)
                if not os.path.abspath(destino).startswith(raiz_destino + os.sep):
                    print(f"  [AVISO] Entrada suspeita ignorada: {info.filename}")
                    continue

                os.makedirs(os.path.dirname(destino), exist_ok=True)
                with zf.open(info) as origem, open(destino, "wb") as saida:
                    shutil.copyfileobj(origem, saida)
                total += 1

        return total

    @staticmethod
    def _mover_zip_processado(arquivo_zip: str) -> None:
        """Move o ZIP para a subpasta 'processados' ao lado dele (nunca apaga)."""
        pasta_origem = os.path.dirname(os.path.abspath(arquivo_zip))
        pasta_destino = os.path.join(pasta_origem, "processados")
        os.makedirs(pasta_destino, exist_ok=True)

        nome = os.path.basename(arquivo_zip)
        destino = os.path.join(pasta_destino, nome)
        if os.path.exists(destino):
            base, ext = os.path.splitext(nome)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            destino = os.path.join(pasta_destino, f"{base}_{timestamp}{ext}")

        shutil.move(arquivo_zip, destino)
        print(f"[ZIP] Movido para: {destino}")

    def emitir_lote_zip(self, arquivo_zip: str) -> bool:
        """
        Importa um arquivo .ZIP e emite as DPS contidas nele.

        Fluxo:
            1. Cria a pasta <pasta_do_zip>/<nome_do_zip_sem_extensao> (se não existir)
            2. Extrai os XMLs nela
            3. Roda o lote normal (enviados/ e erros/ dentro da pasta)
            4. Move o ZIP para <pasta_do_zip>/processados/

        Args:
            arquivo_zip: Caminho do arquivo .ZIP

        Returns:
            True se o lote rodou até o fim, False caso contrário
        """
        arquivo_zip = (arquivo_zip or "").strip().strip('"').strip("'")

        print("\n" + "="*60)
        print("IMPORTAR LOTE DE ARQUIVO ZIP")
        print("="*60)

        if not arquivo_zip:
            print("[ERRO] Nenhum arquivo informado.")
            return False

        if not os.path.isfile(arquivo_zip):
            print(f"[ERRO] Arquivo não encontrado: {arquivo_zip}")
            return False

        if not arquivo_zip.lower().endswith(".zip"):
            print(f"[ERRO] Arquivo não é um ZIP: {arquivo_zip}")
            return False

        if not zipfile.is_zipfile(arquivo_zip):
            print(f"[ERRO] ZIP inválido ou corrompido: {arquivo_zip}")
            return False

        pasta_base = os.path.dirname(os.path.abspath(arquivo_zip))
        nome_zip = os.path.splitext(os.path.basename(arquivo_zip))[0]
        pasta_lote = os.path.join(pasta_base, nome_zip)

        print(f"[ZIP] Arquivo: {os.path.abspath(arquivo_zip)}")
        print(f"[ZIP] Pasta do lote: {pasta_lote}")

        if self.dry_run:
            try:
                with zipfile.ZipFile(arquivo_zip) as zf:
                    xmls = [i.filename for i in zf.infolist()
                            if i.filename.lower().endswith(".xml") and not i.is_dir()]
            except Exception as e:
                print(f"[ERRO] Nao foi possivel ler o ZIP: {e}")
                return False
            self._simulacao(
                f"extrairia {len(xmls)} XML(s) para {pasta_lote} e emitiria o lote"
            )
            self._simulacao("o ZIP nao seria movido para processados/")
            return True

        try:
            if os.path.isdir(pasta_lote):
                print("[ZIP] Pasta já existe, reaproveitando (retoma lote interrompido).")
            else:
                os.makedirs(pasta_lote, exist_ok=True)
                extraidos = self._extrair_zip(arquivo_zip, pasta_lote)
                print(f"[ZIP] Pasta criada. {extraidos} arquivo(s) extraído(s).")
        except RuntimeError as e:
            print(f"[ERRO] ZIP protegido por senha ou não suportado: {e}")
            print("[ZIP] ZIP mantido na origem.")
            return False
        except zipfile.BadZipFile as e:
            print(f"[ERRO] ZIP inválido: {e}")
            print("[ZIP] ZIP mantido na origem.")
            return False
        except Exception as e:
            print(f"[ERRO] Falha ao extrair ZIP: {e}")
            print("[ZIP] ZIP mantido na origem.")
            return False

        pendentes = sorted(Path(pasta_lote).glob("*.xml"))
        if not pendentes:
            print("[INFO] Nenhum XML pendente nesta pasta (tudo já foi processado).")
        else:
            self.emitir_lote(pasta_lote)

        self._mover_zip_processado(arquivo_zip)
        return True

    def _simulacao(self, mensagem: str) -> None:
        """Marca uma acao que nao sera executada por estar em modo simulacao."""
        print(f"  [SIMULACAO] {mensagem}")

    def _pasta_pdfs(self) -> str:
        """Pasta raiz onde os PDFs sao gravados (por competencia)."""
        return self.config.get("nfse", {}).get("caminho_xml_saida", "./nfse_emitidas")

    def _dps_ja_emitidos(self) -> dict:
        """
        Mapa id_dps -> caminho do XML de resposta, lendo nfse_emitidas/.

        Montado uma vez por instancia; usado para avisar sobre reenvio.
        """
        if getattr(self, "_cache_dps", None) is not None:
            return self._cache_dps

        pasta = self.config.get("nfse", {}).get("caminho_xml_saida", "./nfse_emitidas")
        mapa = {}
        if os.path.isdir(pasta):
            for arquivo in Path(pasta).rglob("*.xml"):
                try:
                    with open(arquivo, "r", encoding="utf-8", errors="ignore") as f:
                        conteudo = f.read()
                except OSError:
                    continue
                for id_dps in re.findall(r'id="(DPS\d{20,})"', conteudo, flags=re.IGNORECASE):
                    mapa.setdefault(id_dps, str(arquivo))
        self._cache_dps = mapa
        return mapa

    def _avisar_duplicidade(self, arquivo_xml: str) -> bool:
        """
        Avisa se a DPS do arquivo ja aparece em nfse_emitidas/.

        Nao bloqueia: o portal e a fonte da verdade, e um reenvio pode ser
        proposital. Returns True quando encontrou um emitido anterior.
        """
        id_dps = identificar_dps(arquivo_xml)
        if not id_dps:
            return False

        anterior = self._dps_ja_emitidos().get(id_dps)
        if not anterior:
            return False

        print("\n[AVISO] Esta DPS ja consta em uma NFS-e emitida:")
        print(f"  DPS: {id_dps}")
        print(f"  XML: {anterior}")
        print("  Reenviar pode gerar nota duplicada.")
        return True

    def _abrir_portal(self):
        """Cria o cliente do portal e autentica. Retorna None em caso de falha."""
        try:
            portal = self._criar_portal()
            print("[INFO] Autenticando no portal...")
            portal.login()
            print("[OK] Login realizado.")
            return portal
        except PortalError as e:
            print(f"[ERRO] {e}")
        except Exception as e:
            print(f"[ERRO] Falha ao acessar o portal: {e}")
        return None

    def _salvar_pdf(self, portal, nota, pasta_base: str,
                    chave_esperada: str = None) -> str:
        """
        Baixa e grava o PDF de uma nota.

        Returns:
            'baixado'  - gravou agora
            'existente'- o arquivo ja estava la
            'sem_pdf'  - o portal nao oferece o PDF
        """
        pasta = os.path.join(pasta_base, "pdf", nota.competencia)

        if self.dry_run:
            # nao baixa nada: so informa o que faria
            if chave_esperada:
                nome = os.path.join(pasta, f"nfse_{nota.numero}_{chave_esperada}.pdf")
                if os.path.exists(nome):
                    print(f"  [INFO] Ja existe: {os.path.relpath(nome, pasta_base)}")
                    return "existente"
            self._simulacao(
                f"baixaria o PDF da NFS-e {nota.numero} para {pasta}"
            )
            return "baixado"

        resultado = portal.baixar_pdf(nota, chave_esperada=chave_esperada)
        if not resultado:
            return "sem_pdf"

        conteudo, chave = resultado
        os.makedirs(pasta, exist_ok=True)
        nome = os.path.join(pasta, f"nfse_{nota.numero}_{chave}.pdf")

        if os.path.exists(nome):
            print(f"  [INFO] Ja existe: {os.path.relpath(nome, pasta_base)}")
            return "existente"

        with open(nome, "wb") as arquivo:
            arquivo.write(conteudo)
        print(f"  [OK] Salvo: {os.path.relpath(nome, pasta_base)} ({len(conteudo) // 1024} KB)")
        return "baixado"

    def gerar_indice_pdfs(self) -> bool:
        """
        Gera nfse_emitidas/pdf/indice.csv com as notas emitidas e o PDF de cada uma.

        A lista vem dos XMLs em nfse_emitidas/ (notas sem PDF aparecem com a
        coluna 'pdf' vazia) e tambem dos PDFs em pdf/, para o caso de notas
        baixadas pelo portal que nao tem XML salvo.
        """
        import csv

        print("\n" + "="*60)
        print("INDICE DOS PDFs")
        print("="*60)

        pasta_base = self._pasta_pdfs()
        if not os.path.isdir(pasta_base):
            print(f"[ERRO] Pasta nao encontrada: {pasta_base}")
            return False

        notas = {}
        avisos = 0
        for arquivo in sorted(Path(pasta_base).rglob("*.xml")):
            encontradas, problemas, _ = extrair_notas_xml(str(arquivo))
            avisos += len(problemas)
            for nota in encontradas:
                notas.setdefault(nota.chave, nota)

        pdfs = {p.stem: p for p in Path(pasta_base, "pdf").rglob("*.pdf")}             if os.path.isdir(os.path.join(pasta_base, "pdf")) else {}

        if not notas and not pdfs:
            print(f"[ERRO] Nenhuma NFS-e encontrada em {pasta_base}")
            return False

        linhas = []
        com_pdf = 0
        for nota in notas.values():
            caminho_pdf = os.path.join(
                pasta_base, "pdf", nota.competencia or "",
                f"nfse_{nota.numero}_{nota.chave}.pdf",
            )
            existe = os.path.isfile(caminho_pdf)
            com_pdf += 1 if existe else 0
            linhas.append({
                "numero": nota.numero,
                "competencia": nota.competencia or "",
                "data": nota.data,
                "valor": nota.valor,
                "tomador": nota.tomador,
                "chave": nota.chave,
                "formato": nota.formato,
                "pdf": os.path.relpath(caminho_pdf, pasta_base) if existe else "",
            })

        # PDFs sem XML correspondente (baixados direto do portal)
        chaves_xml = set(notas)
        vistos = {linha["chave"] for linha in linhas}
        for stem, caminho in sorted(pdfs.items()):
            partes = stem.split("_")
            if len(partes) < 3 or partes[0] != "nfse":
                continue
            numero, chave = partes[1], partes[2]
            if chave in chaves_xml or chave in vistos:
                continue
            vistos.add(chave)
            com_pdf += 1
            linhas.append({
                "numero": numero,
                "competencia": caminho.parent.name,
                "data": "",
                "valor": "",
                "tomador": "",
                "chave": chave,
                "formato": "PDF (sem XML)",
                "pdf": os.path.relpath(caminho, pasta_base),
            })

        linhas.sort(key=lambda linha: (linha["competencia"], int(linha["numero"])
                                        if str(linha["numero"]).isdigit() else 0))

        destino = os.path.join(pasta_base, "pdf", "indice.csv")
        if self.dry_run:
            self._simulacao(f"geraria {destino} com {len(linhas)} nota(s)")
            print("="*60)
            return True
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        with open(destino, "w", encoding="utf-8-sig", newline="") as arquivo:
            escritor = csv.DictWriter(
                arquivo,
                fieldnames=["numero", "competencia", "data", "valor",
                            "tomador", "chave", "formato", "pdf"],
                delimiter=";",
            )
            escritor.writeheader()
            escritor.writerows(linhas)

        print(f"[OK] {len(linhas)} nota(s) | {com_pdf} com PDF | "
              f"{len(linhas) - com_pdf} sem PDF")
        if avisos:
            print(f"  [AVISO] {avisos} XML(s) ilegiveis foram ignorados")
        print(f"  Arquivo: {destino}")
        print("="*60)
        return True

    def baixar_pdfs_de_xml(self, caminho: str) -> bool:
        """
        Baixa os PDFs das NFS-e encontradas em um XML ou em uma pasta de XMLs.

        Aceita os formatos:
          - NFS-e nacional (<NFSe><infNFSe>) - inclusive respostas SOAP
          - exportacao 1.02 SIMPLISS (<NOTAS><NOTA>)
          - DPS (<DPS><infDPS>) - apenas avisa que ainda nao virou nota
        """
        print("\n" + "="*60)
        print("DOWNLOAD DE PDF A PARTIR DE XML")
        print("="*60)

        caminho = (caminho or "").strip().strip('"').strip("'")
        if not caminho:
            print("[ERRO] Nenhum caminho informado.")
            return False
        if not os.path.exists(caminho):
            print(f"[ERRO] Caminho nao encontrado: {caminho}")
            return False

        if os.path.isdir(caminho):
            arquivos = sorted(p for p in Path(caminho).rglob("*") if p.suffix.lower() == ".xml")
        else:
            arquivos = [Path(caminho)]

        if not arquivos:
            print(f"[ERRO] Nenhum XML encontrado em: {caminho}")
            return False

        notas = []
        avisos = []
        dps = []
        vistos = set()

        for arquivo in arquivos:
            encontradas, avisos_arq, dps_arq = extrair_notas_xml(str(arquivo))
            avisos.extend(avisos_arq)
            dps.extend(dps_arq)
            for nota in encontradas:
                if nota.chave in vistos:
                    continue
                vistos.add(nota.chave)
                notas.append(nota)

        print(f"[INFO] {len(arquivos)} XML(s) lido(s) | {len(notas)} NFS-e unica(s) | {len(dps)} DPS sem nota")

        for aviso in avisos[:10]:
            print(f"  [AVISO] {aviso}")
        if len(avisos) > 10:
            print(f"  [AVISO] ... e mais {len(avisos) - 10} aviso(s)")
        for item in dps[:5]:
            print(f"  [INFO] Ignorada: {item} (sem NFS-e emitida)")
        if len(dps) > 5:
            print(f"  [INFO] ... e mais {len(dps) - 5} DPS")

        if not notas:
            print("[ERRO] Nenhuma NFS-e encontrada nos XMLs informados.")
            return False

        portal = self._abrir_portal()
        if not portal:
            return False

        # Localiza no portal pelo numero; a competencia do XML e usada como atalho
        por_numero = {}
        sem_competencia = []
        por_competencia = {}

        for nota in notas:
            if nota.competencia:
                por_competencia.setdefault(nota.competencia, []).append(nota)
            else:
                sem_competencia.append(nota)

        for competencia, itens in sorted(por_competencia.items()):
            ano, mes = int(competencia[:4]), int(competencia[4:])
            encontradas, _ = portal.localizar(
                [i.numero for i in itens], mes=mes, ano=ano
            )
            por_numero.update(encontradas)

        if sem_competencia:
            encontradas, _ = portal.localizar([i.numero for i in sem_competencia])
            por_numero.update(encontradas)

        pasta_base = self._pasta_pdfs()

        ok = 0
        pulados = 0
        erros = 0
        fora = 0

        for nota in notas:
            localizada = por_numero.get(nota.numero)
            if not localizada:
                fora += 1
                print(f"\n[{nota.numero}] [AVISO] Nao localizada no portal "
                      f"(XML: {nota.origem}, chave {nota.chave[:12]}...)")
                continue

            print(f"\n[{nota.numero}] {localizada.data} - R$ {localizada.valor} - "
                  f"{localizada.tomador} ({nota.formato})")

            try:
                situacao = self._salvar_pdf(
                    portal, localizada, pasta_base, chave_esperada=nota.chave
                )
                if situacao == "sem_pdf":
                    print("  [AVISO] Portal nao oferece PDF para esta nota.")
                    pulados += 1
                elif situacao == "existente":
                    pulados += 1
                else:
                    ok += 1

            except PortalError as e:
                erros += 1
                print(f"  [ERRO] {e}")
            except Exception as e:
                erros += 1
                print(f"  [ERRO] Falha ao salvar PDF: {e}")

        print("\n" + "="*60)
        print(f"RESUMO: {ok} baixado(s), {pulados} pulado(s), {erros} erro(s), "
              f"{fora} nao localizada(s)")
        print("="*60)
        return erros == 0 and fora == 0

    @staticmethod
    def _parse_numeros(entrada: str) -> list:
        """
        Converte '65-72,80,90-92' em [65, 66, ..., 72, 80, 90, 91, 92].

        Aceita virgula, ponto e virgula, espaco ou 'a' como separador.
        """
        numeros = []
        texto = (entrada or "").replace(";", ",")
        # "1 a 4" e "1-4" viram faixa; separa antes de trocar espacos por virgula
        texto = re.sub(r"\s+a\s+", "-", texto, flags=re.IGNORECASE)
        texto = texto.replace(" ", ",")
        for parte in texto.split(","):
            parte = parte.strip()
            if not parte:
                continue
            if "-" in parte:
                inicio, _, fim = parte.partition("-")
                try:
                    a, b = int(inicio), int(fim)
                except ValueError:
                    raise ValueError(f"Faixa invalida: {parte}")
                if a > b:
                    a, b = b, a
                numeros.extend(range(a, b + 1))
            else:
                try:
                    numeros.append(int(parte))
                except ValueError:
                    raise ValueError(f"Numero invalido: {parte}")
        return list(dict.fromkeys(numeros))

    def _criar_portal(self) -> PortalSimpliss:
        """Monta o cliente do portal a partir do config.json."""
        portal_cfg = self.config.get("portal", {}) or {}
        empresa = self.config.get("empresa", {}) or {}

        base_url = portal_cfg.get("url") or self.config.get("url_producao")
        usuario = portal_cfg.get("usuario") or empresa.get("cnpj")
        inscricao = portal_cfg.get("inscricao_municipal") or empresa.get("inscricao_municipal")
        senha = portal_cfg.get("senha") or os.environ.get("SIMPLISS_SENHA")

        if not senha:
            senha = getpass.getpass("Senha do portal SIMPLISS: ")

        return PortalSimpliss(
            base_url=base_url,
            usuario=usuario,
            senha=senha,
            inscricao_municipal=inscricao,
        )

    def baixar_pdfs(self, entrada: str, mes: int = None, ano: int = None) -> bool:
        """
        Baixa os PDFs (DANFSE) das NFS-e informadas pelo numero.

        Args:
            entrada: numeros no formato '67' ou '65-72,80'
            mes: mes de competencia (None = mes atual)
            ano: ano de competencia (None = ano atual)

        Returns:
            True se baixou todas, False se houve falha/nota nao encontrada.
        """
        print("\n" + "="*60)
        print("DOWNLOAD DE PDF (DANFSE) - PORTAL SIMPLISS")
        print("="*60)

        try:
            numeros = self._parse_numeros(entrada)
        except ValueError as e:
            print(f"[ERRO] {e}")
            return False

        if not numeros:
            print("[ERRO] Nenhum numero de NFS-e informado.")
            return False

        print(f"NFS-e solicitadas: {', '.join(str(n) for n in numeros)}")

        portal = self._abrir_portal()
        if not portal:
            return False

        encontradas, faltando = portal.localizar(numeros, mes=mes, ano=ano)

        if faltando:
            print(f"[AVISO] Nao localizadas nos ultimos meses: {', '.join(str(n) for n in faltando)}")

        pasta_base = self._pasta_pdfs()

        ok = 0
        pulados = 0
        erros = 0

        for numero in numeros:
            nota = encontradas.get(numero)
            if not nota:
                erros += 1
                continue

            print(f"\n[{numero}] NFS-e {nota.numero} - {nota.data} - R$ {nota.valor} - {nota.tomador}")

            try:
                situacao = self._salvar_pdf(portal, nota, pasta_base)
                if situacao == "sem_pdf":
                    print("  [AVISO] Portal nao oferece PDF para esta nota.")
                    pulados += 1
                elif situacao == "existente":
                    pulados += 1
                else:
                    ok += 1

            except PortalError as e:
                erros += 1
                print(f"  [ERRO] {e}")
            except Exception as e:
                erros += 1
                print(f"  [ERRO] Falha ao salvar PDF: {e}")

        print("\n" + "="*60)
        print(f"RESUMO: {ok} baixado(s), {pulados} pulado(s), {erros} erro(s)")
        print("="*60)
        return erros == 0


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
        print("3. Cancelar NFS-e (manual)")
        print("4. Cancelamento Assistido")
        print("5. Emitir em lote (pasta)")
        print("6. Importar lote de arquivo ZIP")
        print("7. Baixar PDF de NFS-e (por número)")
        print("8. Baixar PDFs a partir de XML (arquivo/pasta)")
        print("9. Gerar indice dos PDFs (CSV)")
        modo = "LIGADO" if gerenciador.dry_run else "desligado"
        print(f"0. Alternar modo simulacao (agora: {modo})")
        print("10. Sair")
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
            gerenciador.cancelamento_assistido()

        elif opcao == "5":
            pasta = input("Caminho da pasta (Enter para usar config.json): ").strip()
            gerenciador.emitir_lote(pasta if pasta else None)

        elif opcao == "6":
            arquivo_zip = input("Caminho do arquivo .ZIP: ").strip()
            if arquivo_zip:
                gerenciador.emitir_lote_zip(arquivo_zip)

        elif opcao == "7":
            entrada = input("Números das NFS-e (ex: 67 ou 65-72,80): ").strip()
            if entrada:
                gerenciador.baixar_pdfs(entrada)

        elif opcao == "8":
            caminho = input("Arquivo .XML ou pasta: ").strip()
            if caminho:
                gerenciador.baixar_pdfs_de_xml(caminho)

        elif opcao == "0":
            gerenciador.dry_run = not gerenciador.dry_run
            estado = "LIGADO (nada sera emitido/baixado/movido)" if gerenciador.dry_run else "desligado"
            print(f"[INFO] Modo simulacao {estado}")

        elif opcao == "9":
            gerenciador.gerar_indice_pdfs()

        elif opcao == "10":
            print("Encerrando...")
            break

        else:
            print("[ERRO] Opção inválida!")


def _extrair_flag(flag: str) -> bool:
    """Remove a flag da linha de comando e informa se ela estava presente."""
    if flag in sys.argv:
        sys.argv.remove(flag)
        return True
    return False


if __name__ == "__main__":
    simulacao = _extrair_flag("--dry-run") or _extrair_flag("-n")

    # Se for passado argumento via linha de comando
    if len(sys.argv) > 1:
        comando = sys.argv[1]

        gerenciador = GerenciadorNFSe(dry_run=simulacao)

        if comando == "emitir" and len(sys.argv) > 2:
            gerenciador.emitir_nfse(sys.argv[2])

        elif comando == "consultar" and len(sys.argv) > 2:
            gerenciador.consultar_nfse(sys.argv[2])

        elif comando == "cancelar" and len(sys.argv) > 3:
            gerenciador.cancelar_nfse(sys.argv[2], sys.argv[3])

        elif comando == "cancelar-assistido":
            arquivo = sys.argv[2] if len(sys.argv) > 2 else None
            gerenciador.cancelamento_assistido(arquivo)

        elif comando == "lote":
            pasta = sys.argv[2] if len(sys.argv) > 2 else None
            gerenciador.emitir_lote(pasta)

        elif comando == "zip":
            if len(sys.argv) > 2:
                gerenciador.emitir_lote_zip(sys.argv[2])
            else:
                print("Uso: python main.py zip <arquivo.zip>")

        elif comando == "pdf":
            if len(sys.argv) > 2:
                mes = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3].isdigit() else None
                ano = int(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[4].isdigit() else None
                gerenciador.baixar_pdfs(sys.argv[2], mes, ano)
            else:
                print("Uso: python main.py pdf <numeros> [mes] [ano]")
                print("  ex: python main.py pdf 67")
                print("  ex: python main.py pdf 65-72,80 10 2026")

        elif comando == "indice":
            gerenciador.gerar_indice_pdfs()

        elif comando == "pdf-xml":
            if len(sys.argv) > 2:
                gerenciador.baixar_pdfs_de_xml(sys.argv[2])
            else:
                print("Uso: python main.py pdf-xml <arquivo.xml | pasta>")

        else:
            print("Uso:")
            print("  python main.py emitir <arquivo.xml>")
            print("  python main.py consultar <chave_acesso>")
            print("  python main.py cancelar <chave_acesso> <evento.xml>")
            print("  python main.py cancelar-assistido [arquivo_nfse.xml]")
            print("  python main.py lote [pasta]")
            print("  python main.py zip <arquivo.zip>")
            print("  python main.py pdf <numeros> [mes] [ano]")
            print("  python main.py pdf-xml <arquivo.xml | pasta>")
            print("  python main.py indice")
            print("")
            print("Opcoes:")
            print("  --dry-run  simula, sem emitir/baixar/mover arquivos")
            print("\nOu execute sem argumentos para menu interativo:")
            print("  python main.py")

    else:
        # Menu interativo
        menu_principal()
