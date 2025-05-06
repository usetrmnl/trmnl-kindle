#!/bin/sh
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
API_KEY="INSERT_DEVICE_API_KEY"
BASE_URL="https://trmnl.app"
BATTERY_VOLTAGE="100.00"
RSSI="0"
USER_AGENT="trmnl-display/0.1.1"
DEBUG_MODE=false  # Set to true to enable debug messages, false to disable

# Temporary folder to hold downloaded files
TMP_DIR="/tmp/trmnl-kindle"
mkdir -p "$TMP_DIR"

# Coordinates for displaying the PNG in *pixels*
DISPLAY_X=75
DISPLAY_Y=25

# Size of the PNG in *pixels*
PNG_WIDTH=1400
PNG_HEIGHT=840

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
    DEBUG_Y=$((DEBUG_Y+1))
  fi
}

# Function: json
# Description: Extracts the value of a specified field from a JSON string using sed.
# Parameters:
#   $1: The JSON string (must be a valid JSON string).
#   $2: The name of the field to extract.
# Returns:
#   The value of the specified field from the JSON string.
#   If the field is not found or the JSON is invalid, it prints an error message to stderr and returns an empty string.
#
# Limitations:
#   -  Uses sed, which is not a full JSON parser.  It works for simple key-value string extraction.
#   -  Assumes string field value is a string enclosed in double quotes.
#   -  Will not handle nested JSON structures or arrays reliably.
#   -  Does not handle escaped quotes or other complex JSON string content robustly.
#   -  Relies on pattern matching, which can be fragile with complex or unpredictable JSON.
json() {
  local json_string="$1"
  local field_name="$2"

  if [ -z "$json_string" ] || [ -z "$field_name" ]; then
    echo "Error: json function requires both a JSON string and a field name." >&2
    return 1
  fi

  local extracted_value
  extracted_value=$(echo "$json_string" | sed -n "s/.*\"$field_name\": *\"\\([^\"]*\\)\".*/\\1/p")

  if [ -z "$extracted_value" ]; then
    extracted_value=$(echo "$json_string" | sed -n "s/.*\"$field_name\": *\\([0-9]*\\).*/\\1/p")
    if [ -z "$extracted_value" ]; then
      echo "Error: Field '$field_name' not found in JSON string." >&2
      return 1
    fi
  else
    # Unescape common JSON escape sequences.  This is still basic.
    local unescaped_value
    unescaped_value=$(echo "$extracted_value" \
      | sed 's/\\\\/\\/g;
             s/\\\"/\"/g;
             s/\\\//\//g;
             s/\\u0026/\&/g;
             s/\\u0022/\"/g;'
    )
    extracted_value="$unescaped_value"
  fi
  echo "$extracted_value"
  return 0
}


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
  eips_debug "Fetching JSON..."

  # 2) Fetch JSON metadata
  RESPONSE="$(
    curl -s \
      -H "access-token: $API_KEY" \
      -H "battery-voltage: $BATTERY_VOLTAGE" \
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

  # 3) Parse JSON (using the json function)
  IMAGE_URL=$(json "$RESPONSE" "image_url")
  if [ -z "$IMAGE_URL" ]; then
    eips_debug "Error: Failed to extract image_url from JSON."
    eips_debug "Retry in 60s..."
    sleep 60
    continue
  fi
  eips_debug "ORIGINAL_URL: ${IMAGE_URL}"

  REFRESH_RATE=$(json "$RESPONSE" "refresh_rate")
  if [ -z "$REFRESH_RATE" ]; then
    REFRESH_RATE="60"
  fi
  eips_debug "Refresh Rate: ${REFRESH_RATE}"

  FILENAME=$(json "$RESPONSE" "filename")
  if [ -z "$FILENAME" ]; then
    FILENAME=$(echo "$IMAGE_URL" | sed -n 's/.*\/\([^?] *\)?.*/\1/p')
    if [ -z "$FILENAME" ]; then
      FILENAME="display.png"
    fi
  fi

  # Make sure it ends with .png for eips
  case "$FILENAME" in
    *.png) : ;;
    *) FILENAME="${FILENAME}.png" ;;
  esac

  eips_debug "Parsed URL: $IMAGE_URL"
  eips_debug "Parsed File: $FILENAME"
  eips_debug "Refresh: ${REFRESH_RATE}s"

  # 4) Download the image directly
  IMAGE_PATH="$TMP_DIR/$FILENAME"
  rm -f "$IMAGE_PATH" #remove the file if it exists
  eips_debug "Downloading image..."

  curl -s -o "$IMAGE_PATH" -A "$USER_AGENT" "$IMAGE_URL"

  # Check download success
  if [ ! -s "$IMAGE_PATH" ]; then
    eips_debug "Error: Download failed!"
    eips_debug "Retry in 60s..."
    sleep 60
    continue
  fi

  # Check if the downloaded file is an XML (error check)
  if head -n1 "$IMAGE_PATH" | grep -q '^\s*<?xml'; then
    ERROR_MESSAGE=$(sed -n 's,.*<Message>\(.*\)</Message>.*,\1,p' "$IMAGE_PATH")
    eips_debug "Error page: $ERROR_MESSAGE" >&2
    eips_debug "File: $IMAGE_PATH"
    eips_debug "Exiting in 5s..."
    sleep 5
    exit 1
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
  sleep "$REFRESH_RATE"
done
