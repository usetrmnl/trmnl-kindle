# ----------------------------- CONSTANTS ---------------------------------------- #

# Constants for configuring the wifi management
readonly WIFI_AUTO=0
readonly WIFI_ALWAYS_ON=1
readonly WIFI_DISABLED_DURING_SLEEP=2

# ----------------------------- UTILITY FUNCTIONS -------------------------------- #
get_kindle_battery() {
  # Run the command and capture its output
  local result=$(lipc-get-prop com.lab126.powerd status)

  # Extract the battery level using grep and cut
  # Find the line with "Battery Level", extract just the percentage number
  local battery_level=$(echo "$result" | grep "Battery Level:" | cut -d ":" -f2 | tr -d '% ')

  # Return just the number
  echo "$battery_level"
}

get_kindle_width() {
  # Run the command and capture its output
  local result=$(eips -i)

  # Extract xres using grep and awk
  local xres=$(echo "$result" | grep "xres:" | head -1 | awk '{print $2}')

  # Return just the width value
  echo "$xres"
}

get_kindle_height() {
  # Run the command and capture its output
  local result=$(eips -i)

  # Extract yres using grep and awk
  local yres=$(echo "$result" | grep "yres:" | head -1 | awk '{print $4}')

  # Return just the height value
  echo "$yres"
}

get_mac_address() {
  local address=$(cat /sys/class/net/wlan0/address | tr a-z A-Z)

  echo "$address"
}

# Keep a small log across runs; USB mode may make user storage unavailable.
exit_status() {
  (
    log="$DIR/exit-status.log"
    if [ -f "$log" ]; then
      size=$(wc -c <"$log") || exit 1
      [ "$size" -lt 16384 ] || mv -f "$log" "$log.1" || exit 1
    fi
    printf '%s pid=%s %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$$" "$*" >>"$log"
  ) 2>/dev/null || { echo 'TRMNL: could not write exit-status.log' >&2; return 1; }
}

select_exit_input() {
  local selected fsr prev next
  EXIT_DEVICE= EXIT_KEY= EXIT_LABEL= EXIT_PROMPT=
  EXIT_UNAVAILABLE_REASON=unsupported-abi
  # Support these ARM input layouts only; add others after checking their event format.
  case "$(uname -m)" in armv6l|armv7l) ;; *) return 1 ;; esac
  EXIT_UNAVAILABLE_REASON=missing-reader-tools
  command -v awk >/dev/null || return 1
  EXIT_UNAVAILABLE_REASON=no-unambiguous-enabled-control
  fsr=$(lipc-get-prop com.lab126.deviced fsrkeypadEnable 2>/dev/null) || fsr=
  prev=$(lipc-get-prop com.lab126.deviced fsrkeypadPrevEnable 2>/dev/null) || prev=
  next=$(lipc-get-prop com.lab126.deviced fsrkeypadNextEnable 2>/dev/null) || next=
  selected=$(awk -v fsr="$fsr" -v prev="$prev" -v forward="$next" '
    # Kernel ARM32 bitmaps print 32-bit words, highest first.
    function bit(map, n, words, count, word, value, i) {
      count=split(map, words, " "); word=words[count-int(n/32)]
      value=0
      for (i=1; i<=length(word); i++)
        value=value*16+index("0123456789abcdef", substr(word,i,1))-1
      return int(value / (2^(n%32))) % 2
    }
    function candidate(priority, key, label) {
      if (power_node) return
      counts[priority]++; devices[priority]=dev; keys[priority]=key; labels[priority]=label
    }
    BEGIN { RS=""; FS="\n" }
    {
      dev=name=ev=key=abs=""
      for (i=1; i<=NF; i++) {
        if ($i ~ /^N: /) name=$i
        if ($i ~ /^H: / && match($i, /event[0-9]+/)) dev=substr($i,RSTART,RLENGTH)
        if ($i ~ /^B: EV=/) ev=substr($i,7)
        if ($i ~ /^B: KEY=/) key=substr($i,8)
        if ($i ~ /^B: ABS=/) abs=substr($i,8)
      }
      if (dev == "") next
      power_node=(bit(key,116) || bit(key,142) || bit(key,143) || bit(key,205))
      if (bit(ev,3) && !bit(key,320) && !bit(key,331) && !bit(key,332) &&
          ((bit(abs,0) && bit(abs,1)) || (bit(abs,53) && bit(abs,54)))) {
        touch_count++
        if (bit(ev,1) && bit(key,330)) candidate(0,330,"touch")
      }
      if (!bit(ev,1) || bit(ev,3)) next
      enabled=(name !~ /fsr_keypad/ || (fsr == "1" && prev == "1" && forward == "1"))
      if (enabled) for (k=1; k<256; k++) if (bit(key,k)) {
        candidate(1,0,"button"); break
      }
    }
    END {
      # An unsupported/ambiguous touchscreen must not select pressure keys.
      if (touch_count) {
        if (touch_count == 1 && counts[0] == 1)
          print "/dev/input/" devices[0], keys[0], labels[0]
        exit
      }
      if (counts[1] == 1) print "/dev/input/" devices[1], keys[1], labels[1]
    }' /proc/bus/input/devices) || return 1
  [ -n "$selected" ] || return 1
  read -r EXIT_DEVICE EXIT_KEY EXIT_LABEL <<EOF
$selected
EOF
  EXIT_PROMPT="$DIR/exit-$EXIT_LABEL.png"
  exit_resources_ready
}

exit_resources_ready() {
  EXIT_UNAVAILABLE_REASON=missing-exit-helper
  [ -x "$DIR/exit-input" ] || return 1
  EXIT_UNAVAILABLE_REASON=incompatible-exit-helper
  "$DIR/exit-input" --check >/dev/null 2>&1 || return 1
  EXIT_UNAVAILABLE_REASON=unreadable-input
  [ -r "$EXIT_DEVICE" ] || return 1
  EXIT_UNAVAILABLE_REASON=missing-prompt-image
  [ -r "$EXIT_PROMPT" ] && [ -s "$EXIT_PROMPT" ]
}

stop_exit_reader() {
  if [ -n "$EXIT_READER_PID" ]; then
    # After cancellation, let the helper finish waiting for release despite more signals.
    trap '' TERM INT HUP
    kill "$EXIT_READER_PID" 2>/dev/null
    wait "$EXIT_READER_PID" 2>/dev/null
    EXIT_READER_PID=
  fi
}

read_exit_input() {
  local status
  EXIT_CANCELLED=0 EXIT_READER_PID=
  # A signal before $! is assigned is remembered; afterward it also cancels
  # the helper, which handles the timeout and waits for release.
  trap 'EXIT_CANCELLED=1; [ -z "$EXIT_READER_PID" ] || kill "$EXIT_READER_PID" 2>/dev/null' TERM INT HUP
  "$DIR/exit-input" "$EXIT_DEVICE" "$EXIT_KEY" "$EXIT_PROMPT" &
  EXIT_READER_PID=$!
  [ "$EXIT_CANCELLED" = 0 ] || kill "$EXIT_READER_PID" 2>/dev/null
  wait "$EXIT_READER_PID"
  status=$?
  if [ "$EXIT_CANCELLED" != 0 ]; then
    trap '' TERM INT HUP
    # A signal can interrupt wait before the helper exits. Wait again before restoring the UI.
    wait "$EXIT_READER_PID" 2>/dev/null
    EXIT_READER_PID=
    exit_status 'window cancelled signal'
    exit 0
  fi
  EXIT_READER_PID=
  trap 'exit 0' TERM INT HUP
  case "$status" in
    0) EXIT_REASON=confirmed; return 0 ;;
    1) EXIT_REASON=timeout ;;
    2) EXIT_REASON=grab-failed ;;
    3) EXIT_REASON=state-error ;;
    4) EXIT_REASON=dropped-input ;;
    5) EXIT_REASON=reader-error ;;
    6) EXIT_REASON=prompt-error ;;
    7) EXIT_REASON=signal ;;
    8) EXIT_REASON=held-at-cutoff ;;
    9) EXIT_REASON=unsupported-input; CAN_EXIT=0 ;;
    10) EXIT_REASON=existing-input ;;
    126|127) EXIT_REASON=missing-exit-helper; CAN_EXIT=0 ;;
    *) EXIT_REASON=reader-error ;;
  esac
  return 1
}

is_early_wake() {
  local value
  for value in "$1" "$2"; do
    case "$value" in ''|*[!0-9]*|0*|???????????*) return 1 ;; esac
  done
  [ "$1" -gt "$(($2 + 5))" ]
}

cache_displayed_image() {
  LAST_IMAGE_VALID=0
  if cp "$1" "$DASHBOARD_CACHE.new" 2>/dev/null && mv "$DASHBOARD_CACHE.new" "$DASHBOARD_CACHE"; then
    LAST_IMAGE_VALID=1
  else
    rm -f "$DASHBOARD_CACHE.new"
  fi
}

display_image() {
  # Older eips lacks image coordinates; retain the existing compatibility path.
  if eips | grep -q -v '\-y'; then
    eips -g "$1"
  else
    eips -g "$1" -x "$DISPLAY_X" -y "$DISPLAY_Y"
  fi
}

offer_early_exit() {
  [ "$CAN_EXIT" = 1 ] && [ "$LAST_IMAGE_VALID" = 1 ] &&
    [ -s "$DASHBOARD_CACHE" ] || return 0
  is_early_wake "$1" "$2" || return 0
  if ! exit_resources_ready; then
    CAN_EXIT=0
    exit_status "ineligible $EXIT_UNAVAILABLE_REASON"
    return 0
  fi
  exit_status 'window requested'
  if read_exit_input; then
    exit_status 'window confirmed'
    exit 0
  fi
  if [ "$EXIT_REASON" = timeout ]; then
    exit_status 'window timeout'
  else
    exit_status "window cancelled $EXIT_REASON"
  fi
  display_image "$DASHBOARD_CACHE" || echo 'TRMNL: dashboard redraw failed' >&2
}

# Keep the saved screen on the Kindle and check its layout before restoring it.
stock_screen_geometry() {
  eips -i 2>/dev/null | awk '
    /smem_len:/ {s=$2} /xres:/ {x=$2; y=$4}
    /bits_per_pixel:/ {b=$2; g=$4} /rotate:/ {r=$2}
    /line_length:/ {l=$4} /xres_virtual:/ {vx=$2; vy=$4}
    /xoffset:/ {ox=$2; oy=$4}
    END {
      v=s " " x " " y " " b " " r " " l " " vx " " vy " " ox " " oy " " g
      if (split(v,a," ") != 11) exit 1
      for (i=1;i<=11;i++) if (a[i] !~ /^[0-9]+$/) exit 1
      if (s>0 && x>0 && y>0 && b>0 && l>0) print v; else exit 1
    }'
}

capture_stock_screen() {
  local geometry
  STOCK_SCREEN= STOCK_GEOMETRY=
  [ ! -x /etc/init.d/framework ] && [ "$FRAMEWORK_STATE" = running ] || return 0
  STOCK_SCREEN="$TMP_DIR/.stock-$$.fb"
  if geometry=$(stock_screen_geometry) && set -- $geometry &&
      rm -f "$STOCK_SCREEN" &&
      (umask 077; cat /dev/fb0 >"$STOCK_SCREEN") 2>/dev/null &&
      [ "$(wc -c <"$STOCK_SCREEN")" = "$1" ] &&
      [ "$(stock_screen_geometry)" = "$geometry" ]; then
    STOCK_GEOMETRY=$geometry
    exit_status 'screen saved'
  else
    rm -f "$STOCK_SCREEN"
    exit_status 'screen snapshot-unavailable'
  fi
  return 0
}

restore_stock_screen() {
  local outcome=restore-skipped
  set -- $STOCK_GEOMETRY
  if [ -n "$STOCK_GEOMETRY" ] && [ -r "$STOCK_SCREEN" ] &&
      [ "$(wc -c <"$STOCK_SCREEN")" = "$1" ] && [ -w /dev/fb0 ] &&
      [ "$(stock_screen_geometry)" = "$STOCK_GEOMETRY" ]; then
    if cat "$STOCK_SCREEN" >/dev/fb0 2>/dev/null &&
        eips -s "w=$2,h=$3" -f >/dev/null 2>&1; then
      outcome=restored
    else
      outcome=restore-failed
    fi
  fi
  # Log screen restoration separately from settings and services.
  exit_status "screen $outcome"
}

service_state() {
  local status
  command -v initctl >/dev/null || { echo absent; return; }
  status=$(initctl status "$1" 2>&1) || status="error $status"
  case "$status" in
    *'Unknown job'*) echo absent ;;
    error*) echo unknown ;;
    *start/running*) echo running ;;
    *stop/waiting*) echo stopped ;;
    *) echo unknown ;;
  esac
}

capture_trmnl_state() {
  local missing=
  CAN_EXIT=1 RESTORE_INCOMPLETE=0 RESTORED=0
  FRAMEWORK_STOPPED=0 WEBREADER_STOPPED=0
  ORIGINAL_GOVERNOR=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null) || ORIGINAL_GOVERNOR=
  ORIGINAL_WIFI=$(lipc-get-prop com.lab126.cmd wirelessEnable 2>/dev/null) || ORIGINAL_WIFI=
  ORIGINAL_SCREENSAVER=$(lipc-get-prop com.lab126.powerd preventScreenSaver 2>/dev/null) || ORIGINAL_SCREENSAVER=
  case "$ORIGINAL_GOVERNOR" in ''|*[!a-zA-Z0-9_-]*) ORIGINAL_GOVERNOR=; missing="$missing governor" ;; esac
  case "$ORIGINAL_WIFI" in 0|1) ;; *) ORIGINAL_WIFI=; missing="$missing wireless" ;; esac
  case "$ORIGINAL_SCREENSAVER" in ''|*[!0-9]*) ORIGINAL_SCREENSAVER=; missing="$missing screensaver" ;; esac
  FRAMEWORK_STATE=unknown
  if [ -x /etc/init.d/framework ]; then
    if command -v pidof >/dev/null; then
      FRAMEWORK_STATE=stopped
      pidof cvm >/dev/null && FRAMEWORK_STATE=running
    fi
  else
    FRAMEWORK_STATE=$(service_state framework)
  fi
  WEBREADER_STATE=$(service_state webreader)
  [ "$FRAMEWORK_STATE" != unknown ] || missing="$missing framework"
  [ "$WEBREADER_STATE" != unknown ] || missing="$missing webreader"
  if [ -n "$missing" ]; then
    CAN_EXIT=0 RESTORE_INCOMPLETE=1
    exit_status "ineligible capture-failed$missing"
    echo 'TRMNL: exit confirmation unavailable (original state unavailable)' >&2
  fi
}

restore_trmnl() {
  [ "$RESTORED" = 1 ] && return
  RESTORED=1
  stop_exit_reader
  [ -z "$DASHBOARD_CACHE" ] || rm -f "$DASHBOARD_CACHE" "$DASHBOARD_CACHE.new"
  if [ -n "$OWNED_ALARM" ] &&
      [ "$(cat /sys/class/rtc/rtc1/wakealarm 2>/dev/null)" = "$OWNED_ALARM" ]; then
    echo 0 >/sys/class/rtc/rtc1/wakealarm || { RESTORE_INCOMPLETE=1; exit_status 'cleanup failed alarm'; }
  fi
  if [ -n "$ORIGINAL_GOVERNOR" ]; then
    echo "$ORIGINAL_GOVERNOR" >/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor || { RESTORE_INCOMPLETE=1; exit_status 'cleanup failed governor'; }
  fi
  if [ -n "$ORIGINAL_WIFI" ]; then
    lipc-set-prop com.lab126.cmd wirelessEnable "$ORIGINAL_WIFI" || { RESTORE_INCOMPLETE=1; exit_status 'cleanup failed wireless'; }
  fi
  if [ -n "$ORIGINAL_SCREENSAVER" ]; then
    lipc-set-prop com.lab126.powerd preventScreenSaver "$ORIGINAL_SCREENSAVER" || { RESTORE_INCOMPLETE=1; exit_status 'cleanup failed screensaver'; }
  fi
  if [ "$FRAMEWORK_STOPPED" = 1 ]; then
    /etc/init.d/framework start || { RESTORE_INCOMPLETE=1; exit_status 'cleanup failed framework'; }
  fi
  if [ "$WEBREADER_STOPPED" = 1 ]; then
    initctl start webreader >/dev/null 2>&1 || { RESTORE_INCOMPLETE=1; exit_status 'cleanup failed webreader'; }
  fi
  if [ ! -x /etc/init.d/framework ] && [ "$FRAMEWORK_STATE" = running ]; then
    restore_stock_screen
    lipc-set-prop com.lab126.appmgrd start app://com.lab126.booklet.home || { RESTORE_INCOMPLETE=1; exit_status 'cleanup failed home'; }
  fi
  [ -z "$STOCK_SCREEN" ] || rm -f "$STOCK_SCREEN"
  if [ "$RESTORE_INCOMPLETE" = 0 ]; then
    exit_status 'cleanup restored'
  else
    exit_status 'cleanup partial'
    echo 'TRMNL: restoration incomplete (original state unavailable or restore failed)' >&2
  fi
  sync || echo 'TRMNL: sync failed' >&2
  return 0
}
