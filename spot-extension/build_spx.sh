#!/usr/bin/env bash
# Build the Spot CORE I/O Extension package (arm64). Needs Docker with buildx;
# arm64 is emulated through qemu, so no Jetson is required.
set -euo pipefail

cd "$(dirname "$0")"

NAME="spot_thermal_relay"
TAG="spot-thermal-relay:1.0.0"
OUT="${NAME}.spx"

echo "==> Staging the spot_glass package into the build context"
rm -rf ./spot_glass
cp -r ../spot_glass ./spot_glass
trap 'rm -rf ./spot_glass' EXIT

echo "==> Registering qemu for arm64"
docker run --privileged --rm tonistiigi/binfmt --install arm64 >/dev/null

echo "==> Building ${TAG} for linux/arm64"
docker buildx build --platform linux/arm64 -t "${TAG}" --load .

# Bundle cloudflared too: the CORE I/O may have no internet at install time.
echo "==> Pulling cloudflared (arm64)"
docker pull --platform linux/arm64 cloudflare/cloudflared:latest

echo "==> Saving images"
docker save "${TAG}" cloudflare/cloudflared:latest | gzip > images.tgz

echo "==> Packaging ${OUT}"
rm -f "${OUT}"
tar zcvf "${OUT}" manifest.json docker-compose.yml icon.png images.tgz

echo
ls -lh "${OUT}"
echo "Install via the CORE I/O web portal: Extensions -> Upload New Extension."
