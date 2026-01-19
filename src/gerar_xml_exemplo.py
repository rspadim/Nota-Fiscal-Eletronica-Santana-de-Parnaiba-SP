"""
Exemplo de como gerar XML da DPS em Python
Use como referência para integrar no seu programa
"""

from xml.etree import ElementTree as ET
from datetime import datetime
import os


class GeradorXMLDPS:
    """Gera XML da DPS conforme especificação SIMPLISS"""

    @staticmethod
    def gerar_dps(dados_prestador: dict,
                  dados_tomador: dict,
                  dados_servico: dict,
                  nome_arquivo: str = None) -> str:
        """
        Gera XML da DPS

        Args:
            dados_prestador: {'cnpj', 'inscricao_municipal', ...}
            dados_tomador: {'cnpj_cpf', 'razao_social', ...}
            dados_servico: {'valor', 'codigo', 'descricao', ...}
            nome_arquivo: Nome do arquivo a salvar (opcional)

        Returns:
            Conteúdo XML como string
        """
        # Elemento raiz
        dps = ET.Element('DPS')
        dps.set('xmlns', 'http://www.abrasf.org.br/nfse')

        # Dados do Prestador
        prestador = ET.SubElement(dps, 'Prestador')
        ET.SubElement(prestador, 'CpfCnpj').text = dados_prestador.get('cnpj', '')
        ET.SubElement(prestador, 'InscricaoMunicipal').text = dados_prestador.get('inscricao_municipal', '')

        # Dados do Tomador
        tomador = ET.SubElement(dps, 'Tomador')
        ET.SubElement(tomador, 'CpfCnpj').text = dados_tomador.get('cnpj_cpf', '')
        ET.SubElement(tomador, 'RazaoSocial').text = dados_tomador.get('razao_social', '')

        # Endereço do Tomador (opcional, mas recomendado)
        endereco_tomador = ET.SubElement(tomador, 'Endereco')
        ET.SubElement(endereco_tomador, 'Logradouro').text = dados_tomador.get('logradouro', '')
        ET.SubElement(endereco_tomador, 'Numero').text = dados_tomador.get('numero', '')
        ET.SubElement(endereco_tomador, 'Complemento').text = dados_tomador.get('complemento', '')
        ET.SubElement(endereco_tomador, 'Bairro').text = dados_tomador.get('bairro', '')
        ET.SubElement(endereco_tomador, 'Cidade').text = dados_tomador.get('cidade', '')
        ET.SubElement(endereco_tomador, 'Estado').text = dados_tomador.get('estado', '')
        ET.SubElement(endereco_tomador, 'CEP').text = dados_tomador.get('cep', '')

        # Dados do Serviço
        servico = ET.SubElement(dps, 'Servico')
        ET.SubElement(servico, 'Valores').text = str(dados_servico.get('valor', 0))
        ET.SubElement(servico, 'ItemServico').text = dados_servico.get('codigo_servico', '')
        ET.SubElement(servico, 'Descricao').text = dados_servico.get('descricao', '')
        ET.SubElement(servico, 'DataEmissao').text = dados_servico.get('data_emissao', datetime.now().isoformat())

        # Formatar XML com indentação
        GeradorXMLDPS._indenta(dps)
        xml_string = ET.tostring(dps, encoding='unicode')

        # Adicionar declaração XML
        xml_completo = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_string

        # Salvar em arquivo se solicitado
        if nome_arquivo:
            with open(nome_arquivo, 'w', encoding='utf-8') as f:
                f.write(xml_completo)
            print(f"✓ XML salvo em: {nome_arquivo}")

        return xml_completo

    @staticmethod
    def _indenta(elemento, nivel=0):
        """Adiciona indentação para legibilidade"""
        indent = "\n" + "  " * nivel
        if len(elemento):
            if not elemento.text or not elemento.text.strip():
                elemento.text = indent + "  "
            if not elemento.tail or not elemento.tail.strip():
                elemento.tail = indent
            for filho in elemento:
                GeradorXMLDPS._indenta(filho, nivel + 1)
            if not filho.tail or not filho.tail.strip():
                filho.tail = indent
        else:
            if nivel and (not elemento.tail or not elemento.tail.strip()):
                elemento.tail = indent


def exemplo_1_basico():
    """Exemplo 1: XML básico minimalista"""
    print("\n" + "="*60)
    print("EXEMPLO 1: XML Básico")
    print("="*60)

    dados_prestador = {
        "cnpj": "12345678000190",
        "inscricao_municipal": "123456789"
    }

    dados_tomador = {
        "cnpj_cpf": "98765432000100",
        "razao_social": "Empresa Cliente LTDA"
    }

    dados_servico = {
        "valor": "1000.00",
        "codigo_servico": "0701",  # Serviços de consultoria
        "descricao": "Serviço de consultoria empresarial"
    }

    xml = GeradorXMLDPS.gerar_dps(
        dados_prestador,
        dados_tomador,
        dados_servico,
        nome_arquivo="dps_exemplo_1.xml"
    )

    print("\nXML gerado:")
    print(xml[:300] + "...")


def exemplo_2_completo():
    """Exemplo 2: XML completo com endereço"""
    print("\n" + "="*60)
    print("EXEMPLO 2: XML Completo")
    print("="*60)

    dados_prestador = {
        "cnpj": "12345678000190",
        "inscricao_municipal": "123456789"
    }

    dados_tomador = {
        "cnpj_cpf": "98765432000100",
        "razao_social": "Empresa XYZ Consultoria LTDA",
        "logradouro": "Rua das Flores",
        "numero": "123",
        "complemento": "Sala 45",
        "bairro": "Centro",
        "cidade": "São Paulo",
        "estado": "SP",
        "cep": "01234567"
    }

    dados_servico = {
        "valor": "5000.00",
        "codigo_servico": "0702",  # Desenvolvimento de software
        "descricao": "Desenvolvimento de sistema web de gestão",
        "data_emissao": datetime.now().isoformat()
    }

    xml = GeradorXMLDPS.gerar_dps(
        dados_prestador,
        dados_tomador,
        dados_servico,
        nome_arquivo="dps_exemplo_2.xml"
    )

    print("\nXML gerado com sucesso")
    print(f"Tamanho: {len(xml)} caracteres")


def exemplo_3_multiplos_servicos():
    """Exemplo 3: Gerar múltiplos XMLs em lote"""
    print("\n" + "="*60)
    print("EXEMPLO 3: Gerar Múltiplos XMLs")
    print("="*60)

    # Lista de serviços a faturar
    servicos = [
        {
            "tomador_cnpj": "11111111000111",
            "tomador_razao": "Empresa A LTDA",
            "valor": "500.00",
            "codigo": "0701",
            "descricao": "Consultoria"
        },
        {
            "tomador_cnpj": "22222222000222",
            "tomador_razao": "Empresa B LTDA",
            "valor": "750.00",
            "codigo": "0702",
            "descricao": "Desenvolvimento de software"
        },
        {
            "tomador_cnpj": "33333333000333",
            "tomador_razao": "Empresa C LTDA",
            "valor": "1200.00",
            "codigo": "0703",
            "descricao": "Processamento de dados"
        }
    ]

    dados_prestador = {
        "cnpj": "12345678000190",
        "inscricao_municipal": "123456789"
    }

    # Gerar XML para cada serviço
    for i, servico in enumerate(servicos, 1):
        dados_tomador = {
            "cnpj_cpf": servico["tomador_cnpj"],
            "razao_social": servico["tomador_razao"]
        }

        dados_servico = {
            "valor": servico["valor"],
            "codigo_servico": servico["codigo"],
            "descricao": servico["descricao"]
        }

        nome_arquivo = f"dps_lote_{i:03d}.xml"

        GeradorXMLDPS.gerar_dps(
            dados_prestador,
            dados_tomador,
            dados_servico,
            nome_arquivo=nome_arquivo
        )

    print(f"\n✓ {len(servicos)} arquivos gerados:")
    for i in range(1, len(servicos) + 1):
        print(f"   - dps_lote_{i:03d}.xml")


def exemplo_4_integracao():
    """Exemplo 4: Integração com o cliente NFS-e"""
    print("\n" + "="*60)
    print("EXEMPLO 4: Integração com Emissão")
    print("="*60)

    # Gerar XML
    dados_prestador = {
        "cnpj": "12345678000190",
        "inscricao_municipal": "123456789"
    }

    dados_tomador = {
        "cnpj_cpf": "98765432000100",
        "razao_social": "Cliente Teste LTDA"
    }

    dados_servico = {
        "valor": "1000.00",
        "codigo_servico": "0701",
        "descricao": "Serviço de teste"
    }

    xml = GeradorXMLDPS.gerar_dps(
        dados_prestador,
        dados_tomador,
        dados_servico,
        nome_arquivo="dps_para_enviar.xml"
    )

    print("\nXML gerado: dps_para_enviar.xml")
    print("\nAgora você pode enviar com:")
    print("  python main.py emitir dps_para_enviar.xml")

    # Opcionalmente tentar enviar
    try:
        print("\nTentando enviar...")
        from main import GerenciadorNFSe

        gerenciador = GerenciadorNFSe()
        sucesso = gerenciador.emitir_nfse("dps_para_enviar.xml")

        if sucesso:
            print("✓ NFS-e emitida com sucesso!")
        else:
            print("✗ Erro na emissão (pode ser erro de validação)")

    except Exception as e:
        print(f"ℹ Não foi possível enviar agora: {e}")
        print("   Você pode enviar manualmente depois")


def copiar_exemplo_para_seu_programa():
    """Código para copiar e colar no seu programa"""
    print("\n" + "="*60)
    print("CÓDIGO PARA INTEGRAR NO SEU PROGRAMA")
    print("="*60)

    codigo = '''
# Importe ao início do seu arquivo
from gerar_xml_exemplo import GeradorXMLDPS

# Use assim em seu programa:
def emitir_nota_fiscal(cliente_cnpj, cliente_razao, valor, codigo_servico, descricao):
    """Função para emitir NFS-e a partir dos dados da nota"""

    # Seus dados
    dados_prestador = {
        "cnpj": "COLOQUE_SEU_CNPJ",
        "inscricao_municipal": "COLOQUE_SUA_INSCRICAO"
    }

    # Dados do cliente
    dados_tomador = {
        "cnpj_cpf": cliente_cnpj,
        "razao_social": cliente_razao
    }

    # Dados do serviço
    dados_servico = {
        "valor": str(valor),
        "codigo_servico": codigo_servico,
        "descricao": descricao
    }

    # Gerar XML
    xml = GeradorXMLDPS.gerar_dps(
        dados_prestador,
        dados_tomador,
        dados_servico,
        nome_arquivo="nfse_temp.xml"
    )

    # Enviar com o cliente
    from main import GerenciadorNFSe
    gerenciador = GerenciadorNFSe()
    sucesso = gerenciador.emitir_nfse("nfse_temp.xml")

    return sucesso

# Use assim:
sucesso = emitir_nota_fiscal(
    cliente_cnpj="98765432000100",
    cliente_razao="Cliente LTDA",
    valor=1000.00,
    codigo_servico="0701",
    descricao="Serviço de consultoria"
)
'''
    print(codigo)
    print("\nCopie e adapte este código no seu programa!")


if __name__ == "__main__":
    print("\n")
    print("█" * 60)
    print("█  EXEMPLOS DE GERAÇÃO DE XML - DPS")
    print("█" * 60)

    # Executar exemplos
    exemplo_1_basico()
    exemplo_2_completo()
    exemplo_3_multiplos_servicos()
    exemplo_4_integracao()
    copiar_exemplo_para_seu_programa()

    print("\n" + "="*60)
    print("Arquivos gerados em:")
    for arquivo in os.listdir('.'):
        if arquivo.startswith('dps_'):
            tamanho = os.path.getsize(arquivo)
            print(f"  ✓ {arquivo} ({tamanho} bytes)")
    print("="*60)
