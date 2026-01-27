"""
Cliente para envio de NFS-e já gerada em XML
Alinhado com Swagger SIMPLISS v1.00
Perfeito quando o XML é gerado em outro programa
"""

import json
import gzip
import base64
import requests
from xml.etree import ElementTree as ET
from typing import Tuple, Dict, Optional
from datetime import datetime
import os
import time
from assinador_dps import AssinadorDPS


class ClienteNFSeSimples:
    """Cliente para enviar NFS-e alinhado com API SIMPLISS"""

    def __init__(self,
                 ambiente: str = "homologacao",
                 certificado_path: Optional[str] = None,
                 chave_privada_path: Optional[str] = None,
                 caminho_xml_enviados: Optional[str] = None,
                 salvar_xml_assinado: bool = True,
                 url_homologacao: Optional[str] = None,
                 url_producao: Optional[str] = None):
        """
        Args:
            ambiente: 'homologacao' ou 'producao'
            certificado_path: Caminho do certificado digital (.pem)
            chave_privada_path: Caminho da chave privada (opcional)
            caminho_xml_enviados: Pasta para salvar XMLs assinados (opcional)
            salvar_xml_assinado: Se deve salvar cópia assinada antes de enviar
            url_homologacao: URL do servidor de homologação (do config.json)
            url_producao: URL do servidor de produção (do config.json)
        """
        self.ambiente = ambiente
        self.certificado_path = certificado_path
        self.chave_privada_path = chave_privada_path
        self.caminho_xml_enviados = caminho_xml_enviados or "./nfse_enviadas"
        self.salvar_xml_assinado = salvar_xml_assinado
        self.tipo_ambiente = 2 if ambiente == "homologacao" else 1

        # URLs do config.json ou defaults
        url_homologacao = url_homologacao or "https://producaorestrita.simplissweb.com.br"
        url_producao = url_producao or "https://nfsesantanadeparnaiba.simplissweb.com.br"

        if ambiente == "homologacao":
            self.base_url = url_homologacao
        else:
            self.base_url = url_producao

        # Configurar sessão com certificado
        self.session = self._criar_sessao()

    def _criar_sessao(self) -> requests.Session:
        """Cria sessão com autenticação por certificado"""
        session = requests.Session()

        if self.certificado_path and os.path.exists(self.certificado_path):
            cert = (self.certificado_path,
                    self.chave_privada_path or self.certificado_path)
            session.cert = cert

        return session

    def emitir_nfse_xml(self, arquivo_xml: str) -> Tuple[bool, Dict]:
        """
        Emite uma NFS-e enviando arquivo XML já pronto

        Args:
            arquivo_xml: Caminho do arquivo XML ou conteúdo em string

        Returns:
            (sucesso, resposta_dict)
        """
        try:
            # Ler arquivo se for caminho
            if arquivo_xml.startswith('<'):
                xml_content = arquivo_xml
            else:
                with open(arquivo_xml, 'r', encoding='utf-8') as f:
                    xml_content = f.read()

            # Validar XML
            try:
                ET.fromstring(xml_content)
            except ET.ParseError as e:
                return False, {"erro": f"XML inválido: {str(e)}"}

            # ===== NOVA: Assinar XML =====
            if self.certificado_path and os.path.exists(self.certificado_path):
                print("[INFO] Assinando XML com certificado digital...")
                try:
                    assinador = AssinadorDPS(
                        self.certificado_path,
                        self.chave_privada_path
                    )
                    xml_content = assinador.assinar_xml(xml_content)
                    print("[OK] XML assinado com sucesso!")
                except Exception as e:
                    print(f"[ERRO] Falha ao assinar XML: {e}")
                    return False, {"erro": f"Falha ao assinar: {str(e)}"}
            else:
                print("[AVISO] Certificado não configurado. Enviando XML sem assinatura...")

            # ===== NOVA: Salvar cópia assinada antes de enviar =====
            if self.salvar_xml_assinado:
                self._salvar_xml_enviado(xml_content, arquivo_xml)

            # Compactar em GZip
            xml_bytes = xml_content.encode('utf-8')
            xml_compactado = gzip.compress(xml_bytes)

            # Codificar em base64
            xml_base64 = base64.b64encode(xml_compactado).decode('utf-8')

            # Preparar requisição (campo correto do Swagger)
            payload = {"dpsXmlGZipB64": xml_base64}
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json"
            }

            # Enviar
            url = f"{self.base_url}/nfse"
            print(f"Enviando para: {url}")

            response = self.session.post(url, json=payload, headers=headers, verify=True)

            # Processar resposta (aceita 201 como sucesso)
            return self._processar_resposta_emissao(response)

        except FileNotFoundError:
            return False, {"erro": f"Arquivo não encontrado: {arquivo_xml}"}
        except Exception as e:
            return False, {"erro": str(e)}

    def consultar_nfse(self, chave_acesso: str) -> Tuple[bool, Dict]:
        """
        Consulta uma NFS-e pela chave de acesso

        Args:
            chave_acesso: Chave de acesso (50 posições)

        Returns:
            (sucesso, dados)
        """
        try:
            headers = {"Accept": "application/json"}
            url = f"{self.base_url}/nfse/{chave_acesso}"

            print(f"Consultando: {url}")
            response = self.session.get(url, headers=headers, verify=True)

            return self._processar_resposta_consulta(response)

        except Exception as e:
            return False, {"erro": str(e)}

    def cancelar_nfse(self, chave_acesso: str, arquivo_evento: str) -> Tuple[bool, Dict]:
        """
        Cancela uma NFS-e usando arquivo de evento XML

        Args:
            chave_acesso: Chave de acesso da NFS-e
            arquivo_evento: Caminho ou conteúdo XML do evento

        Returns:
            (sucesso, resposta)
        """
        try:
            # Ler arquivo se for caminho
            if arquivo_evento.startswith('<'):
                xml_content = arquivo_evento
            else:
                with open(arquivo_evento, 'r', encoding='utf-8') as f:
                    xml_content = f.read()

            # Compactar e codificar
            xml_bytes = xml_content.encode('utf-8')
            xml_compactado = gzip.compress(xml_bytes)
            xml_base64 = base64.b64encode(xml_compactado).decode('utf-8')

            # Preparar requisição (campo correto do Swagger)
            payload = {"pedidoRegistroEventoXmlGZipB64": xml_base64}
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json"
            }

            url = f"{self.base_url}/nfse/{chave_acesso}/eventos"
            print(f"Cancelando em: {url}")

            response = self.session.post(url, json=payload, headers=headers, verify=True)

            return self._processar_resposta_evento(response)

        except Exception as e:
            return False, {"erro": str(e)}

    def consultar_evento(self, chave_acesso: str, tipo_evento: int, num_seq_evento: int) -> Tuple[bool, Dict]:
        """
        Consulta um evento específico

        Args:
            chave_acesso: Chave de acesso da NFS-e (50 posições)
            tipo_evento: Tipo do evento (ex: 101101 para cancelamento)
            num_seq_evento: Número sequencial do evento

        Returns:
            (sucesso, dados)
        """
        try:
            headers = {"Accept": "application/json"}
            url = f"{self.base_url}/nfse/{chave_acesso}/eventos/{tipo_evento}/{num_seq_evento}"

            print(f"Consultando evento: {url}")
            response = self.session.get(url, headers=headers, verify=True)

            return self._processar_resposta_evento_get(response)

        except Exception as e:
            return False, {"erro": str(e)}

    def _processar_resposta_emissao(self, response: requests.Response) -> Tuple[bool, Dict]:
        """Processa resposta de emissão (POST /nfse)"""
        try:
            # Aceita 201 Created (sucesso) ou 200 OK
            if response.status_code in [200, 201]:
                data = response.json()

                # Descompactar XML da resposta
                if "nfseXmlGZipB64" in data:
                    try:
                        xml_base64 = data["nfseXmlGZipB64"]
                        xml_compactado = base64.b64decode(xml_base64)
                        xml_nfse = gzip.decompress(xml_compactado).decode('utf-8')

                        # Preparar resposta formatada
                        info = {
                            "sucesso": True,
                            "status_code": response.status_code,
                            "tipoAmbiente": data.get("tipoAmbiente"),
                            "versaoAplicativo": data.get("versaoAplicativo"),
                            "dataHoraProcessamento": data.get("dataHoraProcessamento"),
                            "idDps": data.get("idDps"),
                            "chaveAcesso": data.get("chaveAcesso"),
                            "xml": xml_nfse,
                        }

                        # Adicionar alertas se existirem
                        if "alertas" in data and data["alertas"]:
                            info["alertas"] = data["alertas"]

                        # Tentar extrair identificadores únicos do XML
                        try:
                            root = ET.fromstring(xml_nfse)

                            # Extrair ID completo do atributo 'Id' de infNFSe (ex: NFS35473041210280942000124000000000000626013217816921)
                            infnfse = root.find(".//{http://www.sped.fazenda.gov.br/nfse}infNFSe")
                            if infnfse is not None:
                                id_completo = infnfse.get('Id')
                                if id_completo:
                                    info["id_nfse"] = id_completo

                            # Extrair número da NFS-e (nNFSe)
                            nfse_num = root.findtext(".//{http://www.sped.fazenda.gov.br/nfse}nNFSe")
                            if nfse_num:
                                info["numero_nfse"] = nfse_num

                            # Extrair número único RPS (nDFSe)
                            dfs_num = root.findtext(".//{http://www.sped.fazenda.gov.br/nfse}nDFSe")
                            if dfs_num:
                                info["numero_dfs"] = dfs_num
                        except:
                            pass

                        return True, info

                    except Exception as e:
                        return True, data

                return True, data

            else:
                # Erro na requisição
                try:
                    erro_data = response.json()
                except:
                    erro_data = {"mensagem": response.text or response.reason}

                return False, {
                    "sucesso": False,
                    "status_code": response.status_code,
                    "erro": erro_data
                }

        except Exception as e:
            return False, {"erro": f"Erro ao processar resposta: {str(e)}"}

    def _processar_resposta_consulta(self, response: requests.Response) -> Tuple[bool, Dict]:
        """Processa resposta de consulta (GET /nfse/{chave})"""
        try:
            if response.status_code == 200:
                data = response.json()

                # Descompactar XML se existir
                if "nfseXmlGZipB64" in data:
                    try:
                        xml_base64 = data["nfseXmlGZipB64"]
                        xml_compactado = base64.b64decode(xml_base64)
                        xml_nfse = gzip.decompress(xml_compactado).decode('utf-8')

                        info = {
                            "sucesso": True,
                            "tipoAmbiente": data.get("tipoAmbiente"),
                            "versaoAplicativo": data.get("versaoAplicativo"),
                            "dataHoraProcessamento": data.get("dataHoraProcessamento"),
                            "chaveAcesso": data.get("chaveAcesso"),
                            "xml": xml_nfse,
                        }
                        return True, info

                    except Exception:
                        return True, data

                return True, data

            else:
                try:
                    erro_data = response.json()
                except:
                    erro_data = {"mensagem": response.text or response.reason}

                return False, {
                    "status_code": response.status_code,
                    "erro": erro_data
                }

        except Exception as e:
            return False, {"erro": f"Erro ao processar resposta: {str(e)}"}

    def _processar_resposta_evento(self, response: requests.Response) -> Tuple[bool, Dict]:
        """Processa resposta de evento (POST /nfse/{chave}/eventos)"""
        try:
            if response.status_code in [200, 201]:
                data = response.json()

                # Descompactar XML da resposta
                if "eventoXmlGZipB64" in data:
                    try:
                        xml_base64 = data["eventoXmlGZipB64"]
                        xml_compactado = base64.b64decode(xml_base64)
                        xml_evento = gzip.decompress(xml_compactado).decode('utf-8')

                        info = {
                            "sucesso": True,
                            "tipoAmbiente": data.get("tipoAmbiente"),
                            "versaoAplicativo": data.get("versaoAplicativo"),
                            "dataHoraProcessamento": data.get("dataHoraProcessamento"),
                            "xml": xml_evento,
                        }
                        return True, info

                    except Exception:
                        return True, data

                return True, data

            else:
                try:
                    erro_data = response.json()
                except:
                    erro_data = {"mensagem": response.text or response.reason}

                return False, {
                    "status_code": response.status_code,
                    "erro": erro_data
                }

        except Exception as e:
            return False, {"erro": f"Erro ao processar resposta: {str(e)}"}

    def _processar_resposta_evento_get(self, response: requests.Response) -> Tuple[bool, Dict]:
        """Processa resposta de consulta de evento (GET /nfse/{chave}/eventos/{tipo}/{seq})"""
        try:
            if response.status_code == 200:
                data = response.json()

                # Descompactar XML se existir
                if "eventoXmlGZipB64" in data:
                    try:
                        xml_base64 = data["eventoXmlGZipB64"]
                        xml_compactado = base64.b64decode(xml_base64)
                        xml_evento = gzip.decompress(xml_compactado).decode('utf-8')

                        info = {
                            "sucesso": True,
                            "tipoAmbiente": data.get("tipoAmbiente"),
                            "versaoAplicativo": data.get("versaoAplicativo"),
                            "dataHoraProcessamento": data.get("dataHoraProcessamento"),
                            "xml": xml_evento,
                        }
                        return True, info

                    except Exception:
                        return True, data

                return True, data

            else:
                try:
                    erro_data = response.json()
                except:
                    erro_data = {"mensagem": response.text or response.reason}

                return False, {
                    "status_code": response.status_code,
                    "erro": erro_data
                }

        except Exception as e:
            return False, {"erro": f"Erro ao processar resposta: {str(e)}"}

    def _salvar_xml_enviado(self, xml_assinado: str, arquivo_origem: str) -> str:
        """
        Salva cópia do XML assinado antes de enviar (auditoria)
        Organiza em subpastas por data (YYYYMMDD)
        Nomeia com timestamp + nanosegundos para evitar sobrescrita

        Args:
            xml_assinado: Conteúdo XML assinado
            arquivo_origem: Caminho do arquivo original

        Returns:
            Caminho do arquivo salvo
        """
        try:
            # Gerar timestamp com nanosegundos para evitar sobrescrita
            agora = datetime.now()
            data_pasta = agora.strftime("%Y%m%d")  # Subpasta: 20260127
            timestamp = agora.strftime("%Y%m%d_%H%M%S")
            nanosegundos = time.time_ns() % 1_000_000_000
            timestamp_completo = f"{timestamp}_{nanosegundos:09d}"

            # Criar pasta com data (nfse_enviadas/20260127)
            pasta_data = os.path.join(self.caminho_xml_enviados, data_pasta)
            os.makedirs(pasta_data, exist_ok=True)

            # Gerar nome do arquivo baseado na origem
            if isinstance(arquivo_origem, str) and arquivo_origem.startswith('<'):
                # Se é string XML, gerar nome com timestamp
                nome_base = f"dps_{timestamp_completo}"
            else:
                # Usar nome do arquivo original sem extensão
                nome_base = os.path.splitext(os.path.basename(arquivo_origem))[0]

            # Arquivo com formato: {nome_base}.YYYYMMDD_HHMMSS_nanosegundos.sign.xml
            nome_arquivo = os.path.join(pasta_data, f"{nome_base}.{timestamp_completo}.sign.xml")

            # Salvar XML assinado
            with open(nome_arquivo, 'w', encoding='utf-8') as f:
                f.write(xml_assinado)

            print(f"[OK] XML assinado salvo em: {nome_arquivo}")
            return nome_arquivo

        except Exception as e:
            print(f"[AVISO] Não foi possível salvar cópia assinada: {e}")
            return None

    def salvar_resposta_xml(self, xml: str, nome_arquivo: str = None) -> str:
        """
        Salva XML da resposta em arquivo
        Organiza em subpastas por data (YYYYMMDD)

        Args:
            xml: Conteúdo XML
            nome_arquivo: Nome do arquivo com caminho (gerado automaticamente se não informado)

        Returns:
            Caminho do arquivo salvo
        """
        # Gerar data da subpasta
        agora = datetime.now()
        data_pasta = agora.strftime("%Y%m%d")  # Subpasta: 20260127

        if not nome_arquivo:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            nome_arquivo = f"nfse_{timestamp}.xml"

        # Extrair diretório e nome do arquivo
        if os.path.isabs(nome_arquivo):
            # Se é caminho absoluto, extrair pasta base e nome
            diretorio_base = os.path.dirname(nome_arquivo)
            nome_arquivo_apenas = os.path.basename(nome_arquivo)
        else:
            # Se é relativo, usar diretório atual
            diretorio_base = os.getcwd()
            nome_arquivo_apenas = nome_arquivo

        # Criar subpasta com data (ex: nfse_emitidas/20260127)
        pasta_data = os.path.join(diretorio_base, data_pasta)
        os.makedirs(pasta_data, exist_ok=True)

        # Caminho completo do arquivo na subpasta
        caminho_completo = os.path.join(pasta_data, nome_arquivo_apenas)

        # Formatar XML para legibilidade
        try:
            root = ET.fromstring(xml)
            self._indenta_elemento(root)
            xml_formatado = ET.tostring(root, encoding='unicode')
        except:
            xml_formatado = xml

        # Salvar
        with open(caminho_completo, 'w', encoding='utf-8') as f:
            f.write(xml_formatado)

        print(f"✓ XML salvo em: {caminho_completo}")
        return caminho_completo

    @staticmethod
    def _indenta_elemento(elem, nivel=0):
        """Adiciona indentação para legibilidade"""
        indent = "\n" + "  " * nivel
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = indent + "  "
            if not elem.tail or not elem.tail.strip():
                elem.tail = indent
            for filho in elem:
                ClienteNFSeSimples._indenta_elemento(filho, nivel + 1)
            if not filho.tail or not filho.tail.strip():
                filho.tail = indent
        else:
            if nivel and (not elem.tail or not elem.tail.strip()):
                elem.tail = indent
