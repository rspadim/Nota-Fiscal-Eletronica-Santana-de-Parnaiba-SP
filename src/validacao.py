"""
Funções de validação para NFS-e
"""

import re
from typing import Tuple


class ValidadorNFSe:
    """Valida dados de NFS-e conforme regras de negócio"""

    @staticmethod
    def validar_cnpj(cnpj: str) -> Tuple[bool, str]:
        """Valida formato e dígitos verificadores do CNPJ"""
        # Remover caracteres não numéricos
        cnpj_limpo = re.sub(r'[^\d]', '', cnpj)

        if len(cnpj_limpo) != 14:
            return False, "CNPJ deve ter 14 dígitos"

        # Validar dígitos verificadores
        if cnpj_limpo == cnpj_limpo[0] * 14:
            return False, "CNPJ com dígitos repetidos é inválido"

        # Primeiro dígito verificador
        soma = sum(int(cnpj_limpo[i]) * (5 - (i % 4)) for i in range(12))
        resto = soma % 11
        digito1 = 0 if resto < 2 else 11 - resto

        if int(cnpj_limpo[12]) != digito1:
            return False, "CNPJ com primeiro dígito verificador inválido"

        # Segundo dígito verificador
        soma = sum(int(cnpj_limpo[i]) * (6 - (i % 4)) for i in range(13))
        resto = soma % 11
        digito2 = 0 if resto < 2 else 11 - resto

        if int(cnpj_limpo[13]) != digito2:
            return False, "CNPJ com segundo dígito verificador inválido"

        return True, "CNPJ válido"

    @staticmethod
    def validar_cpf(cpf: str) -> Tuple[bool, str]:
        """Valida formato e dígitos verificadores do CPF"""
        cpf_limpo = re.sub(r'[^\d]', '', cpf)

        if len(cpf_limpo) != 11:
            return False, "CPF deve ter 11 dígitos"

        if cpf_limpo == cpf_limpo[0] * 11:
            return False, "CPF com dígitos repetidos é inválido"

        # Primeiro dígito verificador
        soma = sum(int(cpf_limpo[i]) * (10 - i) for i in range(9))
        resto = soma % 11
        digito1 = 0 if resto < 2 else 11 - resto

        if int(cpf_limpo[9]) != digito1:
            return False, "CPF com primeiro dígito verificador inválido"

        # Segundo dígito verificador
        soma = sum(int(cpf_limpo[i]) * (11 - i) for i in range(10))
        resto = soma % 11
        digito2 = 0 if resto < 2 else 11 - resto

        if int(cpf_limpo[10]) != digito2:
            return False, "CPF com segundo dígito verificador inválido"

        return True, "CPF válido"

    @staticmethod
    def validar_inscricao_municipal(inscricao: str) -> Tuple[bool, str]:
        """Valida inscrição municipal"""
        if not inscricao or len(inscricao.strip()) == 0:
            return False, "Inscrição municipal não pode estar vazia"

        if len(inscricao) > 15:
            return False, "Inscrição municipal não deve exceder 15 caracteres"

        return True, "Inscrição municipal válida"

    @staticmethod
    def validar_valor_servico(valor: float) -> Tuple[bool, str]:
        """Valida valor do serviço"""
        try:
            valor_float = float(valor)

            if valor_float < 0:
                return False, "Valor do serviço não pode ser negativo"

            if valor_float > 999999999.99:
                return False, "Valor do serviço excede o máximo permitido"

            return True, "Valor válido"

        except ValueError:
            return False, "Valor deve ser numérico"

    @staticmethod
    def validar_codigo_servico(codigo: str) -> Tuple[bool, str]:
        """Valida código de serviço conforme LC 116/2003"""
        # Códigos válidos segundo Lei Complementar 116/2003
        codigos_validos = [
            "0701", "0702", "0703", "0704", "0705", "0706", "0707", "0708", "0709",
            "0710", "0711", "0712", "0713", "0714", "0715", "0716", "0717", "0718",
            "0719", "0720", "0721", "0722", "0723", "0724", "0725", "0726", "0727",
            "0728", "0729", "0730", "0731", "0732", "0733", "0734", "0735", "0736",
            "0737", "0738", "0739", "0740", "0741", "0742", "0743", "0744", "0745",
            "0746", "0747", "0748", "0749", "0750"
        ]

        if codigo not in codigos_validos:
            return False, f"Código de serviço '{codigo}' não está na tabela LC 116/2003"

        return True, "Código de serviço válido"

    @staticmethod
    def validar_descricao_servico(descricao: str) -> Tuple[bool, str]:
        """Valida descrição do serviço"""
        if not descricao or len(descricao.strip()) == 0:
            return False, "Descrição do serviço não pode estar vazia"

        if len(descricao) > 2000:
            return False, "Descrição do serviço não deve exceder 2000 caracteres"

        return True, "Descrição válida"

    @staticmethod
    def validar_razao_social(razao_social: str) -> Tuple[bool, str]:
        """Valida razão social"""
        if not razao_social or len(razao_social.strip()) == 0:
            return False, "Razão social não pode estar vazia"

        if len(razao_social) > 150:
            return False, "Razão social não deve exceder 150 caracteres"

        return True, "Razão social válida"

    @staticmethod
    def validar_dps_completa(dps: dict) -> Tuple[bool, list]:
        """
        Valida uma DPS completa

        Args:
            dps: Dicionário com dados da DPS

        Returns:
            Tupla (válida, lista_de_erros)
        """
        erros = []

        # Validar prestador
        if "cnpj_prestador" in dps:
            valido, msg = ValidadorNFSe.validar_cnpj(dps["cnpj_prestador"])
            if not valido:
                erros.append(f"Prestador - CNPJ: {msg}")

        if "inscricao_municipal" in dps:
            valido, msg = ValidadorNFSe.validar_inscricao_municipal(dps["inscricao_municipal"])
            if not valido:
                erros.append(f"Prestador - {msg}")

        # Validar tomador
        if "cnpj_tomador" in dps:
            cnpj = dps["cnpj_tomador"]
            # Tentar validar como CNPJ
            valido_cnpj, _ = ValidadorNFSe.validar_cnpj(cnpj)
            # Ou como CPF
            valido_cpf, _ = ValidadorNFSe.validar_cpf(cnpj)

            if not (valido_cnpj or valido_cpf):
                erros.append("Tomador - CNPJ/CPF inválido")

        if "razao_social_tomador" in dps:
            valido, msg = ValidadorNFSe.validar_razao_social(dps["razao_social_tomador"])
            if not valido:
                erros.append(f"Tomador - {msg}")

        # Validar serviço
        if "valor_servico" in dps:
            valido, msg = ValidadorNFSe.validar_valor_servico(dps["valor_servico"])
            if not valido:
                erros.append(f"Serviço - Valor: {msg}")

        if "codigo_servico" in dps:
            valido, msg = ValidadorNFSe.validar_codigo_servico(dps["codigo_servico"])
            if not valido:
                erros.append(f"Serviço - {msg}")

        if "descricao_servico" in dps:
            valido, msg = ValidadorNFSe.validar_descricao_servico(dps["descricao_servico"])
            if not valido:
                erros.append(f"Serviço - {msg}")

        return len(erros) == 0, erros


def testar_validacao():
    """Testa as funções de validação"""
    validador = ValidadorNFSe()

    print("=== TESTES DE VALIDAÇÃO ===\n")

    # Teste CNPJ
    print("Teste CNPJ:")
    valido, msg = validador.validar_cnpj("12.345.678/0001-90")
    print(f"  12.345.678/0001-90: {msg}")

    # Teste CPF
    print("\nTeste CPF:")
    valido, msg = validador.validar_cpf("123.456.789-09")
    print(f"  123.456.789-09: {msg}")

    # Teste código de serviço
    print("\nTeste Código de Serviço:")
    valido, msg = validador.validar_codigo_servico("0701")
    print(f"  0701: {msg}")

    valido, msg = validador.validar_codigo_servico("9999")
    print(f"  9999: {msg}")

    # Teste DPS completa
    print("\nTeste DPS Completa:")
    dps_teste = {
        "cnpj_prestador": "12345678000190",
        "inscricao_municipal": "123456",
        "cnpj_tomador": "98765432000100",
        "razao_social_tomador": "Empresa Teste LTDA",
        "valor_servico": 1000.00,
        "codigo_servico": "0701",
        "descricao_servico": "Serviço de teste"
    }

    valida, erros = validador.validar_dps_completa(dps_teste)
    if valida:
        print("  ✓ DPS válida!")
    else:
        print("  ✗ DPS inválida:")
        for erro in erros:
            print(f"    - {erro}")


if __name__ == "__main__":
    testar_validacao()
