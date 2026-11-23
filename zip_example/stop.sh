#!/usr/bin/env sh
pkill -f TRMNL.sh
pkill -f TRMNL_powerd.sh
# powerd mode with the Kindle UI stopped: remove kaf.lua (the UI's stand-in signal) and
# bring the UI back.
if pkill -f kaf.lua; then
  start lab126_gui >/dev/null 2>&1 || initctl start lab126_gui >/dev/null 2>&1
  start framework >/dev/null 2>&1 || /etc/init.d/framework start >/dev/null 2>&1
fi
