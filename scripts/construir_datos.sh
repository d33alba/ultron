#!/usr/bin/env bash
# Construye en Linux lo que no se puede preparar en Windows: voz Piper, Node 24 y el Ojo.
set -euo pipefail
D=/tmp/ultron-datos
rm -rf "$D" /tmp/datos-linux.tar.gz
mkdir -p "$D/voz" "$D/ojo"
bajar() {  # bajar URL [archivo]; sin archivo, a la salida estándar
    python3 -c 'import shutil,sys,urllib.request as u
r=u.urlopen(u.Request(sys.argv[1],headers={"User-Agent":"ultron"}),timeout=120)
o=open(sys.argv[2],"wb") if len(sys.argv)>2 else sys.stdout.buffer
shutil.copyfileobj(r,o)' "$@"
}

echo "== voz"
cd "$D/voz"
bajar https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_x86_64.tar.gz | tar xz
B=https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_ES/davefx/medium
bajar "$B/es_ES-davefx-medium.onnx" es_ES-davefx-medium.onnx
bajar "$B/es_ES-davefx-medium.onnx.json" es_ES-davefx-medium.onnx.json

echo "== node"
cd /tmp
DIST=https://nodejs.org/dist/latest-v24.x
bajar "$DIST/SHASUMS256.txt" shasums.txt
NOMBRE=$(grep -o 'node-v[0-9.]*-linux-x64.tar.xz' shasums.txt | head -1)
bajar "$DIST/$NOMBRE" "$NOMBRE"
grep " $NOMBRE\$" shasums.txt | sha256sum -c -
tar xJf "$NOMBRE"
mv "${NOMBRE%.tar.xz}" "$D/node"
export PATH="$D/node/bin:$PATH"
node --version

echo "== ojo"
cd "$D/ojo"
bajar https://codeload.github.com/bilawalsidhu/gods-eye-view/tar.gz/refs/heads/main | tar xz
mv gods-eye-view-main gods-eye-view
cd gods-eye-view
npm ci --no-audit --no-fund
npm run doctor
echo ok > "$D/ojo/instalado"

cd "$D"
tar czf /tmp/datos-linux.tar.gz voz node ojo
ls -la /tmp/datos-linux.tar.gz
echo CONSTRUIDO
