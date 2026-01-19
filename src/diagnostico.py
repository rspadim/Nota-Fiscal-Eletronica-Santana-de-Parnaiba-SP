"""
Script de diagnóstico para problemas de conexão com SIMPLISS
Testa certificado, SSL, e endpoints
"""

import os
import sys
import json
import requests
import ssl
import urllib3
from pathlib import Path

# Desabilitar warnings de SSL (apenas para diagnóstico)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def print_header(titulo):
    print("\n" + "="*60)
    print(titulo)
    print("="*60)

def check_certificado():
    """Verifica se o certificado existe e é válido"""
    print_header("1. VERIFICAÇÃO DE CERTIFICADO")

    try:
        with open("config.json", 'r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception as e:
        print(f"[ERRO] Erro ao ler config.json: {e}")
        return False

    cert_path = config.get("certificado", {}).get("caminho_cert")

    if not cert_path:
        print("[ERRO] Caminho do certificado não configurado")
        return False

    if not os.path.exists(cert_path):
        print(f"[ERRO] Certificado não encontrado: {cert_path}")
        return False

    print(f"[OK] Certificado encontrado: {cert_path}")

    # Verificar tamanho
    size = os.path.getsize(cert_path)
    print(f"     Tamanho: {size} bytes")

    # Tentar ler conteúdo
    try:
        with open(cert_path, 'r') as f:
            content = f.read()
            if "BEGIN CERTIFICATE" in content or "BEGIN RSA PRIVATE KEY" in content:
                print("[OK] Formato PEM valido detectado")
            else:
                print("[AVISO] Formato PEM pode estar incorreto")
        return True
    except Exception as e:
        print(f"[ERRO] Erro ao ler certificado: {e}")
        return False

def test_ssl_handshake():
    """Testa handshake SSL/TLS com o servidor"""
    print_header("2. TESTE DE CONEXÃO SSL/TLS")

    url = "https://producaorestrita.simplissweb.com.br"

    try:
        # Teste sem certificado de cliente primeiro
        print("Testando conexão básica (sem certificado)...")
        response = requests.get(url, timeout=5, verify=False)
        print(f"[OK] Conexão básica OK (status: {response.status_code})")
    except Exception as e:
        print(f"[AVISO] Conexão básica falhou: {e}")

    # Teste com certificado
    try:
        with open("config.json", 'r', encoding='utf-8') as f:
            config = json.load(f)
        cert_path = config.get("certificado", {}).get("caminho_cert")

        print(f"Testando com certificado de cliente...")
        response = requests.get(url, cert=cert_path, timeout=5, verify=False)
        print(f"[OK] Conexão com certificado OK (status: {response.status_code})")
    except Exception as e:
        print(f"[ERRO] Conexão com certificado falhou: {e}")

def test_api_endpoint():
    """Testa os endpoints da API"""
    print_header("3. TESTE DE ENDPOINTS API")

    try:
        with open("config.json", 'r', encoding='utf-8') as f:
            config = json.load(f)
    except:
        print("[ERRO] Erro ao ler config.json")
        return

    cert_path = config.get("certificado", {}).get("caminho_cert")
    base_url = "https://producaorestrita.simplissweb.com.br/api/v1"

    endpoints = [
        ("GET", "/nfse/teste", "Teste de GET (erro esperado)"),
        ("POST", "/nfse", "Teste de POST (sem dados)"),
    ]

    for method, endpoint, desc in endpoints:
        url = base_url + endpoint
        print(f"\nTestando: {desc}")
        print(f"  Método: {method}")
        print(f"  URL: {url}")

        try:
            headers = {"Content-Type": "application/json", "Accept": "application/json"}

            if method == "GET":
                response = requests.get(url, cert=cert_path, headers=headers, timeout=5, verify=False)
            else:
                response = requests.post(url, cert=cert_path, json={}, headers=headers, timeout=5, verify=False)

            print(f"  Status: {response.status_code}")
            print(f"  Resposta: {response.text[:200]}")

            if response.status_code == 404:
                print("  [AVISO] Endpoint retornou 404 - pode estar incorreto")
            elif response.status_code in [200, 201]:
                print("  [OK] Endpoint respondeu")
            else:
                print(f"  [AVISO] Status inesperado: {response.status_code}")

        except Exception as e:
            print(f"  [ERRO] Erro: {e}")

def test_payload_format():
    """Testa formatação do payload"""
    print_header("4. TESTE DE FORMATO DO PAYLOAD")

    xml_test = '<?xml version="1.0" encoding="UTF-8"?><test>teste</test>'

    import gzip
    import base64

    print("XML de teste:", xml_test[:50])

    # Compactar
    xml_bytes = xml_test.encode('utf-8')
    xml_compactado = gzip.compress(xml_bytes)
    print(f"Tamanho após gzip: {len(xml_compactado)} bytes")

    # Codificar
    xml_base64 = base64.b64encode(xml_compactado).decode('utf-8')
    print(f"Base64 (primeiros 50 chars): {xml_base64[:50]}")

    # Montar payload
    payload = {"dpsXmlGZipB64": xml_base64}
    print(f"Payload JSON size: {len(json.dumps(payload))} bytes")
    print("[OK] Formatação de payload OK")

def test_xml_samples():
    """Lista arquivos XML de entrada disponíveis"""
    print_header("5. ARQUIVOS XML DISPONÍVEIS")

    xml_dir = "../nfse_entrada"

    if not os.path.isdir(xml_dir):
        print(f"[ERRO] Diretório não encontrado: {xml_dir}")
        return

    xml_files = list(Path(xml_dir).glob("*.xml"))

    if not xml_files:
        print(f"[ERRO] Nenhum arquivo XML encontrado em {xml_dir}")
        return

    print(f"Total de arquivos: {len(xml_files)}\n")

    for arquivo in xml_files[:5]:  # Mostrar primeiros 5
        size = os.path.getsize(arquivo)
        print(f"  • {arquivo.name} ({size} bytes)")

    if len(xml_files) > 5:
        print(f"  ... e mais {len(xml_files) - 5} arquivo(s)")

def main():
    """Executa todos os testes"""
    print("\n" + "="*60)
    print("  DIAGNÓSTICO DE CONEXÃO SIMPLISS NFS-e")
    print("="*60)

    check_certificado()
    test_ssl_handshake()
    test_api_endpoint()
    test_payload_format()
    test_xml_samples()

    print_header("RESUMO")
    print("""
Sugestões de resolução de problemas:

1. Se receber 404 ("Not Found"):
   - Verifique se a URL está correta
   - Tente sem certificado de cliente primeiro
   - Verifique logs do servidor
   - A URL pode exigir autenticação adicional

2. Se certificado falhar:
   - Certifique-se que é arquivo PEM válido
   - Pode precisar separar cert e chave
   - Verifique permissões do arquivo
   - Tente converter para formato correto

3. Se tudo falhar:
   - Teste com cURL:
     curl --cert certificado_spa.pem -k https://producaorestrita.simplissweb.com.br/api/v1/nfse
   - Ative logs de debug no requests
   - Contate suporte SIMPLISS
    """)

if __name__ == "__main__":
    main()
