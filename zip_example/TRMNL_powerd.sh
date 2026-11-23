#!/bin/sh
# TRMNL client, "powerd mode": opt in with SLEEP_MODE=powerd in TRMNL_config.sh
# (TRMNL.sh hands over to this script).
#
# Why: TRMNL.sh suspends the Kindle itself (echo mem > /sys/power/state). On the Paperwhite 4
# (10th gen, firmware 5.13.x-5.16.x) that left the Wi-Fi daemon hung, or its saved networks
# wiped, after most wakes on battery, so the dashboard stopped refreshing until it was plugged in.
# Here the Kindle's own power manager (powerd) does the suspending: before each suspend we ask
# it for a timed wake (rtcWakeup), and it handles Wi-Fi and the hardware as it normally would.
#
# How: on each timed wake powerd stays in its screensaver state, where the connection manager
# won't bring Wi-Fi up, so we wake it to "active" (Wi-Fi joins in a few seconds), fetch, send it
# back to screensaver and draw the dashboard. The Kindle UI is stopped (STOP_UI=1, the default)
# so nothing repaints the screen between refreshes. kaf.lua stands in for the UI's
# "framework started" signal, without which powerd won't enter screensaver. Pressing the power
# button refreshes immediately.
#
# STOP_UI=0 keeps the Kindle UI running instead: it works without kaf.lua, but the home
# screen flashes up for a few seconds on each refresh and the power button shows the normal UI.
export PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin
cd "$(dirname "$0")" || exit 1
DIR="$(pwd)"
[ -t 1 ] || exec >/dev/null 2>&1
. ./utils.sh

if [ -e apikey.txt ]; then
  API_KEY=$(cat apikey.txt)
fi
BASE_URL="https://trmnl.app"
RSSI="0"
USER_AGENT="trmnl-kindle/0.1.1 (powerd mode)"
PNG_WIDTH=$(get_kindle_height)    # same (swapped) order as TRMNL.sh
PNG_HEIGHT=$(get_kindle_width)
MIN_REFRESH_RATE=300
RETRY_SLEEP=300                   # after a failed refresh
STOP_UI=1
[ -e ./TRMNL_config.sh ] && . ./TRMNL_config.sh
WIFI_TEST_ADDRESS=${WIFI_TEST_ADDRESS:-$(echo "$BASE_URL" | cut -d/ -f3 | cut -d: -f1)}
CUR="$DIR/.current.png"           # last good dashboard image, redrawn when needed
LOG_FILE="$DIR/trmnl.log"
WIFID_CONF=/var/local/system/wifid.conf
WIFID_BAK="$DIR/.wifid.conf.bak"
REFRESH=$MIN_REFRESH_RATE
NEXT=0

now() { date +%s; }
tlog() {
  # On-device log (readable over USB) for refreshes that fail while unplugged. Capped at ~200 KB.
  if [ -f "$LOG_FILE" ] && [ "$(wc -c < "$LOG_FILE")" -gt 200000 ]; then
    tail -c 100000 "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"
  fi
  echo "$(date '+%Y-%m-%d %H:%M:%S') [powerd] $*" >> "$LOG_FILE"
}
pstate() { lipc-get-prop com.lab126.powerd state 2>/dev/null; }
state() {
  echo "pd=$(pstate) cm=$(lipc-get-prop com.lab126.wifid cmState 2>/dev/null)" \
       "pc=$(lipc-get-prop com.lab126.wifid profileCount 2>/dev/null) batt=$(get_kindle_battery)%" \
       "usb=$(cat /sys/class/power_supply/*/online 2>/dev/null | tr '\n' ',')"
}
frontlight_off() {
  lipc-set-prop com.lab126.powerd flIntensity 0 >/dev/null 2>&1
  for b in /sys/class/backlight/*/brightness; do [ -e "$b" ] && echo 0 > "$b" 2>/dev/null; done
}
connected() {
  [ "$(lipc-get-prop com.lab126.wifid cmState 2>/dev/null)" = CONNECTED ] &&
    ping -c 1 -W 2 "$WIFI_TEST_ADDRESS" >/dev/null 2>&1
}
wait_connected() {  # $1 = seconds
  w=0
  while [ "$w" -lt "$1" ]; do connected && return 0; sleep 2; w=$((w+2)); done
  return 1
}
# Saved networks live in wifid.conf (encrypted with a per-device key). If wifid ever comes back
# with none, restore our copy of this device's own file.
backup_wifi_profiles() {
  pc="$(lipc-get-prop com.lab126.wifid profileCount 2>/dev/null)"
  [ -n "$pc" ] && [ "$pc" -gt 0 ] 2>/dev/null || return 0
  cmp -s "$WIFID_CONF" "$WIFID_BAK" 2>/dev/null && return 0
  cat "$WIFID_CONF" > "$WIFID_BAK" && tlog "backed up wifid.conf ($pc saved network(s))"
}
restore_wifi_profiles() {
  [ -s "$WIFID_BAK" ] || return 1
  tlog "no saved networks; restoring backup"
  stop wifid >/dev/null 2>&1; cat "$WIFID_BAK" > "$WIFID_CONF"; start wifid >/dev/null 2>&1
  lipc-set-prop com.lab126.cmd wirelessEnable 1
}
draw() {
  [ -s "$CUR" ] || return 0
  eips -f -g "$CUR" >/dev/null 2>&1
}
to_screensaver() {
  # Active -> screensaver, then draw (over the Kindle's screensaver, if the UI is running).
  # (Don't rely on catching goingToScreenSaver: it can fire before we're listening.)
  [ "$(pstate)" = active ] && powerd_test -p >/dev/null 2>&1
  w=0; while [ "$(pstate)" != screenSaver ] && [ "$w" -lt 10 ]; do sleep 1; w=$((w+1)); done
  if [ "$(pstate)" = active ]; then   # ignored (e.g. UI still starting): one retry
    powerd_test -p >/dev/null 2>&1
    w=0; while [ "$(pstate)" != screenSaver ] && [ "$w" -lt 10 ]; do sleep 1; w=$((w+1)); done
  fi
  [ "$STOP_UI" = 1 ] || sleep 3   # with the UI running, let its screensaver paint first
  frontlight_off; draw
}
stop_ui() {
  # Newer firmware runs the UI as upstart jobs and has no init.d framework script.
  /etc/init.d/framework stop >/dev/null 2>&1 || {
    stop framework >/dev/null 2>&1 || initctl stop framework >/dev/null 2>&1
    stop lab126_gui >/dev/null 2>&1
  }
  initctl stop webreader >/dev/null 2>&1
  # powerd won't enter screensaver (power button, powerd_test -p) until the UI says it has
  # started; kaf.lua publishes that signal in its place (as KOReader's no-framework mode does).
  pkill -f "[k]af.lua" 2>/dev/null
  setsid lua "$DIR/kaf.lua" </dev/null >/dev/null 2>&1 &
  sleep 2
}

fetch() {
  [ -n "$MAC_ADDRESS" ] || MAC_ADDRESS=$(get_mac_address)   # empty if Wi-Fi was off at start
  RESPONSE="$(curl -sL -m 60 \
      -H "access-token: $API_KEY" -H "percent-charged: $(get_kindle_battery)" \
      -H "png-width: $PNG_WIDTH" -H "png-height: $PNG_HEIGHT" -H "rssi: $RSSI" \
      -H "ID: $MAC_ADDRESS" -A "$USER_AGENT" "${BASE_URL}/api/display")"
  [ -n "$RESPONSE" ] || { tlog "FAIL: no JSON response"; return 1; }
  IMAGE_URL=$(echo "$RESPONSE" | sed -n 's/.*"image_url":"\([^"]*\)".*/\1/p' | sed 's/\\u0026/\&/g' | tr -d '\\')
  [ -n "$IMAGE_URL" ] || { tlog "FAIL: no image_url: $(echo "$RESPONSE" | cut -c1-120)"; return 1; }
  r=$(echo "$RESPONSE" | sed -n 's/.*"refresh_rate":\([^,}]*\).*/\1/p' | tr -d ' "')
  case "$r" in ''|*[!0-9]*|??????*) r=0 ;; esac
  [ "$r" -lt "$MIN_REFRESH_RATE" ] && r=$MIN_REFRESH_RATE
  REFRESH=$r
  rm -f "$CUR.tmp"
  curl -sL -m 120 -o "$CUR.tmp" -A "$USER_AGENT" "$IMAGE_URL"
  [ -s "$CUR.tmp" ] || { tlog "FAIL: image download: $IMAGE_URL"; return 1; }
  mv "$CUR.tmp" "$CUR"
  tlog "fetched $(basename "$IMAGE_URL"); next refresh in ${REFRESH}s"
}

refresh() {
  tlog "refresh | $(state)"
  frontlight_off
  woke=0
  if ! connected; then
    if [ "$(pstate)" != active ]; then
      lipc-set-prop -i com.lab126.powerd wakeUp 1 >/dev/null 2>&1; woke=1
      frontlight_off
    fi
    lipc-set-prop com.lab126.cmd wirelessEnable 1 >/dev/null 2>&1
    if ! wait_connected 30; then
      # profileCount reads 0 for a moment after a wake, so only trust it after a failed wait.
      [ "$(lipc-get-prop com.lab126.wifid profileCount 2>/dev/null)" = 0 ] && restore_wifi_profiles
      lipc-set-prop com.lab126.cmd ensureConnection wifi >/dev/null 2>&1
      wait_connected 30
    fi
  fi
  if connected && fetch; then
    backup_wifi_profiles
  else
    tlog "refresh failed | $(state)"
    REFRESH=$RETRY_SLEEP
    [ -s "$CUR" ] || cp "$DIR/wifi-error.png" "$CUR"
  fi
  NEXT=$(( $(now) + REFRESH ))
  frontlight_off
  if [ "$STOP_UI" = 1 ]; then
    draw; to_screensaver          # nobody else draws; always hand back to powerd
  elif [ "$woke" = 1 ] && [ "$(pstate)" = active ]; then
    to_screensaver
  elif [ "$(pstate)" = screenSaver ]; then
    draw
  fi
  # With the UI running and someone using the Kindle, leave the screen alone; the
  # dashboard is drawn when it next goes to screensaver.
}

if [ "$STOP_UI" = 1 ] && ! command -v lua >/dev/null 2>&1; then
  tlog "no lua on this firmware (needed for kaf.lua); keeping the Kindle UI running (STOP_UI=0)"
  STOP_UI=0
fi
tlog "=== client start (powerd mode, STOP_UI=$STOP_UI) | $(state)"
lipc-set-prop com.lab126.powerd preventScreenSaver 0 >/dev/null 2>&1
lipc-set-prop com.lab126.cmd wirelessEnable 1 >/dev/null 2>&1
backup_wifi_profiles
if [ "$STOP_UI" = 1 ]; then
  # Unlike TRMNL.sh, don't set the powersave CPU governor: it's suspected in PW4 slowdowns on
  # battery (lipc calls taking minutes), and powerd suspends the CPU between refreshes anyway.
  frontlight_off; stop_ui; frontlight_off
fi
refresh
# Started from KUAL, so the Kindle is active: hand over to the screensaver now.
[ "$(pstate)" = active ] && to_screensaver

while true; do
  t=$(( NEXT - $(now) )); [ "$t" -lt 5 ] && t=5
  ev=$(lipc-wait-event -s "$t" com.lab126.powerd readyToSuspend,goingToScreenSaver,wakeupFromSuspend,outOfScreenSaver 2>/dev/null)
  case "$ev" in
    readyToSuspend*)
      # powerd is about to suspend: ask it to wake us for the next refresh.
      w=$(( NEXT - $(now) )); [ "$w" -lt 30 ] && w=30
      lipc-set-prop -i com.lab126.powerd rtcWakeup "$w" >/dev/null 2>&1 ;;
    goingToScreenSaver*)
      sleep 3; frontlight_off; draw ;;
    wakeupFromSuspend*)
      tlog "woke | $(state)" ;;
    outOfScreenSaver*)
      # Our own wakeUp happens inside refresh(), when we aren't listening, so this is the
      # power button. With the UI stopped, treat it as "refresh now".
      if [ "$STOP_UI" = 1 ]; then tlog "power button: refreshing"; NEXT=0; fi ;;
  esac
  [ "$(now)" -ge $(( NEXT - 15 )) ] && refresh
done
