"""
Cliente para emissão de Nota Fiscal de Serviços Eletrônica (NFS-e)
Prefeitura de Santana de Parnaíba - SIMPLISS
Conforme Manual de Integração v1.00
"""

import json
import gzip
import base64
import requests
from xml.etree import ElementTree as ET
from datetime import datetime
from typing import Dict, Optional, Tuple
import ssl
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context


class NFSeConfig:
    """Configurações de conexão com o servidor SIMPLISS"""

    def __init__(self,
                 ambiente: str = "homologacao",
                 certificado_path: str = None,
                 chave_privada_path: str = None,
                 senha_certificado: str = None):
        """
        Args:
            ambiente: 'homologacao' ou 'producao'
            certificado_path: Caminho para o arquivo .pem ou .pfx do certificado
            chave_privada_path: Caminho para a chave privada (se separada do cert)
            senha_certificado: Senha do certificado (se necessário)
        """
        self.ambiente = ambiente
        self.certificado_path = certificado_path
        self.chave_privada_path = chave_privada_path
        self.senha_certificado = senha_certificado

        if ambiente == "homologacao":
            self.base_url = "https://producaorestrita.simplissweb.com.br"
        else:
            self.base_url = "https://producao.simplissweb.com.br"  # A ser confirmado


class NFSeEmitter:
    """Cliente para emitir, consultar e cancelar NFS-e"""

    def __init__(self, config: NFSeConfig):
        """
        Inicializa o cliente NFS-e

        Args:
            config: Instância de NFSeConfig com as configurações
        """
        self.config = config
        self.session = self._criar_sessao_segura()

    def _criar_sessao_segura(self) -> requests.Session:
        """Cria uma sessão com suporte a TLS 1.2 e certificado mútuo"""
        session = requests.Session()

        # Configurar adaptador com certificado
        adapter = HTTPAdapter()

        # Se temos certificado, usar autenticação mútua
        if self.config.certificado_path:
            # Formato: (certificado, chave_privada)
            cert = (self.config.certificado_path,
                    self.config.chave_privada_path or self.config.certificado_path)
            adapter.cert = cert

        session.mount('https://', adapter)
        return session

    def emitir_nfse(self, dps_dict: Dict) -> Tuple[bool, Dict]:
        """
        Emite uma NFS-e enviando uma DPS

        Args:
            dps_dict: Dicionário com os dados da Declaração de Prestação de Serviço

        Returns:
            Tupla (sucesso, resposta)
            - sucesso: True se a emissão foi bem-sucedida
            - resposta: Dicionário com dados da NFS-e ou erros
        """
        try:
            # Gerar XML da DPS
            xml_dps = self._gerar_xml_dps(dps_dict)

            # Assinar XML da DPS
            xml_assinado = self._assinar_xml(xml_dps)

            # Compactar em GZip e codificar em base64
            xml_compactado = gzip.compress(xml_assinado.encode('utf-8'))
            xml_base64 = base64.b64encode(xml_compactado).decode('utf-8')

            # Preparar payload JSON
            payload = {
                "arquivo": xml_base64
            }

            # Fazer requisição POST
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json"
            }

            url = f"{self.config.base_url}/api/v1/nfse"
            response = self.session.post(url, json=payload, headers=headers, verify=True)

            return self._processar_resposta_emissao(response)

        except Exception as e:
            return False, {"erro": str(e)}

    def consultar_nfse(self, chave_acesso: str) -> Tuple[bool, Dict]:
        """
        Consulta uma NFS-e pela chave de acesso

        Args:
            chave_acesso: Chave de acesso da NFS-e (formato: XX XXXXXXXXX XXXXXXX XXXXXXX)

        Returns:
            Tupla (sucesso, nfse_data)
        """
        try:
            headers = {
                "Accept": "application/json"
            }

            url = f"{self.config.base_url}/api/v1/nfse/{chave_acesso}"
            response = self.session.get(url, headers=headers, verify=True)

            return self._processar_resposta_consulta(response)

        except Exception as e:
            return False, {"erro": str(e)}

    def cancelar_nfse(self, chave_acesso: str, motivo_cancelamento: str) -> Tuple[bool, Dict]:
        """
        Cancela uma NFS-e existente

        Args:
            chave_acesso: Chave de acesso da NFS-e
            motivo_cancelamento: Motivo do cancelamento

        Returns:
            Tupla (sucesso, resposta)
        """
        try:
            # Gerar XML do evento de cancelamento
            evento_dict = {
                "tipoEvento": "101101",  # Cancelamento
                "descricaoEvento": motivo_cancelamento,
                "dataEvento": datetime.now().isoformat()
            }

            xml_evento = self._gerar_xml_evento(chave_acesso, evento_dict)

            # Assinar XML
            xml_assinado = self._assinar_xml(xml_evento)

            # Compactar e codificar
            xml_compactado = gzip.compress(xml_assinado.encode('utf-8'))
            xml_base64 = base64.b64encode(xml_compactado).decode('utf-8')

            payload = {
                "arquivo": xml_base64
            }

            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json"
            }

            url = f"{self.config.base_url}/api/v1/nfse/{chave_acesso}/eventos"
            response = self.session.post(url, json=payload, headers=headers, verify=True)

            return self._processar_resposta_evento(response)

        except Exception as e:
            return False, {"erro": str(e)}

    def _gerar_xml_dps(self, dps_dict: Dict) -> str:
        """Gera XML da DPS a partir de um dicionário"""
        # Elemento raiz
        root = ET.Element("DPS")
        root.set("xmlns", "http://www.abrasf.org.br/nfse")

        # Informações do Prestador de Serviço
        prestador = ET.SubElement(root, "Prestador")
        ET.SubElement(prestador, "CpfCnpj").text = dps_dict.get("cnpj_prestador", "")
        ET.SubElement(prestador, "InscricaoMunicipal").text = dps_dict.get("inscricao_municipal", "")

        # Informações do Tomador de Serviço
        tomador = ET.SubElement(root, "Tomador")
        ET.SubElement(tomador, "CpfCnpj").text = dps_dict.get("cnpj_tomador", "")
        ET.SubElement(tomador, "RazaoSocial").text = dps_dict.get("razao_social_tomador", "")

        # Informações do Serviço
        servico = ET.SubElement(root, "Servico")
        ET.SubElement(servico, "Valores").text = str(dps_dict.get("valor_servico", 0))
        ET.SubElement(servico, "ItemServico").text = dps_dict.get("codigo_servico", "")
        ET.SubElement(servico, "Descricao").text = dps_dict.get("descricao_servico", "")
        ET.SubElement(servico, "DataEmissao").text = dps_dict.get("data_emissao", datetime.now().isoformat())

        # Converter para string
        xml_string = ET.tostring(root, encoding='unicode')
        return self._formatar_xml(xml_string)

    def _gerar_xml_evento(self, chave_acesso: str, evento_dict: Dict) -> str:
        """Gera XML do evento de cancelamento"""
        root = ET.Element("PedidoRegistroEvento")
        root.set("xmlns", "http://www.abrasf.org.br/nfse")

        # Informações do evento
        ET.SubElement(root, "ChaveAcesso").text = chave_acesso
        ET.SubElement(root, "TipoEvento").text = evento_dict.get("tipoEvento", "101101")
        ET.SubElement(root, "DescricaoEvento").text = evento_dict.get("descricaoEvento", "")
        ET.SubElement(root, "DataEvento").text = evento_dict.get("dataEvento", datetime.now().isoformat())

        xml_string = ET.tostring(root, encoding='unicode')
        return self._formatar_xml(xml_string)

    def _assinar_xml(self, xml_string: str) -> str:
        """
        Assina um XML usando o certificado digital (implementação básica)

        Nota: Para produção, utilize bibliotecas como 'xmlsec' ou 'signxml'
        """
        # Esta é uma implementação simplificada
        # Em produção, use: pip install signxml
        try:
            from signxml import XMLSigner

            xml_bytes = xml_string.encode('utf-8')
            signer = XMLSigner(c14n_algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315")

            # Carregar certificado
            with open(self.config.certificado_path, 'rb') as f:
                cert_data = f.read()

            signed_root = signer.sign(xml_bytes, key=cert_data)
            return ET.tostring(signed_root, encoding='unicode')

        except ImportError:
            # Se signxml não estiver instalado, retornar XML sem assinatura (apenas para teste)
            print("Aviso: signxml não instalado. Para produção, execute: pip install signxml")
            return xml_string

    def _formatar_xml(self, xml_string: str) -> str:
        """Formata XML com indentação adequada"""
        try:
            root = ET.fromstring(xml_string)
            self._indenta_xml(root)
            return ET.tostring(root, encoding='unicode')
        except:
            return xml_string

    def _indenta_xml(self, elem, level=0):
        """Adiciona indentação ao XML"""
        indent = "\n" + level * "  "
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = indent + "  "
            if not elem.tail or not elem.tail.strip():
                elem.tail = indent
            for child in elem:
                self._indenta_xml(child, level + 1)
            if not child.tail or not child.tail.strip():
                child.tail = indent
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = indent

    def _processar_resposta_emissao(self, response: requests.Response) -> Tuple[bool, Dict]:
        """Processa resposta da emissão de NFS-e"""
        try:
            if response.status_code == 200:
                data = response.json()

                # Se há arquivo compactado, descompactar
                if "arquivo" in data:
                    xml_base64 = data["arquivo"]
                    xml_compactado = base64.b64decode(xml_base64)
                    xml_nfse = gzip.decompress(xml_compactado).decode('utf-8')

                    # Extrair informações da NFS-e
                    root = ET.fromstring(xml_nfse)
                    nfse_numero = root.findtext(".//Numero")
                    chave_acesso = root.findtext(".//ChaveAcesso")

                    return True, {
                        "sucesso": True,
                        "numero_nfse": nfse_numero,
                        "chave_acesso": chave_acesso,
                        "xml": xml_nfse
                    }

                return True, data
            else:
                erro = response.json() if response.text else {"erro": response.reason}
                return False, erro

        except Exception as e:
            return False, {"erro": f"Erro ao processar resposta: {str(e)}"}

    def _processar_resposta_consulta(self, response: requests.Response) -> Tuple[bool, Dict]:
        """Processa resposta da consulta de NFS-e"""
        try:
            if response.status_code == 200:
                data = response.json()

                # Descompactar XML se necessário
                if "arquivo" in data:
                    xml_base64 = data["arquivo"]
                    xml_compactado = base64.b64decode(xml_base64)
                    xml_nfse = gzip.decompress(xml_compactado).decode('utf-8')
                    return True, {"xml": xml_nfse, "dados": data}

                return True, data
            else:
                erro = response.json() if response.text else {"erro": response.reason}
                return False, erro

        except Exception as e:
            return False, {"erro": f"Erro ao processar resposta: {str(e)}"}

    def _processar_resposta_evento(self, response: requests.Response) -> Tuple[bool, Dict]:
        """Processa resposta de evento (cancelamento)"""
        return self._processar_resposta_emissao(response)
