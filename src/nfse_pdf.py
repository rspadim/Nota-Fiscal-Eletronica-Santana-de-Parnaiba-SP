"""
Download dos PDFs (DANFSE) das NFS-e pelo portal SIMPLISS.

O portal nao possui API publica para o PDF: o download e feito por uma sessao
autenticada (CNPJ + senha) no site da prefeitura.

Fluxo descoberto:
    1. POST /contrib/Account/Login                     -> cookies de sessao
    2. POST /contrib/app/nfse/Nfse/_prestadorNfseDataTables?Cnpj=..&Im=..&Mes=..&Ano=..&Nacional=3
                                                        -> JSON com a lista de notas (id|S, numero, ...)
    3. GET  /contrib/app/nfse/Nfse/_detalhe/<id>|<S>    -> HTML com a chave (50 digitos) e o id de impressao
    4. GET  /contrib/app/nfse/NotaNacional/_Report?id=<idImpressao>_NFS<chave>
                                                        -> application/pdf
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET

import requests

# Colunas do DataTables server-side (ordem exigida pelo portal)
_COLUNAS = (
    ",nota_nacional,Numero,Dt_emissao,Vl_Servicos,Vl_Deducao,Vl_Base_Calculo,"
    "Vl_Aliquota,Vl_Iss,Tom_Cpf_Cnpj,Sn_Iss_Retido,Es_Guia,Cd_Status,"
    "TemCartaCorrecao,Sn_Verificado"
)

_TAG_RE = re.compile(r"<[^>]+>")
_CHAVE_RE = re.compile(r"\b(\d{50})\b")
_IMPRIMIR_RE = re.compile(r"ImprimirNotaNacional\('(\d+)'")


class PortalError(RuntimeError):
    """Erro de login, sessao ou resposta inesperada do portal."""


@dataclass
class NotaPortal:
    """Uma NFS-e localizada na listagem do portal."""

    rel: str            # identificador interno: "80238255|S"
    numero: str
    data: str
    valor: str
    tomador: str
    mes: int
    ano: int

    @property
    def competencia(self) -> str:
        return f"{self.ano:04d}{self.mes:02d}"


class PortalSimpliss:
    """Cliente do portal do contribuinte (SIMPLISS) para baixar PDFs de NFS-e."""

    def __init__(self, base_url: str, usuario: str, senha: str,
                 inscricao_municipal: str = "", timeout: int = 60):
        self.base_url = base_url.rstrip("/")
        self.usuario = re.sub(r"\D", "", usuario or "")
        self.inscricao_municipal = re.sub(r"\D", "", inscricao_municipal or "")
        self.senha = senha or ""
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/156 Safari/537.36",
        })
        self._autenticado = False

    # ------------------------------------------------------------------ login
    def login(self) -> None:
        """Autentica no portal guardando os cookies de sessao."""
        if not self.usuario or not self.senha:
            raise PortalError("Usuario/senha do portal nao configurados (config.json -> portal).")

        pagina = self.session.get(f"{self.base_url}/contrib/Account/Login", timeout=self.timeout)
        if pagina.status_code != 200:
            raise PortalError(f"Nao foi possivel abrir a pagina de login (HTTP {pagina.status_code}).")

        token = re.search(r'name="__RequestVerificationToken"[^>]*value="([^"]+)"', pagina.text)
        if not token:
            raise PortalError("Token de login nao encontrado na pagina de acesso.")

        resposta = self.session.post(
            f"{self.base_url}/contrib/Account/Login",
            data={
                "__RequestVerificationToken": token.group(1),
                "Login.UserName": self.usuario,
                "Login.Password": self.senha,
            },
            timeout=self.timeout,
            allow_redirects=True,
        )

        if resposta.status_code != 200 or "Login.UserName" in resposta.text:
            raise PortalError("Login recusado pelo portal (verifique CNPJ e senha).")

        self._autenticado = True

    def _garantir_sessao(self) -> None:
        if not self._autenticado:
            self.login()

    def _sessao_invalida(self, resposta) -> bool:
        """Detecta cookie expirado/recusado pelo portal."""
        if resposta.status_code in (401, 403):
            return True
        if "/Account/Login" in resposta.url:
            return True

        tipo = resposta.headers.get("Content-Type", "").lower()
        if "pdf" in tipo or "json" in tipo:
            return False
        if "html" in tipo or not tipo:
            trecho = resposta.text[:4000]
            return "Login.UserName" in trecho or "__RequestVerificationToken" in trecho
        return False

    def _requisitar(self, metodo: str, url: str, **kwargs):
        """Faz a requisicao e, se a sessao caiu, renova uma vez e repete."""
        self._garantir_sessao()
        resposta = self.session.request(metodo, url, timeout=self.timeout, **kwargs)

        if self._sessao_invalida(resposta):
            print("  [AVISO] Sessao expirada; renovando...")
            self.session.cookies.clear()
            self._autenticado = False
            self.login()
            resposta = self.session.request(metodo, url, timeout=self.timeout, **kwargs)

        return resposta

    # --------------------------------------------------------------- listagem
    def _corpo_listagem(self, tamanho: int = 500) -> str:
        partes = [
            "sEcho=1",
            "iColumns=15",
            "sColumns=" + _COLUNAS.replace(",", "%2C"),
            "iDisplayStart=0",
            f"iDisplayLength={tamanho}",
        ]
        for i in range(15):
            # coluna 0 nao e pesquisavel/ordenavel (icone de detalhes)
            pesquisavel = "false" if i == 0 else "true"
            ordenavel = "false" if i == 0 else "true"
            partes.append(f"mDataProp_{i}={i}&sSearch_{i}=&bRegex_{i}=false"
                          f"&bSearchable_{i}={pesquisavel}&bSortable_{i}={ordenavel}")
        partes.append("sSearch=&bRegex=false&iSortCol_0=1&sSortDir_0=asc&iSortingCols=1")
        return "&".join(partes)

    def listar_notas(self, mes: int, ano: int, nacional: int = 3) -> List[NotaPortal]:
        """
        Lista as notas de um mes/ano.

        Args:
            mes: 1-12
            ano: ano com 4 digitos
            nacional: 1=Sim, 2=Nao, 3=Ambos
        """
        self._garantir_sessao()

        url = (
            f"{self.base_url}/contrib/app/nfse/Nfse/_prestadorNfseDataTables"
            f"?Cnpj={self.usuario}&Im={self.inscricao_municipal}&Mes={mes}&Ano={ano}&Nacional={nacional}"
        )
        resposta = self._requisitar(
            "POST",
            url,
            data=self._corpo_listagem(),
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Accept": "application/json, text/javascript, */*; q=0.01",
            },
        )
        if resposta.status_code != 200:
            raise PortalError(f"Falha ao listar notas ({mes:02d}/{ano}): HTTP {resposta.status_code}")

        try:
            dados = resposta.json()
        except ValueError:
            raise PortalError("Resposta inesperada do portal ao listar notas (sessao expirada?).")

        notas: List[NotaPortal] = []
        for linha in dados.get("aaData", []):
            if len(linha) < 4:
                continue
            tomador = _TAG_RE.sub("", str(linha[9])).strip() if len(linha) > 9 else ""
            notas.append(NotaPortal(
                rel=str(linha[0]),
                numero=str(linha[2]).strip(),
                data=str(linha[3]).strip(),
                valor=str(linha[4]).strip(),
                tomador=tomador,
                mes=mes,
                ano=ano,
            ))
        return notas

    def localizar(
        self,
        numeros: List[int],
        mes: Optional[int] = None,
        ano: Optional[int] = None,
        meses_busca: int = 24,
        tentativas: int = 2,
    ) -> Tuple[Dict[int, NotaPortal], List[int]]:
        """
        Localiza as notas pelo numero.

        Se mes/ano nao forem informados, comeca no mes atual e caminha para tras
        ate `meses_busca` meses (ou ate achar todas).

        A prefeitura e instavel e as vezes "esquece" notas que existem: quando
        ainda faltar alguma, a busca e refeita com uma sessao nova e varrendo
        todos os meses (mesmo que mes/ano tenham sido informados).

        Returns:
            (encontradas, nao_encontradas)
        """
        encontradas: Dict[int, NotaPortal] = {}
        pendentes = list(dict.fromkeys(numeros))

        def competencias_padrao() -> List[Tuple[int, int]]:
            hoje = date.today()
            competencias = []
            a, m = hoje.year, hoje.month
            for _ in range(max(1, meses_busca)):
                competencias.append((a, m))
                m -= 1
                if m == 0:
                    a, m = a - 1, 12
            return competencias

        for tentativa in range(1, max(1, tentativas) + 1):
            if not pendentes:
                break

            if tentativa == 1:
                competencias = [(ano, mes)] if mes and ano else competencias_padrao()
            else:
                print(
                    f"  [INFO] Segunda tentativa para {len(pendentes)} nota(s) "
                    "nao localizada(s)..."
                )
                time.sleep(2)
                competencias = competencias_padrao()

            for a, m in competencias:
                if not pendentes:
                    break
                try:
                    notas = self.listar_notas(m, a)
                except PortalError as erro:
                    print(f"  [AVISO] {erro}")
                    continue
                for nota in notas:
                    try:
                        numero = int(nota.numero)
                    except ValueError:
                        continue
                    if numero in pendentes:
                        encontradas[numero] = nota
                        pendentes.remove(numero)
                        print(f"  [OK] NFS-e {numero} encontrada em {m:02d}/{a}")

        return encontradas, pendentes

    # ---------------------------------------------------------------- detalhe
    def dados_impressao(self, rel: str) -> Optional[Tuple[str, str]]:
        """
        Le o detalhe da nota e devolve (id_impressao, chave_50) necessarios
        para montar a URL do PDF.
        """
        url = f"{self.base_url}/contrib/app/nfse/Nfse/_detalhe/{rel.replace('|', '%7C')}"
        resposta = self._requisitar(
            "GET", url, headers={"X-Requested-With": "XMLHttpRequest"}
        )
        if resposta.status_code != 200:
            raise PortalError(f"Falha ao ler detalhe da nota ({rel}): HTTP {resposta.status_code}")

        id_impressao = _IMPRIMIR_RE.search(resposta.text)
        chave = _CHAVE_RE.search(resposta.text)
        if not id_impressao or not chave:
            return None
        return id_impressao.group(1), chave.group(1)

    def baixar_pdf(self, nota: NotaPortal, chave_esperada: Optional[str] = None) -> Optional[Tuple[bytes, str]]:
        """Baixa o PDF da nota. Retorna (conteudo, chave) ou None se nao houver PDF."""
        dados = self.dados_impressao(nota.rel)
        if not dados:
            return None
        id_impressao, chave = dados

        if chave_esperada and chave != chave_esperada:
            raise PortalError(
                f"Chave divergente para a NFS-e {nota.numero}: "
                f"portal={chave[:12]}... esperado={chave_esperada[:12]}..."
            )

        url = f"{self.base_url}/contrib/app/nfse/NotaNacional/_Report?id={id_impressao}_NFS{chave}"
        resposta = self._requisitar(
            "GET", url, headers={"X-Requested-With": "XMLHttpRequest"}
        )
        if resposta.status_code != 200:
            raise PortalError(f"Falha ao baixar PDF da NFS-e {nota.numero}: HTTP {resposta.status_code}")
        if not resposta.content.startswith(b"%PDF"):
            raise PortalError(f"Resposta nao e PDF para a NFS-e {nota.numero}.")
        return resposta.content, chave


# --------------------------------------------------------------------------
# Leitura de XMLs locais (DPS, NFS-e nacional e exportacao 1.02 SIMPLISS)
# --------------------------------------------------------------------------

@dataclass
class NotaXml:
    """NFS-e encontrada em um XML local."""

    numero: int
    chave: str
    competencia: Optional[str]   # AAAAMM
    formato: str
    origem: str
    id_dps: Optional[str] = None
    data: str = ""
    valor: str = ""
    tomador: str = ""


def _local(tag: str) -> str:
    """Nome do elemento sem namespace."""
    return tag.rsplit("}", 1)[-1]


def _texto(elemento, *nomes: str) -> str:
    """Primeiro texto nao vazio entre os elementos filhos com esses nomes."""
    for filho in elemento.iter():
        if _local(filho.tag) in nomes and filho.text and filho.text.strip():
            return filho.text.strip()
    return ""


def _id_dps(elemento) -> Optional[str]:
    """Id do DPS (DPS...) dentro de um infDPS/infNFSe, se houver."""
    for filho in elemento.iter():
        if _local(filho.tag) == "infDPS":
            valor = (filho.get("Id") or "").strip()
            if valor:
                return valor
    return None


def identificar_dps(caminho: str) -> Optional[str]:
    """Le o Id do DPS (ex.: DPS3547...) de um XML de entrada, se existir."""
    try:
        raiz = ET.parse(caminho).getroot()
    except (ET.ParseError, OSError):
        return None
    for elemento in raiz.iter():
        if _local(elemento.tag) == "infDPS":
            valor = (elemento.get("Id") or "").strip()
            if valor:
                return valor
    return None


def _texto_tomador(elemento) -> str:
    """Razao social do tomador dentro de <toma> (formato nacional)."""
    for filho in elemento.iter():
        if _local(filho.tag) == "toma":
            return _texto(filho, "xNome")
    return ""


def _competencia(texto: str) -> Optional[str]:
    """'2026-02-19' ou '2026-02-19T11:12:27-03:00' -> '202602'."""
    if not texto or len(texto) < 7:
        return None
    ano_mes = texto[:7].replace("-", "").replace("/", "")
    return ano_mes if ano_mes.isdigit() and len(ano_mes) == 6 else None


def extrair_notas_xml(caminho: str) -> Tuple[List[NotaXml], List[str], List[str]]:
    """
    Le um XML local e devolve as NFS-e que ele representa.

    Entende tres formatos, detectados pelo conteudo (nao pelo nome do arquivo):
      - NFS-e nacional : <NFSe><infNFSe Id="NFS..."><nNFSe>..</nNFSe>
      - Exportacao 1.02: <NOTAS><NOTA><NUMERO>..</NUMERO><CD_VERIFICACAO>NFS..</...>
      - DPS            : <DPS><infDPS> (ainda sem NFS-e, nao gera PDF)

    Returns:
        (notas, avisos, dps_sem_nota)
    """
    nome = Path(caminho).name
    notas: List[NotaXml] = []
    avisos: List[str] = []
    dps: List[str] = []

    try:
        raiz = ET.parse(caminho).getroot()
    except ET.ParseError as erro:
        return [], [f"{nome}: XML invalido ({erro})"], []
    except OSError as erro:
        return [], [f"{nome}: nao foi possivel ler ({erro})"], []

    achou_nota = False

    for elemento in raiz.iter():
        tag = _local(elemento.tag)

        if tag == "infNFSe":
            achou_nota = True
            chave = re.sub(r"^NFS", "", (elemento.get("Id") or "").strip())
            numero = _texto(elemento, "nNFSe")
            competencia = _competencia(_texto(elemento, "dCompet", "dhEmi"))
            if not numero.isdigit() or len(chave) != 50:
                avisos.append(f"{nome}: infNFSe sem numero/chave validos")
                continue
            notas.append(NotaXml(
                numero=int(numero),
                chave=chave,
                competencia=competencia,
                formato="NFSe nacional",
                origem=nome,
                id_dps=_id_dps(elemento),
                data=_texto(elemento, "dhEmi")[:10],
                valor=_texto(elemento, "vLiq"),
                tomador=_texto_tomador(elemento),
            ))

        elif tag == "NOTA":
            achou_nota = True
            chave = re.sub(r"^NFS", "", _texto(elemento, "CD_VERIFICACAO"))
            numero = _texto(elemento, "NUMERO")
            competencia = _competencia(_texto(elemento, "DT_COMPETENCIA"))
            if not numero.isdigit() or len(chave) != 50:
                avisos.append(f"{nome}: NOTA (1.02) sem numero/chave validos")
                continue
            notas.append(NotaXml(
                numero=int(numero),
                chave=chave,
                competencia=competencia,
                formato="SIMPLISS 1.02",
                origem=nome,
                data=_texto(elemento, "DT_COMPETENCIA")[:10],
                valor=_texto(elemento, "VL_SERVICO"),
                tomador=_texto(elemento, "TOM_RAZAO_SOCIAL"),
            ))

    if not achou_nota:
        for elemento in raiz.iter():
            if _local(elemento.tag) == "infDPS":
                numero = _texto(elemento, "nDPS")
                dps.append(f"{nome}: DPS {numero or '-'}")
                break

    return notas, avisos, dps
