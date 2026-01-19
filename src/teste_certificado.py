"""
Script para testar configuração do certificado e conexão
"""

import os
import json
import sys
from pathlib import Path


def testar_certificado():
    """Testa se o certificado está configurado corretamente"""

    print("="*60)
    print("TESTE DE CONFIGURAÇÃO - NFS-e")
    print("="*60)

    # 1. Verificar arquivo de configuração
    print("\n1. Verificando arquivo config.json...")
    if not os.path.exists("config.json"):
        print("   ✗ Arquivo config.json não encontrado!")
        print("   → Copie config.json.exemplo para config.json")
        return False

    try:
        with open("config.json", 'r', encoding='utf-8') as f:
            config = json.load(f)
        print("   ✓ config.json carregado com sucesso")
    except json.JSONDecodeError as e:
        print(f"   ✗ Erro ao ler config.json: {e}")
        return False

    # 2. Verificar certificado
    print("\n2. Verificando certificado digital...")
    cert_path = config.get("certificado", {}).get("caminho_cert", "")

    if not cert_path:
        print("   ✗ Caminho do certificado não configurado")
        print("   → Configure 'certificado.caminho_cert' em config.json")
        return False

    if not os.path.exists(cert_path):
        print(f"   ✗ Certificado não encontrado em: {cert_path}")
        print("   → Verifique o caminho ou converta para PEM")
        return False

    print(f"   ✓ Certificado encontrado: {cert_path}")

    # 3. Verificar tamanho do certificado
    tamanho = os.path.getsize(cert_path)
    print(f"   ✓ Tamanho: {tamanho} bytes")

    # 4. Verificar chave privada (se separada)
    print("\n3. Verificando chave privada...")
    chave_path = config.get("certificado", {}).get("caminho_chave", "")

    if chave_path:
        if not os.path.exists(chave_path):
            print(f"   ✗ Chave privada não encontrada: {chave_path}")
            return False
        print(f"   ✓ Chave privada encontrada: {chave_path}")
    else:
        print("   ℹ Chave privada não configurada (pode estar no mesmo arquivo do cert)")

    # 5. Verificar configurações da empresa
    print("\n4. Verificando configurações da empresa...")
    empresa = config.get("empresa", {})

    cnpj = empresa.get("cnpj", "")
    if not cnpj or len(cnpj.replace(".", "").replace("-", "")) != 14:
        print("   ✗ CNPJ não configurado ou inválido")
        return False
    print(f"   ✓ CNPJ: {cnpj}")

    inscricao = empresa.get("inscricao_municipal", "")
    if not inscricao:
        print("   ✗ Inscrição municipal não configurada")
        return False
    print(f"   ✓ Inscrição Municipal: {inscricao}")

    razao = empresa.get("razao_social", "")
    if not razao:
        print("   ✗ Razão social não configurada")
        return False
    print(f"   ✓ Razão Social: {razao}")

    # 6. Verificar ambientes
    print("\n5. Verificando configurações de ambiente...")
    ambiente = config.get("ambiente", "")

    if ambiente not in ["homologacao", "producao"]:
        print(f"   ✗ Ambiente inválido: {ambiente}")
        return False

    print(f"   ✓ Ambiente: {ambiente}")

    url_homo = config.get("url_homologacao", "")
    url_prod = config.get("url_producao", "")

    if url_homo:
        print(f"   ✓ URL Homologação: {url_homo}")
    if url_prod:
        print(f"   ✓ URL Produção: {url_prod}")

    # 7. Verificar caminhos de pastas
    print("\n6. Verificando caminhos das pastas...")
    nfse_config = config.get("nfse", {})

    pasta_entrada = nfse_config.get("caminho_xml_entrada", ".")
    print(f"   ℹ Pasta de entrada: {pasta_entrada}")

    pasta_saida = nfse_config.get("caminho_xml_saida", "./nfse_emitidas")
    print(f"   ℹ Pasta de saída: {pasta_saida}")

    # Criar pasta de saída se não existir
    os.makedirs(pasta_saida, exist_ok=True)
    print(f"   ✓ Pasta de saída criada/verificada")

    # 8. Testar importação de módulos
    print("\n7. Testando importação de módulos...")
    try:
        import requests
        print("   ✓ requests")
    except ImportError:
        print("   ✗ requests não instalado")
        print("   → Execute: pip install requests")
        return False

    try:
        from nfse_simples import ClienteNFSeSimples
        print("   ✓ nfse_simples")
    except ImportError as e:
        print(f"   ✗ Erro ao importar nfse_simples: {e}")
        return False

    try:
        from main import GerenciadorNFSe
        print("   ✓ main")
    except ImportError as e:
        print(f"   ✗ Erro ao importar main: {e}")
        return False

    # 9. Teste de conexão (opcional)
    print("\n8. Testando conexão com servidor...")
    try:
        import requests
        from requests.packages.urllib3.exceptions import InsecureRequestWarning
        requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

        url = config.get("url_homologacao", "https://producaorestrita.simplissweb.com.br")
        print(f"   Tentando conectar a: {url}")

        response = requests.get(f"{url}/swagger/index.html", timeout=10, verify=False)

        if response.status_code == 200:
            print("   ✓ Servidor SIMPLISS respondendo")
        else:
            print(f"   ⚠ Servidor respondeu com status {response.status_code}")

    except requests.exceptions.ConnectionError:
        print("   ⚠ Não foi possível conectar ao servidor (pode estar offline)")
    except Exception as e:
        print(f"   ⚠ Erro na conexão: {e}")

    # Resumo
    print("\n" + "="*60)
    print("✓ CONFIGURAÇÃO OK!")
    print("="*60)
    print("\nPróximos passos:")
    print("1. Gere um XML de teste do DPS em seu programa")
    print("2. Coloque em: " + pasta_entrada)
    print("3. Execute: python main.py emitir seu_dps.xml")
    print("\nOu use o menu interativo:")
    print("   python main.py")
    print("\n")

    return True


if __name__ == "__main__":
    sucesso = testar_certificado()
    sys.exit(0 if sucesso else 1)
