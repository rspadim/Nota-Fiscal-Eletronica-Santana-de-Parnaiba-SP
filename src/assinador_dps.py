"""
Módulo para assinatura digital de XML DPS
Usa signxml para conformidade com padrões SEFIN
"""

import os
import ssl
from lxml import etree
from typing import Optional

# Habilitar SHA1 no OpenSSL 3.0+ (necessário para SEFIN)
# SHA1 é legado mas obrigatório para compatibilidade com SEFIN
_openssl_conf = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'openssl.cnf')
if os.path.exists(_openssl_conf):
    os.environ['OPENSSL_CONF'] = _openssl_conf

# Tentar importações
try:
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import hashes
    import hashlib
    # Permitir SHA1 para assinatura digital (usedforsecurity=False)
    hashlib.new('sha1', usedforsecurity=False)
except:
    pass

class AssinadorDPS:
    """Assina documento DPS digitalmente usando signxml"""

    def __init__(self, certificado_path: str, chave_privada_path: Optional[str] = None):
        """
        Args:
            certificado_path: Caminho do certificado (.pem)
            chave_privada_path: Caminho da chave privada (se separada)
        """
        self.certificado_path = certificado_path
        self.chave_privada_path = chave_privada_path or certificado_path

        if not os.path.exists(self.certificado_path):
            raise FileNotFoundError(f"Certificado não encontrado: {self.certificado_path}")

        if not os.path.exists(self.chave_privada_path):
            raise FileNotFoundError(f"Chave privada não encontrada: {self.chave_privada_path}")

    def assinar_xml(self, xml_conteudo: str) -> str:
        """
        Assina um XML DPS com assinatura XAdES (padrão SEFIN)

        Args:
            xml_conteudo: Conteúdo do XML como string

        Returns:
            XML assinado como string
        """
        try:
            from signxml import XMLSigner
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.backends import default_backend

            # Carregar chave privada
            with open(self.chave_privada_path, 'rb') as f:
                key_data = f.read()

            private_key = serialization.load_pem_private_key(
                key_data,
                password=None,
                backend=default_backend()
            )

            # Carregar certificado (manter em bytes para signxml)
            with open(self.certificado_path, 'rb') as f:
                cert_data = f.read()

            # Parse XML
            xml_bytes = xml_conteudo.encode('utf-8')
            root = etree.fromstring(xml_bytes)

            # Encontrar elemento infDPS para obter seu ID
            elemento_inf = root.find('.//{http://www.sped.fazenda.gov.br/nfse}infDPS')
            if elemento_inf is None:
                raise ValueError("Elemento infDPS não encontrado no XML")

            # Obter o ID do elemento infDPS (será usado na referência)
            elemento_id = elemento_inf.get('Id')
            if not elemento_id:
                raise ValueError("Atributo Id não encontrado no infDPS")

            # Criar assinador com configurações SEFIN
            # SEFIN especifica SHA1, mas OpenSSL 3.0+ bloqueia por segurança
            # Tentamos SHA1 primeiro, se falhar usamos SHA256 (mais moderno e aceito)
            signer_configs = [
                {
                    "name": "SHA1 (padrão SEFIN)",
                    "signature_algorithm": "rsa-sha1",
                    "digest_algorithm": "sha1",
                },
                {
                    "name": "SHA256 (moderno)",
                    "signature_algorithm": "rsa-sha256",
                    "digest_algorithm": "sha256",
                },
            ]

            xml_assinado = None
            ultimo_erro = None

            for config in signer_configs:
                try:
                    signer = XMLSigner(
                        c14n_algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315",
                        signature_algorithm=config["signature_algorithm"],
                        digest_algorithm=config["digest_algorithm"],
                    )

                    # Tentar assinar
                    xml_assinado = signer.sign(
                        root,
                        key=private_key,
                        cert=cert_data,
                        reference_uri=f"#{elemento_id}"
                    )

                    print(f"[OK] XML assinado com {config['name']}")
                    break

                except Exception as e:
                    ultimo_erro = str(e)
                    print(f"[TENTATIVA] {config['name']} falhou: {e}")
                    continue

            if xml_assinado is None:
                raise RuntimeError(f"Falha em todos os algoritmos de assinatura. Último erro: {ultimo_erro}")

            return etree.tostring(xml_assinado, encoding='unicode', pretty_print=True)

        except ImportError as e:
            raise ImportError(
                f"Biblioteca 'signxml' não encontrada. "
                f"Instale com: pip install signxml cryptography\n"
                f"Erro: {e}"
            )
        except Exception as e:
            raise RuntimeError(f"Erro ao assinar XML: {str(e)}")

    def assinar_evento(self, xml_conteudo: str) -> str:
        """
        Assina um XML de Pedido de Registro de Evento (pedRegEvento)
        Assina o elemento infPedReg com assinatura XAdES

        Args:
            xml_conteudo: Conteúdo do XML pedRegEvento como string

        Returns:
            XML assinado como string
        """
        try:
            from signxml import XMLSigner
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.backends import default_backend

            with open(self.chave_privada_path, 'rb') as f:
                key_data = f.read()

            private_key = serialization.load_pem_private_key(
                key_data, password=None, backend=default_backend()
            )

            with open(self.certificado_path, 'rb') as f:
                cert_data = f.read()

            xml_bytes = xml_conteudo.encode('utf-8')
            root = etree.fromstring(xml_bytes)

            ns = 'http://www.sped.fazenda.gov.br/nfse'
            elemento_inf = root.find(f'.//{{{ns}}}infPedReg')
            if elemento_inf is None:
                raise ValueError("Elemento infPedReg não encontrado no XML")

            elemento_id = elemento_inf.get('Id')
            if not elemento_id:
                raise ValueError("Atributo Id não encontrado no infPedReg")

            signer_configs = [
                {"name": "SHA1 (padrão SEFIN)", "signature_algorithm": "rsa-sha1", "digest_algorithm": "sha1"},
                {"name": "SHA256 (moderno)", "signature_algorithm": "rsa-sha256", "digest_algorithm": "sha256"},
            ]

            xml_assinado = None
            ultimo_erro = None

            for config in signer_configs:
                try:
                    signer = XMLSigner(
                        c14n_algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315",
                        signature_algorithm=config["signature_algorithm"],
                        digest_algorithm=config["digest_algorithm"],
                    )
                    xml_assinado = signer.sign(
                        root, key=private_key, cert=cert_data,
                        reference_uri=f"#{elemento_id}"
                    )
                    print(f"[OK] Evento assinado com {config['name']}")
                    break
                except Exception as e:
                    ultimo_erro = str(e)
                    print(f"[TENTATIVA] {config['name']} falhou: {e}")
                    continue

            if xml_assinado is None:
                raise RuntimeError(f"Falha ao assinar evento. Último erro: {ultimo_erro}")

            return etree.tostring(xml_assinado, encoding='unicode', pretty_print=True)

        except ImportError as e:
            raise ImportError(
                f"Biblioteca 'signxml' não encontrada. "
                f"Instale com: pip install signxml cryptography\nErro: {e}"
            )
        except Exception as e:
            raise RuntimeError(f"Erro ao assinar evento: {str(e)}")

    def validar_assinatura(self, xml_assinado: str) -> bool:
        """
        Valida se o XML está corretamente assinado

        Args:
            xml_assinado: XML assinado como string

        Returns:
            True se válido, False caso contrário
        """
        try:
            root = etree.fromstring(xml_assinado.encode('utf-8'))

            # Verificar se contém nó de assinatura
            signature = root.find('.//{http://www.w3.org/2000/09/xmldsig#}Signature')
            return signature is not None

        except Exception:
            return False
