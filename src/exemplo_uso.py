"""
Exemplos de uso do cliente NFS-e para Santana de Parnaíba
"""

from nfse_emitter import NFSeEmitter, NFSeConfig
from datetime import datetime


def exemplo_emitir_nfse():
    """Exemplo de emissão de uma NFS-e"""

    # Configurar conexão
    config = NFSeConfig(
        ambiente="homologacao",
        certificado_path="seu_certificado.pem",  # Caminho para seu certificado
        chave_privada_path="sua_chave_privada.pem"  # Ou None se estiver no mesmo arquivo
    )

    # Criar cliente
    client = NFSeEmitter(config)

    # Preparar dados da DPS (Declaração de Prestação de Serviço)
    dps = {
        "cnpj_prestador": "12345678000190",  # Seu CNPJ
        "inscricao_municipal": "123456789",  # Sua inscrição municipal
        "cnpj_tomador": "98765432000100",    # CNPJ do cliente
        "razao_social_tomador": "Empresa XYZ LTDA",
        "valor_servico": 1000.00,
        "codigo_servico": "0701",  # Código de serviço conforme LC 116/2003
        "descricao_servico": "Serviço de consultoria empresarial",
        "data_emissao": datetime.now().isoformat()
    }

    # Emitir NFS-e
    sucesso, resposta = client.emitir_nfse(dps)

    if sucesso:
        print("✓ NFS-e emitida com sucesso!")
        print(f"Número da NFS-e: {resposta.get('numero_nfse')}")
        print(f"Chave de acesso: {resposta.get('chave_acesso')}")
    else:
        print("✗ Erro na emissão:")
        print(resposta.get("erro"))


def exemplo_consultar_nfse():
    """Exemplo de consulta de uma NFS-e"""

    config = NFSeConfig(
        ambiente="homologacao",
        certificado_path="seu_certificado.pem"
    )

    client = NFSeEmitter(config)

    # Chave de acesso da NFS-e a consultar
    chave_acesso = "12 123456789 123456789 123456789"

    sucesso, resposta = client.consultar_nfse(chave_acesso)

    if sucesso:
        print("✓ NFS-e consultada com sucesso!")
        # O XML da NFS-e está em resposta["xml"]
        print(f"XML: {resposta.get('xml')[:200]}...")
    else:
        print("✗ Erro na consulta:")
        print(resposta.get("erro"))


def exemplo_cancelar_nfse():
    """Exemplo de cancelamento de uma NFS-e"""

    config = NFSeConfig(
        ambiente="homologacao",
        certificado_path="seu_certificado.pem"
    )

    client = NFSeEmitter(config)

    chave_acesso = "12 123456789 123456789 123456789"
    motivo = "Cancelamento por solicitação do cliente"

    sucesso, resposta = client.cancelar_nfse(chave_acesso, motivo)

    if sucesso:
        print("✓ NFS-e cancelada com sucesso!")
    else:
        print("✗ Erro no cancelamento:")
        print(resposta.get("erro"))


def exemplo_lote_nfse():
    """Exemplo de emissão em lote"""

    config = NFSeConfig(
        ambiente="homologacao",
        certificado_path="seu_certificado.pem"
    )

    client = NFSeEmitter(config)

    # Múltiplas NFS-e para emitir
    nfses = [
        {
            "cnpj_prestador": "12345678000190",
            "inscricao_municipal": "123456789",
            "cnpj_tomador": "11111111000111",
            "razao_social_tomador": "Empresa A LTDA",
            "valor_servico": 500.00,
            "codigo_servico": "0701",
            "descricao_servico": "Consultoria",
            "data_emissao": datetime.now().isoformat()
        },
        {
            "cnpj_prestador": "12345678000190",
            "inscricao_municipal": "123456789",
            "cnpj_tomador": "22222222000222",
            "razao_social_tomador": "Empresa B LTDA",
            "valor_servico": 750.00,
            "codigo_servico": "0702",
            "descricao_servico": "Desenvolvimento de software",
            "data_emissao": datetime.now().isoformat()
        }
    ]

    for i, dps in enumerate(nfses, 1):
        print(f"\nEmitindo NFS-e {i}/{len(nfses)}...")
        sucesso, resposta = client.emitir_nfse(dps)

        if sucesso:
            print(f"  ✓ Sucesso - Número: {resposta.get('numero_nfse')}")
        else:
            print(f"  ✗ Erro: {resposta.get('erro')}")


if __name__ == "__main__":
    print("=== EXEMPLOS DE USO - NFS-e SANTANA DE PARNAÍBA ===\n")

    print("1. Para emitir uma NFS-e:")
    print("   - Atualize os dados da DPS com suas informações")
    print("   - Configure o caminho do certificado digital")
    print("   - Execute: exemplo_emitir_nfse()")

    print("\n2. Para consultar uma NFS-e:")
    print("   - Use a chave de acesso gerada na emissão")
    print("   - Execute: exemplo_consultar_nfse()")

    print("\n3. Para cancelar uma NFS-e:")
    print("   - Use a chave de acesso da NFS-e a cancelar")
    print("   - Execute: exemplo_cancelar_nfse()")

    print("\n4. Para emitir em lote:")
    print("   - Prepare uma lista de DPS")
    print("   - Execute: exemplo_lote_nfse()")

    print("\n" + "="*50)
    print("Ambiente de homologação disponível em:")
    print("https://producaorestrita.simplissweb.com.br/swagger/index.html")
