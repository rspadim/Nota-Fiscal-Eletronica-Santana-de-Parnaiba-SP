"""
Script para testar diferentes URLs e endpoints da API SIMPLISS
Ajuda a identificar qual é a URL correta
"""

import requests
import json
import os

def testar_urls():
    """Testa diferentes URLs possíveis"""

    # Carregar config
    with open("config.json", 'r', encoding='utf-8') as f:
        config = json.load(f)

    cert_path = config.get("certificado", {}).get("caminho_cert")

    # URLs a testar (base e endpoints)
    bases = [
        "https://producaorestrita.simplissweb.com.br/api/v1",
        "https://producaorestrita.simplissweb.com.br/api/v2",
        "https://producaorestrita.simplissweb.com.br/api",
        "https://producaorestrita.simplissweb.com.br",
        "https://simplissweb.com.br/api/v1",
    ]

    endpoints = [
        "/nfse",
        "/dps",
        "/nfse/",
        "/dps/",
        "/nfse/teste",
        "/api/nfse",
    ]

    print("="*70)
    print("TESTANDO URLs E ENDPOINTS ALTERNATIVOS")
    print("="*70)
    print()

    for base in bases:
        print(f"\nBase: {base}")
        print("-" * 70)

        for endpoint in endpoints:
            url = base + endpoint

            try:
                # GET simples
                response = requests.get(
                    url,
                    cert=cert_path if os.path.exists(cert_path) else None,
                    headers={"Accept": "application/json"},
                    timeout=5,
                    verify=False
                )
                status = response.status_code

                # Colorir resultado
                if status == 404:
                    marcador = "[NOTFOUND]"
                elif status == 403:
                    marcador = "[FORBIDDEN]"
                elif status in [200, 201, 204]:
                    marcador = "[OK]"
                else:
                    marcador = f"[{status}]"

                print(f"  {marcador} GET {endpoint:30} -> {status}")

                # Se receber resposta, mostrar
                if status not in [404, 403] and response.text:
                    print(f"         Resposta: {response.text[:100]}")

            except Exception as e:
                print(f"  [ERRO] GET {endpoint:30} -> {str(e)[:50]}")

    print("\n" + "="*70)
    print("TESTE DE POST COM DADOS VAZIOS")
    print("="*70)
    print()

    # Testar POST com dados mínimos
    urls_post = [
        "https://producaorestrita.simplissweb.com.br/api/v1/nfse",
        "https://producaorestrita.simplissweb.com.br/api/v2/nfse",
        "https://producaorestrita.simplissweb.com.br/api/nfse",
    ]

    payload = {"dpsXmlGZipB64": ""}

    for url in urls_post:
        print(f"URL: {url}")

        try:
            response = requests.post(
                url,
                json=payload,
                cert=cert_path if os.path.exists(cert_path) else None,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                timeout=5,
                verify=False
            )

            status = response.status_code
            if status == 404:
                print(f"  [NOTFOUND] Status: {status}")
            elif status in [200, 201]:
                print(f"  [OK] Status: {status}")
                if response.text:
                    print(f"  Resposta: {response.text[:200]}")
            else:
                print(f"  [STATUS {status}]")
                if response.text:
                    print(f"  Resposta: {response.text[:200]}")

        except Exception as e:
            print(f"  [ERRO] {str(e)}")

        print()

if __name__ == "__main__":
    testar_urls()
