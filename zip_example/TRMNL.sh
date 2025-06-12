#!/bin/sh
source ./utils.sh

###############################################################################
# TRMNL.sh
#
# Kindle-friendly shell script that:
#  1. Prints debug messages on-screen using eips
#  2. Fetches JSON from TRMNL's API
#  3. Parses out the image URL and refresh rate
#  4. Downloads the image by POSTing the entire JSON response to the proxy
#  5. Displays the image via eips
#  6. Prints the FULL image URL and FULL filename below the displayed image
#  7. Loops, sleeping for <refresh_rate> seconds
###############################################################################
#
# ----------------------------- USER SETTINGS -------------------------------- #
API_KEY=$(cat apikey.txt)
BASE_URL="https://trmnl.app"
RSSI="0"
USER_AGENT="trmnl-display/0.1.1"
DEBUG_MODE=false  # Set to true to enable debug messages, false to disable
DIR="$(dirname "$0")"

# Temporary folder to hold downloaded files
TMP_DIR="/tmp/trmnl-kindle"
mkdir -p "$TMP_DIR"

# Coordinates for displaying the PNG in *pixels*
DISPLAY_X=75
DISPLAY_Y=25

# Size of the PNG in *pixels*
PNG_WIDTH=$(get_kindle_height)
PNG_HEIGHT=$(get_kindle_width)
ROTATION=90

# ---------------------------------------------------------------------------- #

# If eips is not found (i.e. running locally), define a no-op stub for testing
if ! command -v eips >/dev/null 2>&1; then
  eips() {
    # Simply echo to console so you can see what *would* happen on Kindle
    echo "[eips STUB] $*"
  }
fi

# Helper to track a text-based "cursor" for debug lines
DEBUG_X=0
DEBUG_Y=0

# Prints debug lines in text mode at the next (col=DEBUG_X, row=DEBUG_Y)
# and increments DEBUG_Y for each new line.
eips_debug() {
  if [ "$DEBUG_MODE" = true ]; then
    eips "${DEBUG_X}" "${DEBUG_Y}" "$1"
    echo "$1" #Also echo to terminal
    DEBUG_Y=$((DEBUG_Y+1))
  fi
}

init() {
  /etc/init.d/framework stop
  initctl stop webreader >/dev/null 2>&1
  echo powersave >/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor
  lipc-set-prop com.lab126.powerd preventScreenSaver 1
}

init
while true; do
  # Clear the screen only if in debug mode, otherwise clear right before displaying the image
  if [ "$DEBUG_MODE" = true ]; then
    eips -c
    sleep 1
  fi

  # Reset debug text row
  DEBUG_Y=0

  # 1) Indicate the start of a new loop
  eips_debug "TRMNL Kindle Debug Script"

  eips_debug "Wait for wifi..."
  # enable wireless if it is currently off
  if [ 0 -eq `lipc-get-prop com.lab126.cmd wirelessEnable` ]; then
    eips_debug "WiFi is off, turning it on now"
    lipc-set-prop com.lab126.cmd wirelessEnable 1
    #lipc-set-prop com.lab126.wifid enable 1 
    DISABLE_WIFI=1
  fi
  "$DIR/wait-for-wifi.sh" "$WIFI_TEST_IP"

  eips_debug "Fetching JSON..."

  # 2) Fetch JSON metadata
  BATTERY_VOLTAGE=$(get_kindle_battery)
  RESPONSE="$(
    curl -s \
      -H "access-token: $API_KEY" \
      -H "battery-voltage: $BATTERY_VOLTAGE" \
      -H "png-width: $PNG_WIDTH" \
      -H "png-height: $PNG_HEIGHT" \
      -H "rssi: $RSSI" \
      -A "$USER_AGENT" \
      "${BASE_URL}/api/display"
  )"

  # If no response, display error and retry
  if [ -z "$RESPONSE" ]; then
    eips_debug "Error: No JSON response."
    eips_debug "Retry in 60s..."
    sleep 60
    continue
  fi

  # Show part of the JSON in debug (trim if it's too long)
  SHORT_JSON="$(echo "$RESPONSE" | cut -c1-60)"
  eips_debug "JSON: ${SHORT_JSON}..."

  # 3) Parse JSON (naive sed approach)
  IMAGE_URL=$(echo "$RESPONSE" | sed -n 's/.*"image_url":"\([^"]*\)".*/\1/p' | sed 's/\\u0026/\&/g')
  eips_debug "ORIGINAL_URL: ${IMAGE_URL}"

  REFRESH_RATE=$(echo "$RESPONSE" | sed -n 's/.*"refresh_rate":\([^,}]*\).*/\1/p')
  [ -z "$REFRESH_RATE" ] && REFRESH_RATE="60"

  # Quick check for missing URL
  if [ -z "$IMAGE_URL" ]; then
    eips_debug "Error: Unable to parse image_url from JSON."
    eips_debug "Retry in 60s..."
    sleep 60
    continue
  fi

  # --- Extract filename directly from the top-level JSON field if present ---
  FILENAME=$(echo "$RESPONSE" | sed -n 's/.*"filename":"\([^"]*\)".*/\1/p')

  # If the JSON has no "filename" field or is empty, try extracting from the URL
  if [ -z "$FILENAME" ]; then
    # Try to get filename from URL path
    FILENAME=$(echo "$IMAGE_URL" | sed -n 's/.*\/\([^?/]*\)\?.*/\1/p')
    # If that fails too, use default
    [ -z "$FILENAME" ] && FILENAME="display.png"
  fi

  # Make sure it ends with .png for eips
  case "$FILENAME" in
    *.png) : ;;
    *) FILENAME="${FILENAME}.png" ;;
  esac

  eips_debug "Parsed URL: $IMAGE_URL"
  eips_debug "Parsed File: $FILENAME"
  eips_debug "Refresh: ${REFRESH_RATE}s"

  # 4) Download the image via the proxy endpoint using POST with full JSON
  IMAGE_PATH="$TMP_DIR/$FILENAME"
  rm -f "$IMAGE_PATH"
  eips_debug "Downloading image..."

  # Download the image directly from IMAGE_URL
  curl -s -o "$IMAGE_PATH" \
    -A "$USER_AGENT" \
    "$IMAGE_URL"

  # Check download success
  if [ ! -s "$IMAGE_PATH" ]; then
    eips_debug "Error: Download failed!"
    eips_debug "Retry in 60s..."
    sleep 60
    continue
  fi

  eips_debug "Image downloaded OK."
  eips_debug "Clearing screen to show image..."

  # 5) Display the downloaded image
  # Always clear screen before showing the image
  eips -c
  sleep 1
  eips -g "$IMAGE_PATH" -x "$DISPLAY_X" -y "$DISPLAY_Y"

  # 6) Print full URL & filename below the displayed image only if debug mode is on
  if [ "$DEBUG_MODE" = true ]; then
    eips 0 18 "URL: $IMAGE_URL"
    eips 0 19 "File: $IMAGE_PATH"
  fi

  # Optional: show how long we will sleep (only in debug mode)
  eips_debug "Sleeping for $REFRESH_RATE seconds..."
  
  # disable wireless if necessary
  if [ 1 -eq $DISABLE_WIFI ]; then
    eips_debug "Disabling WiFi"
    lipc-set-prop com.lab126.cmd wirelessEnable 0
    #lipc-set-prop com.lab126.wifid enable 0
  fi
  
  # take a bit of time before going to sleep, so this process can be aborted
  sleep 10

  echo 0 > /sys/class/rtc/rtc1/wakealarm
  echo "+180" > /sys/class/rtc/rtc1/wakealarm
  echo "mem" > /sys/power/state
done
