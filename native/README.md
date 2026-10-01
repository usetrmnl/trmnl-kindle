# Maintaining the exit prompt

The shipped `zip_example/exit-input` is ready to use. Rebuild it when changing the C helper.

## Build the helper

With Docker installed and network access available, run from the repository root:

```sh
docker build --pull=false -t trmnl-exit-toolchain -f native/Dockerfile native
mkdir -p /tmp/trmnl-native-build
docker run --rm -v "$PWD:/work" -v /tmp/trmnl-native-build:/build \
  trmnl-exit-toolchain sh tools/build-exit-input.sh /build
```

The script replaces `zip_example/exit-input` and prints its checksum. It saves the compiler in `/tmp/trmnl-native-build` for reuse and writes `exit-input.map` there to show which code was included. No compiler or extra library needs to be installed on the Kindle.

## Run local tests

Build the image above and have `busybox:1.36.1` available locally. From the repository root:

```sh
docker run --rm --init --pull=never --network=none -v "$PWD:/work:ro" \
  trmnl-exit-toolchain python3 tests/native-reader.py
python3 tests/early-wake-exit.py
python3 tests/network-recovery.py
docker run --rm --pull=never --network=none -v "$PWD:/work:ro" -w /work \
  busybox:1.36.1 sh -n zip_example/TRMNL.sh zip_example/utils.sh
```

These tests simulate device input and check confirmation, timeouts, restoration and network recovery without contacting a Kindle. Keep `--init`: without it, the helper treats the test runner as a missing parent and cancels.

## Edit the pictures

Edit `images/exit-prompts/touch.svg` or `images/exit-prompts/button.svg`. With ImageMagick installed, run from the repository root:

```sh
sh tools/export-exit-prompts.sh
```

The exporter writes `zip_example/exit-touch.png` and `zip_example/exit-button.png`: 600×200 grayscale images. Keep explicit `stroke-opacity` values for ImageMagick. The Kindle displays the images without resizing or rotating them.

The prompt SVGs and their exported PNGs are dedicated to the public domain under [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/).

## Troubleshoot

Read `exit-status.log` beside `TRMNL.sh` for skipped prompts, confirmation results and restoration failures. It keeps one backup and contains no credentials, URLs or touch coordinates.

Check that `exit-input` is executable and both prompt PNGs are present. Unsupported input or unreadable original settings can disable confirmation. From the installed extension directory on the Kindle, this checks the helper's processor compatibility without reading input or drawing:

```sh
./exit-input --check
```

The helper returns these exit codes. TRMNL records the corresponding reason in the log.

| Code | Meaning |
| --- | --- |
| 0 | Confirmed |
| 1 | No confirmation before timeout |
| 2 | Could not take exclusive access to input |
| 3 | Could not read input state or the clock |
| 4 | The input system lost events |
| 5 | Could not read input events |
| 6 | Drawing failed or took too long |
| 7 | Cancelled by a signal |
| 8 | Input was still held after the release wait |
| 9 | Unsupported device, key, arguments or processor |
| 10 | Input was already held during setup |

For detailed input handling, see [exit-input.c](exit-input.c) and [utils.sh](../zip_example/utils.sh).

## Package

Distribute the `zip_example` files with `exit-input` executable (mode 755). Preserve users' credentials and settings when updating. Device-only distributions must include the root [MIT licence](../LICENSE) and [musl notice](../LICENSES/musl-COPYRIGHT); repository Download ZIPs already contain them. Separate GCC licence texts are unnecessary for this helper under the [Runtime Library Exception](https://www.gnu.org/licenses/gcc-exception-3.1.en.html).

## Tested devices

Tested on Voyage firmware 5.13.6: timeout resumed the dashboard; touch confirmation exited to clean Home and restored settings and services. Other models, physical buttons and the KUAL stop command still need device testing.
