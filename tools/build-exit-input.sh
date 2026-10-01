#!/bin/sh
# Run inside the Docker image described in native/README.md.
set -eu
repo=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
. "$repo/native/toolchain.env"
export SOURCE_DATE_EPOCH LC_ALL=C TZ=UTC
build_root=${1:-/build}
mkdir -p "$build_root"
if [ ! -d "$build_root/musl-cross-make/.git" ]; then
    git clone https://github.com/richfelker/musl-cross-make.git "$build_root/musl-cross-make"
fi
cd "$build_root/musl-cross-make"
git checkout --detach "$MUSL_CROSS_COMMIT"
# Reject edits to compiler build scripts; config.mak is generated separately.
git diff --quiet && git diff --cached --quiet
cp "$repo/native/toolchain.config" config.mak
# Check download hashes before unpacking or building the compiler sources.
make $(awk '{print $2}' "$repo/native/toolchain.sha256")
sha256sum -c "$repo/native/toolchain.sha256"
make -j8 OUTPUT="$build_root/toolchain"
make install OUTPUT="$build_root/toolchain"
cc="$build_root/toolchain/bin/arm-linux-musleabi-gcc"
# Keep build paths and dates out of the binary, and include the C library.
"$cc" -std=c11 -Os -static -march=armv6 -mfloat-abi=soft -Wall -Wextra -Werror \
    -ffile-prefix-map="$repo"=. -Wl,--build-id=none \
    -Wl,-Map,"$build_root/exit-input.map" \
    "$repo/native/exit-input.c" -o "$build_root/exit-input"
"$build_root/toolchain/bin/arm-linux-musleabi-strip" "$build_root/exit-input"
cp "$build_root/exit-input" "$repo/zip_example/exit-input"
chmod 755 "$repo/zip_example/exit-input"
"$build_root/toolchain/bin/arm-linux-musleabi-readelf" -h -A -l "$repo/zip_example/exit-input"
cd "$repo/zip_example"
sha256sum exit-input
