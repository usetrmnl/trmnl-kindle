#!/bin/sh
# Run on your computer to turn the editable SVGs into Kindle prompt images.
set -eu
cd "$(dirname "$0")/.."
for action in touch button; do
  magick -background white "images/exit-prompts/$action.svg" -resize 600x200 \
    -alpha remove -alpha off -colorspace Gray -depth 8 -strip -define png:color-type=0 \
    "zip_example/exit-$action.png"
done
