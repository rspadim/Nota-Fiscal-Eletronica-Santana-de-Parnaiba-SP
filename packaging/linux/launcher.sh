#!/bin/sh
# Launcher do NFS-e Santana (Linux).
#
# Usa ~/.config/nfse-santana/config.json. Se nao existir, copia o modelo e
# avisa para preencher, em vez de simplesmente falhar.
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/nfse-santana"
CONFIG="$CONFIG_DIR/config.json"

mkdir -p "$CONFIG_DIR"

if [ ! -f "$CONFIG" ]; then
    cp /opt/nfse-santana/config.json.exemplo "$CONFIG"
    echo "Primeira execucao: criei $CONFIG a partir do modelo."
    echo "Preencha os dados (certificado, CNPJ, senha do portal) e rode de novo."
    echo "Modelo: /opt/nfse-santana/config.json.exemplo"
    echo "Ajuda:  /opt/nfse-santana/configuracao.txt"
    exit 1
fi

cd "$CONFIG_DIR" || exit 1
exec /opt/nfse-santana/nfse-santana "$@"
