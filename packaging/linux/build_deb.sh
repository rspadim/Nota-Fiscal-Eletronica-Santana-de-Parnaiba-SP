#!/bin/sh
# Gera o pacote .deb do NFS-e Santana para a distribuicao informada.
#
# Uso (dentro do container da distro alvo):
#   VERSION=1.0.0 DISTRO=22.04 SUITE=jammy ./packaging/linux/build_deb.sh
#
# Espera o executavel gerado pelo PyInstaller em dist/nfse-santana/.
set -eu

VERSAO="${VERSAO:-${VERSION:-1.0.0}}"
DISTRO="${DISTRO:-22.04}"
SUITE="${SUITE:-jammy}"
ARQUITETURA="${ARQUITETURA:-amd64}"
APP="nfse-santana"
ORIGEM="$(cd "$(dirname "$0")/../.." && pwd)"
BUILD="${ORIGEM}/build/deb/${SUITE}"

rm -rf "${BUILD}"
mkdir -p "${BUILD}/DEBIAN" \
         "${BUILD}/opt/${APP}" \
         "${BUILD}/usr/bin" \
         "${BUILD}/usr/share/applications" \
         "${BUILD}/usr/share/doc/${APP}"

# programa
cp -r "${ORIGEM}/dist/${APP}/." "${BUILD}/opt/${APP}/"
chmod 755 "${BUILD}/opt/${APP}/${APP}"

# config modelo e nota de instalacao
install -m 644 "${ORIGEM}/config.json.exemplo" "${BUILD}/opt/${APP}/config.json.exemplo"
install -m 644 "${ORIGEM}/packaging/linux/configuracao.txt" \
    "${BUILD}/usr/share/doc/${APP}/configuracao.txt"
install -m 644 "${ORIGEM}/packaging/linux/configuracao.txt" \
    "${BUILD}/opt/${APP}/configuracao.txt"
install -m 644 "${ORIGEM}/README.md" "${BUILD}/usr/share/doc/${APP}/README.md"

# launcher: usa o config do usuario
install -m 755 "${ORIGEM}/packaging/linux/launcher.sh" "${BUILD}/usr/bin/${APP}"

cat > "${BUILD}/usr/share/applications/${APP}.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=NFS-e Santana
Comment=Emissao de NFS-e - Santana de Parnaiba (SIMPLISS)
Exec=${APP}
Terminal=true
Categories=Office;Finance;
DESKTOP

SIZE=$(du -sk "${BUILD}" | cut -f1)
cat > "${BUILD}/DEBIAN/control" <<CONTROL
Package: ${APP}
Version: ${VERSAO}
Section: misc
Priority: optional
Architecture: ${ARQUITETURA}
Maintainer: Spadim <rspadim@gmail.com>
Installed-Size: ${SIZE}
Depends: libc6, libssl3 | libssl3t64 | libssl1.1, libxml2 | libxml2-16, libxslt1.1, zlib1g
Description: Emissao de NFS-e para Santana de Parnaiba (SIMPLISS)
 Aplicativo de linha de comando para emitir, consultar, cancelar e
 baixar os PDFs (DANFSE) das notas de servico do municipio, com o
 certificado digital A1.
 .
 Configuracao em ~/.config/nfse-santana/config.json
 Logs em ~/.local/state/nfse-santana/logs (30 dias de retencao)
 .
 Build para Ubuntu ${DISTRO} (${SUITE}).
CONTROL

cat > "${BUILD}/DEBIAN/postinst" <<'POSTINST'
#!/bin/sh
set -e
# permissoes padrao; nada e gravado em /opt (logs ficam no perfil do usuario)
chmod -R go-w /opt/nfse-santana 2>/dev/null || true
POSTINST
chmod 755 "${BUILD}/DEBIAN/postinst"

SAIDA="${ORIGEM}/dist/linux"
mkdir -p "${SAIDA}"
DEB="${SAIDA}/${APP}_${VERSAO}~ubuntu${DISTRO}_${ARQUITETURA}.deb"
dpkg-deb --root-owner-group --build "${BUILD}" "${DEB}"
echo "Gerado: ${DEB}"
