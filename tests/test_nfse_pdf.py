"""Testes unitarios das partes que nao dependem do portal.

Rodar na raiz do repositorio:
    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
import unittest.mock

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "src"))

from main import GerenciadorNFSe  # noqa: E402
from nfse_pdf import (  # noqa: E402
    NotaPortal,
    PortalError,
    PortalSimpliss,
    _competencia,
    extrair_notas_xml,
)

NFSE_NACIONAL = """<?xml version="1.0" encoding="UTF-8"?>
<ns0:NFSe xmlns:ns0="http://www.sped.fazenda.gov.br/nfse" versao="1.01">
  <ns0:infNFSe Id="NFS35473041211222333000181000000000000926024804098780">
    <ns0:nNFSe>9</ns0:nNFSe>
    <ns0:DPS>
      <ns0:infDPS Id="DPS354730411122233300018100002000000000000009">
        <ns0:dCompet>2026-02-19</ns0:dCompet>
      </ns0:infDPS>
    </ns0:DPS>
  </ns0:infNFSe>
</ns0:NFSe>
"""

SIMPLISS_102 = """<?xml version="1.0" encoding="UTF-8"?>
<NOTAS>
  <VERSAO>1.02</VERSAO>
  <NOTA>
    <NUMERO>59</NUMERO>
    <CD_VERIFICACAO>NFS35473041211222333000181000000000005926090302917506</CD_VERIFICACAO>
    <DT_COMPETENCIA>2026-09-12</DT_COMPETENCIA>
  </NOTA>
  <NOTA>
    <NUMERO>60</NUMERO>
    <CD_VERIFICACAO>NFS35473041211222333000181000000000006026090402917507</CD_VERIFICACAO>
    <DT_COMPETENCIA>2026-09-13</DT_COMPETENCIA>
  </NOTA>
</NOTAS>
"""

DPS = """<?xml version="1.0" encoding="UTF-8"?>
<DPS xmlns="http://www.sped.fazenda.gov.br/nfse">
  <infDPS Id="DPS354730411122233300018100002000000000000066">
    <nDPS>66</nDPS>
    <dCompet>2026-10-14</dCompet>
  </infDPS>
</DPS>
"""


class TestParseNumeros(unittest.TestCase):
    def test_numero_unico(self):
        self.assertEqual(GerenciadorNFSe._parse_numeros("67"), [67])

    def test_faixa_e_lista(self):
        self.assertEqual(
            GerenciadorNFSe._parse_numeros("1-4,10-11,5,99"),
            [1, 2, 3, 4, 10, 11, 5, 99],
        )

    def test_faixa_invertida_e_normalizada(self):
        self.assertEqual(GerenciadorNFSe._parse_numeros("4-1"), [1, 2, 3, 4])

    def test_separadores(self):
        self.assertEqual(GerenciadorNFSe._parse_numeros("1;4 5"), [1, 4, 5])
        self.assertEqual(GerenciadorNFSe._parse_numeros("1 a 4"), [1, 2, 3, 4])
        self.assertEqual(GerenciadorNFSe._parse_numeros("2 A 3, 7"), [2, 3, 7])

    def test_duplicados_sao_removidos(self):
        self.assertEqual(GerenciadorNFSe._parse_numeros("5,5,4-5"), [5, 4])

    def test_entrada_vazia(self):
        self.assertEqual(GerenciadorNFSe._parse_numeros(""), [])
        self.assertEqual(GerenciadorNFSe._parse_numeros(None), [])

    def test_invalido(self):
        with self.assertRaises(ValueError):
            GerenciadorNFSe._parse_numeros("abc")
        with self.assertRaises(ValueError):
            GerenciadorNFSe._parse_numeros("3-x")


class TestExtrairNotasXml(unittest.TestCase):
    def _arquivo(self, conteudo: str, nome: str = "nota.xml") -> str:
        pasta = tempfile.mkdtemp()
        caminho = os.path.join(pasta, nome)
        with open(caminho, "w", encoding="utf-8") as arquivo:
            arquivo.write(conteudo)
        return caminho

    def test_nfse_nacional(self):
        notas, avisos, dps = extrair_notas_xml(self._arquivo(NFSE_NACIONAL))
        self.assertEqual(len(notas), 1)
        self.assertEqual(notas[0].numero, 9)
        self.assertEqual(notas[0].chave, "35473041211222333000181000000000000926024804098780")
        self.assertEqual(notas[0].competencia, "202602")
        self.assertEqual(notas[0].formato, "NFSe nacional")
        self.assertEqual((avisos, dps), ([], []))

    def test_simpliss_102_com_varias_notas(self):
        notas, avisos, dps = extrair_notas_xml(self._arquivo(SIMPLISS_102))
        self.assertEqual([n.numero for n in notas], [59, 60])
        self.assertEqual(notas[0].competencia, "202609")
        self.assertTrue(all(len(n.chave) == 50 for n in notas))
        self.assertEqual((avisos, dps), ([], []))

    def test_dps_e_ignorada(self):
        notas, avisos, dps = extrair_notas_xml(self._arquivo(DPS, "dps.XML"))
        self.assertEqual(notas, [])
        self.assertEqual(len(dps), 1)
        self.assertIn("66", dps[0])

    def test_xml_invalido(self):
        notas, avisos, dps = extrair_notas_xml(self._arquivo("<NFSe><infNFSe>"))
        self.assertEqual(notas, [])
        self.assertEqual(len(avisos), 1)

    def test_xml_sem_nota(self):
        notas, avisos, dps = extrair_notas_xml(self._arquivo("<qualquer><coisa/></qualquer>"))
        self.assertEqual((notas, avisos, dps), ([], [], []))


class TestCompetencia(unittest.TestCase):
    def test_formatos(self):
        self.assertEqual(_competencia("2026-02-19"), "202602")
        self.assertEqual(_competencia("2026-02-19T11:12:27-03:00"), "202602")
        self.assertEqual(_competencia("2026/09/12"), "202609")

    def test_invalido(self):
        self.assertIsNone(_competencia(""))
        self.assertIsNone(_competencia("abc"))

    def test_nota_portal(self):
        nota = NotaPortal(rel="1|S", numero="67", data="01/10/2026",
                          valor="0,00", tomador="X", mes=10, ano=2026)
        self.assertEqual(nota.competencia, "202610")


class _RespostaFalsa:
    def __init__(self, status=200, url="https://portal/contrib/app", tipo="application/json", texto=""):
        self.status_code = status
        self.url = url
        self.headers = {"Content-Type": tipo}
        self.text = texto
        self.content = texto.encode()


class TestSessao(unittest.TestCase):
    def test_json_ok(self):
        resposta = _RespostaFalsa(texto='{"aaData": []}')
        self.assertFalse(PortalSimpliss._sessao_invalida(None, resposta))

    def test_pdf_ok(self):
        resposta = _RespostaFalsa(tipo="application/pdf", texto="%PDF-1.7")
        self.assertFalse(PortalSimpliss._sessao_invalida(None, resposta))

    def test_http_de_sessao(self):
        self.assertTrue(PortalSimpliss._sessao_invalida(None, _RespostaFalsa(status=401)))
        self.assertTrue(PortalSimpliss._sessao_invalida(None, _RespostaFalsa(status=403)))

    def test_redirecionado_para_login(self):
        resposta = _RespostaFalsa(url="https://portal/contrib/Account/Login")
        self.assertTrue(PortalSimpliss._sessao_invalida(None, resposta))

    def test_html_de_login(self):
        resposta = _RespostaFalsa(tipo="text/html", texto='<input name="Login.UserName">')
        self.assertTrue(PortalSimpliss._sessao_invalida(None, resposta))


class TestPortalSimpliss(unittest.TestCase):
    def test_documentos_so_com_digitos(self):
        portal = PortalSimpliss("https://portal/", "11.222.333/0001-81", "x", "12.345")
        self.assertEqual(portal.usuario, "11222333000181")
        self.assertEqual(portal.inscricao_municipal, "12345")
        self.assertEqual(portal.base_url, "https://portal")

    def test_corpo_listagem(self):
        corpo = PortalSimpliss("https://portal/", "1", "x")._corpo_listagem()
        self.assertIn("iColumns=15", corpo)
        self.assertIn("iDisplayLength=500", corpo)
        self.assertIn("sColumns=", corpo)


if __name__ == "__main__":
    unittest.main()


class _PortalFalso:
    """Dublê do portal: responde por mes/ano e conta as chamadas."""

    def __init__(self, notas_por_mes=None, esquecer_primeira=True):
        self.notas_por_mes = notas_por_mes or {}
        self.esquecer_primeira = esquecer_primeira
        self.chamadas = []
        self._primeira_volta = True

    def listar_notas(self, mes, ano):
        self.chamadas.append((mes, ano))
        # simula a prefeitura "esquecendo" notas na primeira varredura
        if self.esquecer_primeira and self._primeira_volta:
            self._primeira_volta = False
            return []
        return self.notas_por_mes.get((mes, ano), [])


def _nota(numero: int, mes: int, ano: int) -> NotaPortal:
    return NotaPortal(rel=f"{numero}|S", numero=str(numero), data="01/01/2026",
                      valor="10,00", tomador="X", mes=mes, ano=ano)


class TestLocalizar(unittest.TestCase):
    def setUp(self):
        self.portal = PortalSimpliss("https://portal/", "1", "x")

    def test_encontra_no_mes_informado(self):
        self.portal.listar_notas = lambda m, a: [_nota(67, m, a)]

        encontradas, faltando = self.portal.localizar([67], mes=10, ano=2026)

        self.assertEqual(list(encontradas), [67])
        self.assertEqual(faltando, [])
        self.assertEqual(encontradas[67].competencia, "202610")

    def test_nao_varre_24_meses_quando_acha(self):
        chamadas = []

        def listar(m, a):
            chamadas.append((m, a))
            return [_nota(67, m, a)]

        self.portal.listar_notas = listar
        self.portal.localizar([67], mes=10, ano=2026)

        self.assertEqual(len(chamadas), 1)

    def test_segunda_tentativa_acha_a_nota(self):
        duble = _PortalFalso({(10, 2026): [_nota(67, 10, 2026)]}, esquecer_primeira=True)
        self.portal.listar_notas = duble.listar_notas

        with unittest.mock.patch("nfse_pdf.time.sleep"):
            encontradas, faltando = self.portal.localizar([67], mes=10, ano=2026)

        self.assertEqual(list(encontradas), [67])
        self.assertEqual(faltando, [])
        self.assertGreater(len(duble.chamadas), 1)

    def test_segunda_tentativa_amplia_para_24_meses(self):
        # nota esta em outro mes; a 1a volta olha so 10/2026, a 2a varre tudo
        duble = _PortalFalso({(1, 2026): [_nota(5, 1, 2026)]}, esquecer_primeira=False)
        self.portal.listar_notas = duble.listar_notas

        with unittest.mock.patch("nfse_pdf.time.sleep"):
            encontradas, _ = self.portal.localizar([5], mes=10, ano=2026)

        self.assertIn(5, encontradas)
        self.assertIn((1, 2026), duble.chamadas)

    def test_nota_inexistente_insiste_duas_vezes(self):
        duble = _PortalFalso({}, esquecer_primeira=False)
        self.portal.listar_notas = duble.listar_notas

        with unittest.mock.patch("nfse_pdf.time.sleep"):
            encontradas, faltando = self.portal.localizar(
                [99999], meses_busca=3, tentativas=2
            )

        self.assertEqual(encontradas, {})
        self.assertEqual(faltando, [99999])
        # 3 meses por tentativa, 2 tentativas
        self.assertEqual(len(duble.chamadas), 6)

    def test_erro_de_listagem_nao_aborta(self):
        def listar(m, a):
            raise PortalError("portal fora")

        self.portal.listar_notas = listar

        with unittest.mock.patch("nfse_pdf.time.sleep"):
            encontradas, faltando = self.portal.localizar(
                [1], meses_busca=2, tentativas=1
            )

        self.assertEqual(encontradas, {})
        self.assertEqual(faltando, [1])


class _PortalPdfFalso:
    def __init__(self, resultado):
        self.resultado = resultado
        self.chamadas = []

    def baixar_pdf(self, nota, chave_esperada=None):
        self.chamadas.append((nota.numero, chave_esperada))
        if isinstance(self.resultado, Exception):
            raise self.resultado
        return self.resultado


class TestSalvarPdf(unittest.TestCase):
    CHAVE = "1" * 50

    def setUp(self):
        self.gerenciador = GerenciadorNFSe.__new__(GerenciadorNFSe)
        self.gerenciador.config = {}
        self.gerenciador.dry_run = False
        self.pasta = tempfile.mkdtemp()
        self.nota = _nota(67, 10, 2026)

    def test_grava_na_pasta_da_competencia(self):
        portal = _PortalPdfFalso((b"%PDF-1.4 conteudo", self.CHAVE))

        situacao = self.gerenciador._salvar_pdf(portal, self.nota, self.pasta)

        self.assertEqual(situacao, "baixado")
        destino = os.path.join(
            self.pasta, "pdf", "202610", f"nfse_67_{self.CHAVE}.pdf"
        )
        self.assertTrue(os.path.isfile(destino))
        with open(destino, "rb") as arquivo:
            self.assertEqual(arquivo.read(), b"%PDF-1.4 conteudo")

    def test_nao_sobrescreve_arquivo_existente(self):
        destino = os.path.join(self.pasta, "pdf", "202610")
        os.makedirs(destino)
        arquivo = os.path.join(destino, f"nfse_67_{self.CHAVE}.pdf")
        with open(arquivo, "wb") as f:
            f.write(b"%PDF antigo")

        portal = _PortalPdfFalso((b"%PDF novo", self.CHAVE))
        situacao = self.gerenciador._salvar_pdf(portal, self.nota, self.pasta)

        self.assertEqual(situacao, "existente")
        with open(arquivo, "rb") as f:
            self.assertEqual(f.read(), b"%PDF antigo")

    def test_sem_pdf_no_portal(self):
        portal = _PortalPdfFalso(None)
        self.assertEqual(
            self.gerenciador._salvar_pdf(portal, self.nota, self.pasta), "sem_pdf"
        )

    def test_repassa_chave_esperada(self):
        portal = _PortalPdfFalso((b"%PDF", self.CHAVE))
        self.gerenciador._salvar_pdf(portal, self.nota, self.pasta, chave_esperada="x")
        self.assertEqual(portal.chamadas, [("67", "x")])

    def test_erro_de_chave_divergente_propaga(self):
        portal = _PortalPdfFalso(PortalError("Chave divergente"))
        with self.assertRaises(PortalError):
            self.gerenciador._salvar_pdf(portal, self.nota, self.pasta)


class TestExtrairZip(unittest.TestCase):
    def _zip(self, entradas) -> str:
        import zipfile

        pasta = tempfile.mkdtemp()
        caminho = os.path.join(pasta, "lote.zip")
        with zipfile.ZipFile(caminho, "w") as zf:
            for nome, conteudo in entradas.items():
                zf.writestr(nome, conteudo)
        return caminho

    def test_extrai_xml_mantendo_subpastas(self):
        origem = self._zip({"a.xml": "<x/>", "sub/b.xml": "<y/>"})
        destino = tempfile.mkdtemp()

        total = GerenciadorNFSe._extrair_zip(origem, destino)

        self.assertEqual(total, 2)
        self.assertTrue(os.path.isfile(os.path.join(destino, "a.xml")))
        self.assertTrue(os.path.isfile(os.path.join(destino, "sub", "b.xml")))

    def test_bloqueia_zip_slip(self):
        origem = self._zip({"../../fora.xml": "<x/>", "ok.xml": "<y/>"})
        destino = tempfile.mkdtemp()
        pai = os.path.dirname(os.path.abspath(destino))

        total = GerenciadorNFSe._extrair_zip(origem, destino)

        self.assertEqual(total, 1)
        self.assertFalse(os.path.exists(os.path.join(pai, "fora.xml")))
        self.assertTrue(os.path.isfile(os.path.join(destino, "ok.xml")))

    def test_bloqueia_caminho_absoluto(self):
        origem = self._zip({"/etc/passwd": "x", "C:/windows/x.xml": "x"})
        destino = tempfile.mkdtemp()

        total = GerenciadorNFSe._extrair_zip(origem, destino)

        self.assertEqual(total, 0)

    def test_ignora_arquivos_de_sistema(self):
        origem = self._zip({
            "__MACOSX/x.xml": "x",
            ".DS_Store": "x",
            "Thumbs.db": "x",
            "nota.xml": "<x/>",
        })
        destino = tempfile.mkdtemp()

        total = GerenciadorNFSe._extrair_zip(origem, destino)

        self.assertEqual(total, 1)
        self.assertTrue(os.path.isfile(os.path.join(destino, "nota.xml")))


class TestIndicePdfs(unittest.TestCase):
    def test_gera_csv_com_pdf_e_sem_pdf(self):
        raiz = tempfile.mkdtemp()
        with open(os.path.join(raiz, "nfse_nacional.xml"), "w", encoding="utf-8") as f:
            f.write(NFSE_NACIONAL)
        with open(os.path.join(raiz, "lote102.xml"), "w", encoding="utf-8") as f:
            f.write(SIMPLISS_102)

        gerenciador = GerenciadorNFSe.__new__(GerenciadorNFSe)
        gerenciador.config = {"nfse": {"caminho_xml_saida": raiz}}
        gerenciador.dry_run = False

        self.assertTrue(gerenciador.gerar_indice_pdfs())

        caminho = os.path.join(raiz, "pdf", "indice.csv")
        self.assertTrue(os.path.isfile(caminho))
        with open(caminho, encoding="utf-8-sig") as arquivo:
            linhas = arquivo.read().strip().splitlines()

        self.assertEqual(linhas[0].split(";")[0], "numero")
        self.assertEqual(len(linhas), 4)  # cabecalho + 3 notas
        # nenhum PDF existe: coluna pdf vazia em todas
        self.assertTrue(all(linha.endswith(";") for linha in linhas[1:]))

    def test_pasta_inexistente(self):
        gerenciador = GerenciadorNFSe.__new__(GerenciadorNFSe)
        gerenciador.config = {"nfse": {
            "caminho_xml_saida": os.path.join(tempfile.mkdtemp(), "nao_existe")
        }}
        gerenciador.dry_run = False
        self.assertFalse(gerenciador.gerar_indice_pdfs())

    def test_pasta_sem_xml(self):
        gerenciador = GerenciadorNFSe.__new__(GerenciadorNFSe)
        gerenciador.config = {"nfse": {"caminho_xml_saida": tempfile.mkdtemp()}}
        gerenciador.dry_run = False
        self.assertFalse(gerenciador.gerar_indice_pdfs())


class TestLogs(unittest.TestCase):
    def test_um_arquivo_por_dia(self):
        from datetime import datetime

        import logger_config as lc

        pasta = tempfile.mkdtemp()
        for dia in ("20260105", "20260106"):
            quando = datetime.strptime(dia, "%Y%m%d")
            caminho = lc._log_path(quando, pasta)
            self.assertEqual(caminho.name, f"execucao_{dia}.log")

    def test_remove_logs_mais_antigos_que_30_dias(self):
        from datetime import datetime
        from pathlib import Path

        import logger_config as lc
        pasta = Path(tempfile.mkdtemp())
        agora = datetime(2026, 3, 31, 12, 0)
        antigos = ["20260228", "20260201"]
        recentes = ["20260301", "20260330", "20260331"]

        for dia in antigos + recentes:
            lc._log_path(datetime.strptime(dia, "%Y%m%d"), pasta).write_text("x", encoding="utf-8")

        removidos = lc.limpar_logs_antigos(pasta, dias=30, agora=agora)

        restantes = sorted(p.name for p in pasta.glob("*.log"))
        self.assertEqual(removidos, 2)
        self.assertEqual(
            restantes,
            [f"execucao_{dia}.log" for dia in recentes],
        )
        self.assertNotIn("execucao_20260201.log", restantes)

    def test_nao_remove_arquivo_de_outro_padrao(self):
        from pathlib import Path

        import logger_config as lc
        pasta = Path(tempfile.mkdtemp())
        (pasta / "outro.log").write_text("x", encoding="utf-8")
        (pasta / "execucao_20200101.log").write_text("x", encoding="utf-8")

        lc.limpar_logs_antigos(pasta, dias=30)

        self.assertTrue((pasta / "outro.log").exists())
        self.assertFalse((pasta / "execucao_20200101.log").exists())

    def test_pasta_inexistente_nao_explode(self):
        import logger_config as lc

        self.assertEqual(lc.limpar_logs_antigos(tempfile.mkdtemp() + "/nao_existe"), 0)


class TestDryRun(unittest.TestCase):
    def test_salvar_pdf_nao_grava_nem_baixa_em_simulacao(self):
        gerenciador = GerenciadorNFSe.__new__(GerenciadorNFSe)
        gerenciador.config = {}
        gerenciador.dry_run = True
        pasta = tempfile.mkdtemp()

        class PortalQueExplode:
            def baixar_pdf(self, nota, chave_esperada=None):
                raise AssertionError("nao deveria baixar em simulacao")

        situacao = gerenciador._salvar_pdf(
            PortalQueExplode(), _nota(67, 10, 2026), pasta
        )

        self.assertEqual(situacao, "baixado")
        self.assertFalse(os.path.exists(os.path.join(pasta, "pdf")))

    def test_simulacao_detecta_pdf_existente(self):
        gerenciador = GerenciadorNFSe.__new__(GerenciadorNFSe)
        gerenciador.config = {}
        gerenciador.dry_run = True
        pasta = tempfile.mkdtemp()
        chave = "4" * 50
        destino = os.path.join(pasta, "pdf", "202610")
        os.makedirs(destino)
        open(os.path.join(destino, f"nfse_67_{chave}.pdf"), "wb").write(b"%PDF")

        situacao = gerenciador._salvar_pdf(
            _PortalPdfFalso(None), _nota(67, 10, 2026), pasta, chave_esperada=chave
        )

        self.assertEqual(situacao, "existente")

    def test_lote_em_simulacao_nao_cria_pastas(self):
        gerenciador = GerenciadorNFSe.__new__(GerenciadorNFSe)
        gerenciador.config = {}
        gerenciador.dry_run = True
        pasta = tempfile.mkdtemp()
        with open(os.path.join(pasta, "a.xml"), "w", encoding="utf-8") as f:
            f.write("<DPS/>")

        gerenciador.emitir_lote(pasta)

        self.assertEqual(os.listdir(pasta), ["a.xml"])

    def test_indice_em_simulacao_nao_grava(self):
        raiz = tempfile.mkdtemp()
        with open(os.path.join(raiz, "n.xml"), "w", encoding="utf-8") as f:
            f.write(NFSE_NACIONAL)
        gerenciador = GerenciadorNFSe.__new__(GerenciadorNFSe)
        gerenciador.config = {"nfse": {"caminho_xml_saida": raiz}}
        gerenciador.dry_run = True

        self.assertTrue(gerenciador.gerar_indice_pdfs())
        self.assertFalse(os.path.exists(os.path.join(raiz, "pdf", "indice.csv")))

    def test_modo_normal_grava(self):
        gerenciador = GerenciadorNFSe.__new__(GerenciadorNFSe)
        gerenciador.config = {}
        gerenciador.dry_run = False
        pasta = tempfile.mkdtemp()
        chave = "2" * 50
        portal = _PortalPdfFalso((b"%PDF-1.4", chave))

        gerenciador._salvar_pdf(portal, _nota(68, 10, 2026), pasta)

        self.assertTrue(os.path.isfile(os.path.join(
            pasta, "pdf", "202610", f"nfse_68_{chave}.pdf"
        )))


class TestEntradaSemConsole(unittest.TestCase):
    def test_eof_encerra_sem_traceback(self):

        import logger_config as lc

        original = lc._original_input

        def sem_entrada(prompt=""):
            raise EOFError()

        lc._original_input = sem_entrada
        try:
            with self.assertRaises(SystemExit):
                lc.input_and_log("opcao: ")
        finally:
            lc._original_input = original

    def test_ctrl_c_encerra_sem_traceback(self):
        import logger_config as lc

        original = lc._original_input

        def interrompido(prompt=""):
            raise KeyboardInterrupt()

        lc._original_input = interrompido
        try:
            with self.assertRaises(SystemExit):
                lc.input_and_log("opcao: ")
        finally:
            lc._original_input = original


class TestIndiceSoComPdfs(unittest.TestCase):
    def test_indice_inclui_pdf_sem_xml(self):
        raiz = tempfile.mkdtemp()
        pasta = os.path.join(raiz, "pdf", "202601")
        os.makedirs(pasta)
        chave = "5" * 50
        with open(os.path.join(pasta, f"nfse_2_{chave}.pdf"), "wb") as f:
            f.write(b"%PDF-1.4")

        gerenciador = GerenciadorNFSe.__new__(GerenciadorNFSe)
        gerenciador.config = {"nfse": {"caminho_xml_saida": raiz}}
        gerenciador.dry_run = False

        self.assertTrue(gerenciador.gerar_indice_pdfs())

        with open(os.path.join(raiz, "pdf", "indice.csv"), encoding="utf-8-sig") as f:
            linhas = f.read().strip().splitlines()

        self.assertEqual(len(linhas), 2)  # cabecalho + 1 PDF
        campos = linhas[1].split(";")
        self.assertEqual(campos[0], "2")
        self.assertEqual(campos[1], "202601")
        self.assertEqual(campos[5], chave)
        self.assertEqual(campos[6], "PDF (sem XML)")
        self.assertIn("nfse_2_", campos[7])

    def test_indice_com_xml_e_pdf_nao_duplica(self):
        raiz = tempfile.mkdtemp()
        with open(os.path.join(raiz, "n.xml"), "w", encoding="utf-8") as f:
            f.write(NFSE_NACIONAL)
        chave = "35473041211222333000181000000000000926024804098780"
        pasta = os.path.join(raiz, "pdf", "202602")
        os.makedirs(pasta)
        with open(os.path.join(pasta, f"nfse_9_{chave}.pdf"), "wb") as f:
            f.write(b"%PDF-1.4")

        gerenciador = GerenciadorNFSe.__new__(GerenciadorNFSe)
        gerenciador.config = {"nfse": {"caminho_xml_saida": raiz}}
        gerenciador.dry_run = False

        self.assertTrue(gerenciador.gerar_indice_pdfs())

        with open(os.path.join(raiz, "pdf", "indice.csv"), encoding="utf-8-sig") as f:
            linhas = f.read().strip().splitlines()

        self.assertEqual(len(linhas), 2)  # cabecalho + 1 nota (sem duplicar)


class TestIndiceAposDownload(unittest.TestCase):
    def test_pdf_baixado_aparece_no_indice_seguinte(self):
        import csv
        raiz = tempfile.mkdtemp()
        gerenciador = GerenciadorNFSe.__new__(GerenciadorNFSe)
        gerenciador.config = {"nfse": {"caminho_xml_saida": raiz}}
        gerenciador.dry_run = False
        chave = "6" * 50

        # 1) baixa um PDF (sem XML nenhum)
        gerenciador._salvar_pdf(
            _PortalPdfFalso((b"%PDF-1.4", chave)), _nota(70, 10, 2026), raiz
        )
        # 2) gera o indice
        self.assertTrue(gerenciador.gerar_indice_pdfs())

        with open(os.path.join(raiz, "pdf", "indice.csv"), encoding="utf-8-sig", newline="") as f:
            linhas = list(csv.DictReader(f, delimiter=";"))

        self.assertEqual(len(linhas), 1)
        self.assertEqual(linhas[0]["numero"], "70")
        self.assertEqual(linhas[0]["competencia"], "202610")
        self.assertEqual(linhas[0]["chave"], chave)
        self.assertTrue(linhas[0]["pdf"].endswith(".pdf"))


class TestConfigInstalado(unittest.TestCase):
    def test_encontra_config_em_etc(self):
        from unittest import mock

        import main as main_mod

        with mock.patch.object(main_mod.Path, "cwd", return_value=main_mod.Path(tempfile.mkdtemp())):
            with mock.patch.object(main_mod.Path, "is_file", return_value=True):
                caminho = GerenciadorNFSe._localizar_config_instalado()
        self.assertTrue(caminho.endswith("config.json"))

    def test_sem_config_volta_padrao(self):
        from unittest import mock

        import main as main_mod

        with mock.patch.object(main_mod.Path, "cwd", return_value=main_mod.Path(tempfile.mkdtemp())):
            with mock.patch.object(main_mod.Path, "is_file", return_value=False):
                caminho = GerenciadorNFSe._localizar_config_instalado()
        self.assertEqual(caminho, "config.json")


class TestLogsSemPermissao(unittest.TestCase):
    def test_linux_usa_pasta_do_usuario(self):
        from unittest import mock

        import logger_config as lc

        with mock.patch.object(lc.sys, "frozen", True, create=True):
            with mock.patch.object(lc.sys, "executable", "/opt/nfse/nfse-santana"):
                with mock.patch.object(lc.os, "name", "posix"):
                    with mock.patch.object(lc.Path, "home", return_value=lc.Path("/home/teste")):
                        base = lc._base_dir()
        self.assertIn(".local", str(base))
        self.assertIn("nfse-santana", str(base))

    def test_windows_usa_pasta_do_exe(self):
        from unittest import mock

        import logger_config as lc

        class _CaminhoFalso:
            """Imita Path(...).resolve().parent sem depender do SO."""

            def __init__(self, texto):
                self._texto = str(texto).replace("\\", "/")
                self.name = self._texto.rsplit("/", 1)[-1] or self._texto

            def resolve(self):
                return _CaminhoFalso(self._texto)

            @property
            def parent(self):
                return _CaminhoFalso(self._texto.rsplit("/", 1)[0])

        with mock.patch.object(lc.sys, "frozen", True, create=True):
            with mock.patch.object(lc.sys, "executable", "C:/Programas/nfse/nfse-santana.exe"):
                with mock.patch.object(lc.os, "name", "nt"):
                    with mock.patch.object(lc, "Path", _CaminhoFalso):
                        base = lc._base_dir()
        self.assertEqual(base.name, "nfse")


def _tem_signxml() -> bool:
    try:
        import signxml  # noqa: F401
        return True
    except ImportError:
        return False


@unittest.skipUnless(_tem_signxml(), "signxml nao instalado")
class TestAssinatura(unittest.TestCase):
    """Garante que as versoes fixadas de signxml/cryptography ainda assinam."""

    def test_assina_dps_com_certificado_sintetico(self):
        import datetime

        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID

        import assinador_dps

        pasta = tempfile.mkdtemp()
        chave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        nome = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Teste NFS-e")])
        agora = datetime.datetime.now(datetime.timezone.utc)
        cert = (
            x509.CertificateBuilder()
            .subject_name(nome)
            .issuer_name(nome)
            .public_key(chave.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(agora - datetime.timedelta(days=1))
            .not_valid_after(agora + datetime.timedelta(days=1))
            .sign(chave, hashes.SHA256())
        )
        caminho = os.path.join(pasta, "cert.pem")
        with open(caminho, "wb") as f:
            f.write(chave.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            ))
            f.write(cert.public_bytes(serialization.Encoding.PEM))

        dps = (
            '<DPS xmlns="http://www.sped.fazenda.gov.br/nfse">'
            '<infDPS Id="DPS123"><nDPS>1</nDPS></infDPS></DPS>'
        )

        assinado = assinador_dps.AssinadorDPS(caminho).assinar_xml(dps)

        self.assertIn("Signature", assinado)
        self.assertIn("infDPS", assinado)
