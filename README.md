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
- **3**: Cancelar NFS-e
- **4**: Emitir em lote
- **5**: Sair

## 📁 Estrutura

```
.
├── README.md                              ← 📖 Você está aqui
├── Exemplo funcionamento.png              ← 🎬 Menu do sistema
├── site prefeitura.png                    ← 🌐 Integração SIMPLISS
├── config.json.exemplo                    ← Template de configuração
├── requirements.txt                       ← Dependências Python
├── .gitignore                             ← Configuração git
├── src/
│   ├── main.py                           ← 🎯 EXECUTE ESTE ARQUIVO
│   ├── nfse_simples.py                   ← Cliente HTTP
│   ├── assinador_dps.py                  ← Assinatura digital
│   ├── teste_certificado.py              ← Validação
│   └── ...
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

## 📋 Fluxo de Emissão

1. ✅ XML é lido
2. ✅ Validação do formato
3. ✅ **Assinatura digital** com certificado (SHA256)
4. ✅ Cópia assinada salva em `nfse_enviadas/` (.sign.xml)
5. ✅ Compactação em GZip + Base64
6. ✅ Envio ao servidor SIMPLISS
7. ✅ NFS-e retornada salva em `nfse_emitidas/`

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
DPS3547304110280942000124700000000000000001
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

Sistema fornecido para integração com SIMPLISS.
