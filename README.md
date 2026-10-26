# Sistema de Emissão de NFS-e - Santana de Parnaíba

Sistema Python para emissão de Notas Fiscais de Serviços Eletrônicas (NFS-e) pela Prefeitura de Santana de Parnaíba através da plataforma SIMPLISS.

Rode o `python3 main.py` com o arquivo `config.json` preenchido, e as notas na pasta de entrada configurada.

## 🎬 Demonstração

### Menu do Sistema
![Exemplo funcionamento](./Exemplo%20funcionamento.png)

### Integração com SIMPLISS
![Site Prefeitura](./site%20prefeitura.png)

## 🚀 Início Rápido

### 1. Instalação de Dependências

```bash
pip install -r requirements.txt
```

As versões são fixas (`requirements.txt`) para o build ser reproduzível e
funcionar de **Python 3.8** (Ubuntu 20.04) a **3.14** (Ubuntu 26.04).

Opcional, para rodar os testes e o lint como o CI faz:

```bash
pip install ruff
python -m unittest discover -s tests -v
ruff check src tests
```

### 2. Configuração

1. Copie `config.json.exemplo` para criar seu `config.json` na mesma pasta do `main.py`:
```bash
cp config.json.exemplo config.json
```

2. Edite `config.json` com seus dados:
   - Certificado digital (caminho .pem)
   - CNPJ e inscrição municipal
   - URLs dos servidores

### 3. Executar

```bash
cd src
python main.py
```

Escolha uma opção no menu:
- **1**: Emitir NFS-e (arquivo específico)
- **2**: Consultar NFS-e
- **3**: Cancelar NFS-e (manual)
- **4**: Cancelamento assistido
- **5**: Emitir em lote (pasta)
- **6**: Importar lote de arquivo ZIP
- **7**: Baixar PDF de NFS-e (por número)
- **8**: Baixar PDFs a partir de XML (arquivo/pasta)
- **9**: Gerar índice dos PDFs (CSV)
- **0**: Alternar modo simulação (dry-run)
- **10**: Sair

### Baixar PDFs (DANFSE)

Por número(s) — aceita faixas e listas:

```bash
cd src
python main.py pdf 67
python main.py pdf 65-72,80,90-92
python main.py pdf 65-72 10 2026   # opcional: mês e ano
```

A partir de XMLs locais (pasta é varrida recursivamente):

```bash
cd src
python main.py pdf-xml ../nfse_emitidas
python main.py pdf-xml "C:\\caminho\\nota.xml"
```

Aceita os três formatos encontrados na prática, identificados pelo conteúdo:

| Formato | Como reconhece | Nº da nota |
| --- | --- | --- |
| NFS-e nacional | `<NFSe><infNFSe Id="NFS...">` | `nNFSe` |
| Exportação 1.02 SIMPLISS | `<NOTAS><NOTA>` | `NUMERO` + `CD_VERIFICACAO` |
| DPS (ainda sem nota) | `<DPS><infDPS>` | ignorado, com aviso |

A competência do XML é usada como atalho para achar o mês no portal. A chave
do XML é conferida contra a do portal antes de salvar, e notas não localizadas
são procuradas **duas vezes** (a segunda com sessão nova e varredura de 24
meses), porque a prefeitura às vezes "esquece" notas antigas.

Saída: `nfse_emitidas/pdf/<AAAAMM>/nfse_<numero>_<chave>.pdf` (não sobrescreve).

### Índice dos PDFs

```bash
cd src
python main.py indice
```

Gera `nfse_emitidas/pdf/indice.csv` (separador `;`, UTF-8 com BOM para abrir
direto no Excel) com número, competência, data, valor, tomador, chave, formato
e o caminho do PDF. A lista vem dos XMLs em `nfse_emitidas/`, então notas sem
PDF também aparecem — com a coluna `pdf` vazia.

### Aviso de reenvio

Ao emitir (opção 1), o sistema confere o `Id` da DPS contra os XMLs já
emitidos em `nfse_emitidas/`. Se a mesma DPS já virou nota, avisa e pede
confirmação antes de enviar. No lote (opção 5) o aviso é impresso, mas o
processamento continua — o portal é a fonte da verdade.

### Modo simulação (dry-run)

```bash
cd src
python main.py --dry-run pdf 65-72
python main.py -n lote ../nfse_entrada
```

No modo simulação nada é emitido, baixado ou movido: o sistema mostra o que
faria (inclusive no lote e no ZIP). Nem consulta o portal para baixar PDF — só
lista as notas e informa o destino. No menu, a opção **0** liga/desliga o modo.

### Importar ZIP

```bash
cd src
python main.py zip ../nfse_entrada/rspadim-20261024-18-2136.ZIP
```

O sistema cria a pasta `rspadim-20261024-18-2136/` ao lado do ZIP, extrai os XMLs,
emite o lote e move o ZIP para `processados/`. Se a pasta já existir, ela é
reaproveitada (retoma lote interrompido) e nada é sobrescrito.

## 📁 Estrutura

```
.
├── README.md                              ← 📖 Você está aqui
├── Exemplo funcionamento.png              ← 🎬 Menu do sistema
├── site prefeitura.png                    ← 🌐 Integração SIMPLISS
├── config.json.exemplo                    ← Template de configuração
├── requirements.txt                       ← Dependências Python (versões fixas)
├── requirements-build.txt                 ← Dependências do build (PyInstaller)
├── LICENSE                                ← MIT
├── .gitattributes                         ← Line endings (LF nos .sh)
├── installer.iss                          ← Instalador Windows (Inno Setup)
├── nfse.spec                              ← Build do executável (PyInstaller)
├── packaging/linux/                       ← Empacotamento .deb
├── .gitignore                             ← Configuração git
├── src/
│   ├── main.py                           ← 🎯 EXECUTE ESTE ARQUIVO
│   ├── nfse_simples.py                   ← Cliente HTTP
│   ├── nfse_pdf.py                       ← Portal SIMPLISS (PDF) + leitor de XML
│   ├── assinador_dps.py                  ← Assinatura digital
│   ├── teste_certificado.py              ← Validação
│   └── ...
├── tests/
│   └── test_nfse_pdf.py                  ← Testes unitários (offline)
├── .github/workflows/ci.yml              ← CI (testes + lint)
├── nfse_entrada/                         ← Coloque XMLs aqui
├── nfse_emitidas/                        ← NFS-es emitidas (automático)
└── nfse_enviadas/                        ← XMLs assinados (automático)
```

## ⚙️ Configuração (config.json)

```json
{
  "ambiente": "producao",
  "certificado": {
    "caminho_cert": "c:\\certificado.pem",
    "caminho_chave": "",
    "senha": "Senha"
  },
  "empresa": {
    "cnpj": "123456789",
    "inscricao_municipal": "12345",
    "razao_social": "Nome Empresa",
    "logradouro": "Rua",
    "numero": "16",
    "complemento": "Complemento",
    "bairro": "Bairro",
    "cidade": "Santana de Parnaíba",
    "estado": "SP",
    "cep": "CEPPP-PPP",
    "email": "rspadim@gmail.com.br"
  },
  "portal": {
    "url": "https://santanadeparnaiba.simplissweb.com.br",
    "usuario": "SEU_CNPJ_APENAS_NUMEROS",
    "senha": "SUA_SENHA_DO_PORTAL"
  },
  "nfse": {
    "caminho_xml_entrada": "c:/santana-parnaiba-xml/nfse_entrada",
    "caminho_xml_enviados": "c:/santana-parnaiba-xml/nfse_enviadas",
    "caminho_xml_saida": "c:/santana-parnaiba-xml/nfse_emitidas",
    "salvar_xml_assinado": true,
    "salvar_xml_resposta": true
  },
  "url_homologacao": "https://producaorestrita.simplissweb.com.br/api/v1",
  "url_producao": "https://nfsesantanadeparnaiba.simplissweb.com.br"
}
```

---

O bloco `portal` é usado só para baixar PDFs (opções 7 e 8). A `senha` é a do
portal do contribuinte, **diferente** da senha do certificado. `usuario` aceita
CNPJ com ou sem pontuação; a inscrição municipal vem de `empresa`.

## 🧪 Testes e CI

```bash
python -m unittest discover -s tests -v
```

Os testes rodam offline: cobrem o parser de números (`1-4,10-11,5,99`, `1 a 4`),
a leitura dos três formatos de XML, o cálculo de competência, a detecção de
sessão expirada, o retry de duas tentativas em `localizar` e a gravação
idempotente dos PDFs. Nenhum teste acessa o portal.

O workflow `.github/workflows/ci.yml` roda esses testes e o lint (`ruff`) em
todo push na `main` e em pull requests.

## 📋 Fluxo de Emissão

1. ✅ XML é lido
2. ✅ Validação do formato
3. ✅ **Assinatura digital** com certificado (SHA256)
4. ✅ Cópia assinada salva em `nfse_enviadas/` (.sign.xml)
5. ✅ Compactação em GZip + Base64
6. ✅ Envio ao servidor SIMPLISS
7. ✅ NFS-e retornada salva em `nfse_emitidas/`

## 🧾 Logs

Um arquivo por dia em `logs/execucao_AAAAMMDD.log`, com retenção de **30 dias**
(arquivos mais antigos são apagados automaticamente). Configurável:

```json
"log": {
  "pasta": "./logs",
  "retencao_dias": 30
}
```

No executável instalado, a pasta padrão é `logs/` ao lado do `.exe`.

## 📦 Executável e Instalador

### Build local

```bash
pip install -r requirements-build.txt
pyinstaller nfse.spec --noconfirm
iscc installer.iss
```

Saídas:
- `dist/nfse-santana/` — programa (36 MB, roda sem Python instalado)
- `dist/instalador/nfse-santana-1.0.0-setup.exe` — instalador Inno Setup

O instalador cria atalhos, instala em `%LOCALAPPDATA%\Programs\NFS-e Santana`
(sem pedir administrador) e, na primeira instalação, copia
`config.json.exemplo` para `config.json`. O `config.json` do build **não é
embutido**, para não carregar senha e certificado dentro do executável.

### Release automática

O workflow `.github/workflows/build.yml` roda em tags `v*` (ou manualmente):
testa, gera o `.exe` com PyInstaller, monta o instalador e anexa na release.

```bash
git tag v1.0.0 && git push origin v1.0.0
```

## 🔑 Certificado Digital

### Converter .pfx para .pem

```bash
openssl pkcs12 -in seu_certificado.pfx -out certificado_spa.pem -nodes
```

### Configurar

```json
"certificado": {
  "caminho_cert": "./certificado_spa.pem"
}
```

## 🌐 Ambientes

| Ambiente | tpAmb | URL |
|----------|-------|-----|
| Homologação (teste) | 2 | https://producaorestrita.simplissweb.com.br |
| Produção | 1 | https://nfsesantanadeparnaiba.simplissweb.com.br |

### Importante
- XML com `<tpAmb>2</tpAmb>` → usar homologação
- XML com `<tpAmb>1</tpAmb>` → usar produção
- Configurar `"ambiente"` no config.json de acordo

## 📝 Geração do ID da DPS

O ID deve ter exatamente **45 caracteres** (DPS + 42 dígitos):

```
DPS + Cód.Mun(7) + TipoInsc(1) + Inscrição(14) + Série(5) + Número(15)
```

**Exemplo:**
```
DPS3547304111222333000181000000000000000001
```

## ✅ Checklist

- [ ] Python 3.8+ instalado
- [ ] Dependências instaladas: `pip install -r requirements.txt`
- [ ] Certificado digital em .pem
- [ ] `config.json` criado com suas configurações
- [ ] `python src/teste_certificado.py` passou OK
- [ ] XML de teste gerado
- [ ] `python src/main.py` funcionando

## 🐛 Solução de Problemas

| Erro | Solução |
|------|---------|
| "config.json não encontrado" | Execute: `cp config.json.exemplo config.json` |
| "Certificado não encontrado" | Verifique caminho em config.json |
| "XML inválido" | Valide estrutura do XML |
| "E0010 - Série inválida" | Verificar tipo de emissão (`tpEmit`) |
| "ECXXXX - Série diverge" | ID da DPS deve conter a série correta (5 dígitos) |

## 📞 Suporte

**SIMPLISS:**
- https://www.simplissweb.com.br
- Swagger Homologação: https://producaorestrita.simplissweb.com.br/swagger/index.html

**Santana de Parnaíba:**
- https://www.santanadeparnaiba.sp.gov.br
- Telefone: (19) 3602-3600

## 📄 Licença

MIT — use, modifique e redistribua livremente, inclusive comercialmente, desde
que o aviso de copyright e a licença sejam mantidos. Veja [LICENSE](LICENSE).

Se usar este projeto em algo que vá para produção, um aviso ao autor é
apreciado (não obrigatório): rspadim@gmail.com.

### Aviso

Este software não é oficial da Prefeitura de Santana de Parnaíba nem da
SIMPLISS. Ele automatiza o portal do contribuinte com as credenciais do
próprio usuário. A responsabilidade pela exatidão das notas emitidas é de quem
opera o sistema — confira antes de transmitir em produção.
