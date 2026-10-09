#!/usr/bin/env python3
"""Run with python3 tests/early-wake-exit.py; uses existing busybox:1.36.1, never pulls."""
import os
from pathlib import Path
import re
import struct
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
import zlib

ROOT = Path(__file__).resolve().parents[1]
IMAGE = 'busybox:1.36.1'


def shell(script, files=None, timeout=18, stderr=''):
    with tempfile.TemporaryDirectory() as directory:
        p = Path(directory)
        (p/'utils.sh').write_text((ROOT/'zip_example/utils.sh').read_text().replace(
            '/proc/bus/input/devices', '/work/devices').replace('/sys/', '/work/sys/').replace(
            '/etc/init.d/framework', '/work/framework').replace('/dev/input/', '/work/nodes/').replace('/dev/fb0', '/work/fb'))
        for action in ('touch', 'button'):
            (p/f'exit-{action}.png').write_bytes(b'image-fixture')
        (p/'nodes').mkdir()
        for number in re.findall(rb'Handlers=event(\d+)', (files or {}).get('devices', b'')):
            (p/'nodes'/f'event{number.decode()}').touch()
        source = (ROOT/'zip_example/TRMNL.sh').read_text()
        functions = 'init() {' + source.split('init() {', 1)[1].split('\ninit\n', 1)[0]
        functions = functions.replace('echo "mem" > /sys/power/state', 'suspend_write')
        functions = functions.replace('echo "+${REFRESH_RATE}" > /sys/class/rtc/rtc1/wakealarm',
                                      'alarm_write')
        (p/'functions.sh').write_text(functions.replace('/sys/', '/work/sys/').replace(
            '/etc/init.d/framework', '/work/framework'))
        (p/'bin').mkdir()
        # Shell integration uses a status stub; actual native behavior is tested
        # by tests/native-reader.py against the production C implementation.
        helper = p/'exit-input'
        helper.write_text('#!/bin/sh\n[ "$1" = --check ] && exit 0\nexit 1\n')
        helper.chmod(0o755)
        for name, data in (files or {}).items():
            (p/name).parent.mkdir(parents=True, exist_ok=True)
            (p/name).write_bytes(data)
            if name.startswith('bin/') or name in ('framework', 'exit-input'):
                (p/name).chmod(0o755)
        (p/'run.sh').write_text('''#!/bin/sh
PATH=/work/bin:$PATH
cd /work
. ./utils.sh
TMP_DIR=/work
DIR=/work
EXIT_DEVICE=/work/input
EXIT_KEY=330
EXIT_PROMPT=/work/exit-touch.png
''' + script)
        start = time.monotonic()
        result = subprocess.run(
            ['docker', 'run', '--rm', '--pull=never', '--network=none',
             '--init', '-v', f'{p}:/work', IMAGE, 'sh', '/work/run.sh'],
            capture_output=True, text=True, timeout=timeout)
        assert result.returncode == 0 and result.stderr == stderr, (result.stdout, result.stderr)
        return result.stdout, time.monotonic()-start


def reader_checks():
    for code, expected in [(0, 'confirmed'), (1, 'timeout'), (2, 'grab-failed'),
                           (3, 'state-error'), (4, 'dropped-input'), (5, 'reader-error'),
                           (6, 'prompt-error'), (8, 'held-at-cutoff'),
                           (9, 'unsupported-input'), (10, 'existing-input')]:
        out, _ = shell('''read_exit_input
echo "result=$? reason=$EXIT_REASON"
[ -z "$EXIT_READER_PID" ] || exit 20
''', {'exit-input': f'#!/bin/sh\n[ "$1" = --check ] && exit 0\nexit {code}\n'.encode()})
        assert f'result={0 if code == 0 else 1} reason={expected}' in out, out
        print('PASS native reader status', expected)
    for delay in ('.001', '.1'):
        out, _ = shell(f'''trap 'echo cleanup' EXIT
(sleep {delay}; kill -TERM $$) &
read_exit_input
echo unexpected-return
''', {'exit-input': b'''#!/bin/sh
trap 'echo helper-closed; exit 7' TERM INT HUP
while :; do sleep 1; done
'''})
        assert 'cleanup' in out and 'unexpected-return' not in out, out
        print('PASS native helper signal/launch cancellation', delay)



def top_level_signal_checks():
    source = (ROOT/'zip_example/TRMNL.sh').read_text()
    traps = source.split('\ninit\n', 1)[1].split('if [ "$CAN_EXIT"', 1)[0]
    for sig in ('TERM', 'INT', 'HUP'):
        out, _ = shell('restore_trmnl() { echo cleanup; }\n' + traps +
                       f'kill -{sig} $$\necho unexpected-return\n')
        assert out.strip() == 'cleanup', (sig, out)
        print('PASS top-level cleanup signal', sig)


def bitmap(bits):
    value = sum(1 << bit for bit in bits)
    words = []
    while value:
        words.append(f'{value & 0xffffffff:x}')
        value >>= 32
    return ' '.join(reversed(words or ['0']))


def device(name, number, keys, axes=()):
    return (f'N: Name="{name}"\nH: Handlers=event{number}\n'
            f'B: EV={bitmap([0, 1, 3] if axes else [0, 1])}\n'
            f'B: KEY={bitmap(keys)}\nB: ABS={bitmap(axes)}\n\n')


def selection_checks():
    touch = device('cyttsp4_mt', 7, [330], [47, 53, 54, 57])
    page = device('fsr_keypad', 9, [104, 109])
    for name, devices, fsr, arch, expected in [
        ('touch', touch, 0, 'armv7l', 'event7 330'),
        ('disabled FSR', page+touch, 0, 'armv7l', 'event7 330'),
        ('touch before enabled FSR', page+touch, 1, 'armv7l', 'event7 330'),
        ('enabled FSR non-touch', page, 1, 'armv7l', 'event9 0'),
        ('disabled FSR non-touch', page, 0, 'armv7l', 'unavailable'),
        ('previous non-touch', device('keypad', 2, [104, 109]), 0, 'armv7l', 'event2 0'),
        ('next non-touch', device('keypad', 2, [109]), 0, 'armv7l', 'event2 0'),
        ('Home non-touch', device('keypad', 2, [102]), 0, 'armv6l', 'event2 0'),
        ('page alias', device('keypad', 4, [193]), 0, 'armv7l', 'event4 0'),
        ('next alias', device('keypad', 4, [124]), 0, 'armv7l', 'event4 0'),
        ('ordinary key', device('keypad', 4, [98]), 0, 'armv7l', 'event4 0'),
        ('ambiguous button devices', device('one', 2, [104])+device('two', 3, [109]),
         0, 'armv7l', 'unavailable'),
        ('button with sleep', device('mixed', 7, [104, 142]), 0, 'armv7l', 'unavailable'),
        ('button with wake-up', device('mixed', 7, [104, 143]), 0, 'armv7l', 'unavailable'),
        ('button with suspend', device('mixed', 7, [104, 205]), 0, 'armv7l', 'unavailable'),
        ('button with axes', device('pen', 3, [98], [0, 1]), 0, 'armv7l', 'unavailable'),
        ('touch with power', device('mixed', 7, [116, 330], [0, 1]), 0, 'armv7l', 'unavailable'),
        ('page with power', device('mixed', 7, [104, 116]), 0, 'armv7l', 'unavailable'),
        ('power only', device('onkey', 0, [116]), 0, 'armv7l', 'unavailable'),
        ('ambiguous touch', touch+device('other', 6, [330], [0, 1]), 0, 'armv7l', 'unavailable'),
        ('pen', device('pen', 3, [320, 330], [0, 1]), 0, 'armv7l', 'unavailable'),
        ('MT only', device('mt', 3, [], [47, 53, 54, 57]), 0, 'armv7l', 'unavailable'),
        ('MT plus keys', device('mt', 3, [], [53, 54])+page, 1, 'armv7l', 'unavailable'),
        ('MT without EV_KEY plus keys', device('mt', 3, [], [53, 54]).replace('EV=b', 'EV=9')+page,
         1, 'armv7l', 'unavailable'),
        ('ambiguous touch plus keys', touch+device('other', 6, [330], [0, 1])+page,
         1, 'armv7l', 'unavailable'),
        ('unknown ABI', touch, 0, 'aarch64', 'unavailable'),
    ]:
        out, _ = shell(f'''
uname() {{ echo {arch}; }}
if select_exit_input; then echo "$EXIT_DEVICE $EXIT_KEY"; else echo unavailable; fi
''', {'devices': devices.encode(), 'bin/lipc-get-prop': f'#!/bin/sh\necho {fsr}\n'.encode()})
        assert expected in out, (name, out)
        print('PASS capability', name)

    for code, label in [(330, 'touch'), (98, 'button')]:
        controls = touch if code == 330 else device('keypad', 7, [code])
        out, _ = shell('''
uname() { echo armv7l; }
select_exit_input || exit 50
echo "$EXIT_PROMPT"
''', {'devices': controls.encode(), 'bin/lipc-get-prop': b'#!/bin/sh\necho 0\n'})
        assert f'/work/exit-{label}.png' in out, (code, out)
    print('PASS every retained action maps to its prompt asset')

    for remove, reason in [('nodes/event7', 'unreadable-input'),
                            ('exit-touch.png', 'missing-prompt-image')]:
        out, _ = shell(f'''
uname() {{ echo armv7l; }}
rm {remove}
if select_exit_input; then exit 51; fi
echo "$EXIT_UNAVAILABLE_REASON"
''', {'devices': touch.encode(), 'bin/lipc-get-prop': b'#!/bin/sh\necho 0\n'})
        assert reason in out, out
        print('PASS selection fails closed', reason)

    for mode in ('missing', 'incompatible'):
        out, _ = shell(f'''
uname() {{ echo armv7l; }}
if [ '{mode}' = missing ]; then rm exit-input; else echo 'exit 9' >>exit-input; fi
if select_exit_input; then echo eligible; else echo "$EXIT_UNAVAILABLE_REASON"; fi
''', {'devices': touch.encode(), 'bin/lipc-get-prop': b'#!/bin/sh\necho 0\n',
       'exit-input': b'#!/bin/sh\n'})
        assert 'missing-exit-helper' in out or 'incompatible-exit-helper' in out, out
        print('PASS helper availability', mode)


def lifecycle_checks():
    for deadline, now, expected in [('1300', '1294', 0), ('1300', '1295', 1),
                                    ('1300', '1300', 1), ('1300', '1301', 1),
                                    ('', '1000', 1), ('+300', '1000', 1),
                                    ('1300', '', 1), ('0', '0', 1)]:
        out, _ = shell(f'is_early_wake "{deadline}" "{now}"; echo result=$?\n')
        assert f'result={expected}' in out, (deadline, now, out)
    print('PASS RTC gate and exact margin')

    out, _ = shell('''
DASHBOARD_CACHE=/work/dashboard
cache_displayed_image /work/first
cache_displayed_image /work/missing
[ "$LAST_IMAGE_VALID" = 0 ] || exit 23
cache_displayed_image /work/first
[ "$(cat "$DASHBOARD_CACHE")" = good ] || exit 24
echo cache-ok
''', {'first': b'good'})
    assert 'cache-ok' in out
    print('PASS cache failure disables stale-image prompting')

    fixtures = {
        'sys/devices/system/cpu/cpu0/cpufreq/scaling_governor': b'ondemand\n',
        'sys/class/rtc/rtc1/wakealarm': b'1400\n',
        'wifi': b'1\n', 'screensaver': b'0\n', 'webreader': b'start/running',
        'bin/lipc-get-prop': b'''#!/bin/sh
case "$2" in wirelessEnable) cat /work/wifi;; preventScreenSaver) cat /work/screensaver;; esac
''',
        'bin/lipc-set-prop': b'''#!/bin/sh
echo "$*" >>/work/events
case "$2" in
wirelessEnable) [ -z "$3" ] || echo "$3" >/work/wifi;;
preventScreenSaver) echo "$3" >/work/screensaver;;
esac
exit 0
''',
        'bin/initctl': b'''#!/bin/sh
case "$1 $2" in
"status framework") echo "framework start/running";;
"status webreader") cat /work/webreader;;
"stop webreader") echo stop/waiting >/work/webreader; echo stop-webreader >>/work/events;;
"start webreader") echo start/running >/work/webreader; echo start-webreader >>/work/events;;
*) echo unexpected-service-operation >>/work/events; exit 1;;
esac
''',
    }
    for missing in (False, True):
        files = dict(fixtures)
        if missing:
            files['wifi'] = b''
        out, _ = shell('''
. ./functions.sh
eips_debug() { :; }
WIFI_MANAGEMENT=2
init
echo eligible=$CAN_EXIT
[ "$CAN_EXIT" = 1 ] || grep -q 'ineligible capture-failed wireless' exit-status.log || exit 29
# An external owner replaced our alarm: cleanup must leave it alone.
OWNED_ALARM=1300
restore_trmnl
restore_trmnl
[ "$(cat sys/class/rtc/rtc1/wakealarm)" = 1400 ] || exit 30
[ "$(cat sys/devices/system/cpu/cpu0/cpufreq/scaling_governor)" = ondemand ] || exit 31
[ "$(cat screensaver)" = 0 ] || exit 32
[ "$(cat webreader)" = start/running ] || exit 33
[ "$(grep -c start-webreader events)" = 1 ] || exit 34
! grep -q unexpected-service-operation events || exit 35
cat events
''', files, stderr=('TRMNL: exit confirmation unavailable (original state unavailable)\n'
                   'TRMNL: restoration incomplete (original state unavailable or restore failed)\n') if missing else '')
        assert f'eligible={int(not missing)}' in out, out
        assert 'com.lab126.appmgrd start app://com.lab126.booklet.home' in out
        if not missing:
            assert out.count('com.lab126.cmd wirelessEnable 1') == 1, out
        print('PASS exact restore / missing capture', missing)

    for running in (False, True):
        files = dict(fixtures)
        files['bin/pidof'] = f'#!/bin/sh\nexit {0 if running else 1}\n'.encode()
        files['framework'] = b'#!/bin/sh\necho framework-$1 >>/work/events\n'
        files['webreader'] = b'start/running' if running else b'stop/waiting'
        out, _ = shell('''
. ./functions.sh
eips_debug() { :; }
WIFI_MANAGEMENT=2
init
restore_trmnl
restore_trmnl
cat events
''', files)
        assert out.count('framework-start') == int(running), out
        assert out.count('start-webreader') == int(running), out
        assert 'booklet.home' not in out, out
        print('PASS SysV restores only initially running services', running)

    # Exercise the shared production sleep path; only hardware commands are faked.
    for name, remaining, failed, valid, capture, confirm in [
        ('timeout redraw', 300, 0, 1, 1, 1),
        ('confirmation exits', 300, 0, 1, 1, 0),
        ('scheduled wake', 0, 0, 1, 1, 1),
        ('failed suspend', 300, 1, 1, 1, 1),
        ('no dashboard', 300, 0, 0, 1, 1),
        ('capture unavailable', 300, 0, 1, 0, 1),
    ]:
        files = dict(fixtures, dashboard=b'good', input=b'')
        files['sys/class/rtc/rtc1/since_epoch'] = b'1000\n'
        out, _ = shell(f'''
. ./functions.sh
CAN_EXIT={capture} LAST_IMAGE_VALID={valid}
DASHBOARD_CACHE=/work/dashboard INITIAL_WIFI_STATE=1 REFRESH_RATE=300
sleep() {{ :; }}
sync() {{ echo sync; }}
eips_debug() {{ :; }}
eips() {{ [ $# -gt 0 ] && echo "screen:$*" || echo usage; }}
alarm_write() {{ echo {1000+remaining} >sys/class/rtc/rtc1/wakealarm; }}
suspend_write() {{ echo suspend; return {failed}; }}
read_exit_input() {{ echo "screen:-g $EXIT_PROMPT"; echo reader; EXIT_REASON=timeout; return {confirm}; }}
trap 'echo cleanup' EXIT
go_to_sleep
echo network
''', files)
        prompt = capture and valid and not failed and remaining > 5
        assert ('screen:-g /work/exit-touch.png' in out) == bool(prompt), (name, out)
        assert out.index('sync') < out.index('suspend'), out
        if prompt and confirm:
            assert out.index('reader') < out.index('screen:-g /work/dashboard') < out.index('network'), out
        elif prompt:
            assert 'network' not in out and 'cleanup' in out, out
        print('PASS sleep integration', name)

    for failure in ('missing', 'draw-error'):
        out, _ = shell(f'''
CAN_EXIT=1 LAST_IMAGE_VALID=1 DASHBOARD_CACHE=/work/dashboard
eips() {{ echo "screen:$*"; [ "$2" != "$EXIT_PROMPT" ]; }}
read_exit_input() {{ EXIT_REASON=prompt-error; return 1; }}
[ '{failure}' != missing ] || rm "$EXIT_PROMPT"
offer_early_exit 1300 1000
echo network
cat exit-status.log
''', {'dashboard': b'image', 'input': b''})
        assert 'network' in out, out
        if failure == 'missing':
            assert 'ineligible missing-prompt-image' in out and 'screen:' not in out, out
        else:
            assert 'window cancelled prompt-error' in out and 'screen:-g /work/dashboard' in out, out
        print('PASS prompt failure preserves operation', failure)

    out, _ = shell('''
. ./functions.sh
DIR=/proc/trmnl-unwritable
eips_debug() { :; }
sleep() { :; }
sync() { echo sync; }
WIFI_MANAGEMENT=2
init
CAN_EXIT=0
REFRESH_RATE=300
alarm_write() { echo 1300 >sys/class/rtc/rtc1/wakealarm; }
suspend_write() { echo suspend; return 1; }
go_to_sleep
restore_trmnl
echo finished
''', fixtures, stderr='TRMNL: could not write exit-status.log\n'*3)
    assert 'suspend' in out and 'finished' in out and out.count('sync') == 2, out
    print('PASS unwritable durable log does not block suspend or cleanup')



def stock_screen_checks():
    info = b'''Fixed framebuffer info
    smem_len: 16 type: PACKED PIXELS
    ywrapstep: 0 line_length: 4
Variable framebuffer info
    xres: 4 yres: 4
    xres_virtual: 4 yres_virtual: 4
    xoffset: 0 yoffset: 0
    bits_per_pixel: 8 grayscale: 1
    rotate: 0
'''
    files = {'fb': b'0123456789abcdef', 'info': info,
             'bin/lipc-set-prop': b'#!/bin/sh\necho home:$* >>/work/events\n'}
    setup = '''
FRAMEWORK_STATE=running CAN_EXIT=1 RESTORED=0 RESTORE_INCOMPLETE=0
eips() {
  if [ "$1" = -i ]; then cat /work/info; return; fi
  [ "$(cat /work/fb)" = 0123456789abcdef ] || exit 70
  echo "refresh:$*" >>events
  [ ! -e /work/refresh-failed ]
}
sync() { :; }
'''
    for case in ('roundtrip', 'capture-short', 'capture-read-error', 'capture-geometry-change',
                 'capture-info-missing', 'restore-short', 'restore-geometry-change',
                 'restore-write-error', 'refresh-error'):
        fault = {
            'capture-short': 'printf short >fb',
            'capture-read-error': 'cat() { if [ "$1" = /work/fb ]; then printf short; return 1; fi; command cat "$@"; }',
            'capture-geometry-change': 'cat() { command cat "$@"; [ "$1" != /work/fb ] || sed -i "s/rotate: 0/rotate: 1/" info; }',
            'capture-info-missing': 'echo unsupported >info',
        }.get(case, ':')
        after = {
            'restore-short': 'printf short >"$STOCK_SCREEN"',
            'restore-geometry-change': 'sed -i "s/xoffset: 0/xoffset: 1/" info',
            'restore-write-error': 'cat() { [ "$1" != "$STOCK_SCREEN" ] || return 1; command cat "$@"; }',
            'refresh-error': 'touch refresh-failed',
        }.get(case, ':')
        out, _ = shell(setup + fault + '''
capture_stock_screen
[ "$CAN_EXIT" = 1 ] || exit 71
if [ -s "$STOCK_SCREEN" ]; then
  [ "$(stat -c %a "$STOCK_SCREEN")" = 600 ] || exit 72
fi
printf dashboard >fb
''' + after + '''
restore_trmnl
restore_trmnl
[ ! -e "$STOCK_SCREEN" ] || exit 73
cat events
cat exit-status.log
''', files)
        assert out.count('home:') == 1 and 'cleanup restored' in out, (case, out)
        assert 'cleanup partial' not in out and 'ineligible' not in out, (case, out)
        if case == 'roundtrip':
            assert out.index('refresh:-s w=4,h=4 -f') < out.index('home:'), out
            assert 'screen restored' in out, out
        elif case == 'refresh-error':
            assert 'screen restore-failed' in out, out
        else:
            assert 'refresh:' not in out, (case, out)
            assert 'screen restore-skipped' in out or 'screen restore-failed' in out, out
        print('PASS stock screen', case)

    # Actual startup functions + top-level capture/traps: stop during capture
    # must discard the partial file without trying to display it.
    source = (ROOT/'zip_example/TRMNL.sh').read_text()
    startup = source.split('\ninit\n', 1)[1].split('if [ "$CAN_EXIT"', 1)[0]
    startup = startup.replace('trap restore_trmnl EXIT',
        "trap 'restore_trmnl; [ ! -e \"$STOCK_SCREEN\" ] || exit 73; cat events' EXIT")
    out, _ = shell(setup + '''
cat() {
  if [ "$1" = /work/fb ]; then printf short; kill -TERM $$; return 1; fi
  command cat "$@"
}
''' + startup + '\necho unexpected-return\n', files)
    assert 'unexpected-return' not in out and 'refresh:' not in out, out
    print('PASS stock screen signal during capture')


def logging_checks():
    out, _ = shell('''
exit_status startup
exit_status 'ineligible capture-failed governor'
exit_status startup
[ "$(grep -c startup exit-status.log)" = 2 ] || exit 40
grep -q 'ineligible capture-failed governor' exit-status.log || exit 41
# A large existing log is retained as the sole backup at the next append.
dd if=/dev/zero bs=16384 count=1 >>exit-status.log 2>/dev/null
exit_status 'window timeout'
grep -q 'capture-failed governor' exit-status.log.1 || exit 42
[ "$(wc -c <exit-status.log)" -lt 1024 ] || exit 43
dd if=/dev/zero bs=16384 count=1 >>exit-status.log 2>/dev/null
exit_status 'cleanup restored'
[ ! -e exit-status.log.2 ] || exit 44
grep -q 'window timeout' exit-status.log.1 || exit 45
echo log-ok
''')
    assert 'log-ok' in out
    out, _ = shell('''
DIR=/proc/trmnl-unwritable
exit_status startup && exit 46
echo continued
''', stderr='TRMNL: could not write exit-status.log\n')
    assert 'continued' in out
    print('PASS persistent reasons, rotation/retention and unwritable fallback')


def asset_checks():
    for action in ('touch', 'button'):
        data = (ROOT/f'zip_example/exit-{action}.png').read_bytes()
        assert data[:8] == b'\x89PNG\r\n\x1a\n'
        assert struct.unpack('>IIBBBBB', data[16:29]) == (600, 200, 8, 0, 0, 0, 0)
        offset = 8
        while offset < len(data):
            size = struct.unpack('>I', data[offset:offset+4])[0]
            chunk = data[offset+4:offset+8+size]
            crc = struct.unpack('>I', data[offset+8+size:offset+12+size])[0]
            assert zlib.crc32(chunk) == crc, action
            offset += size+12
        source = ET.parse(ROOT/f'images/exit-prompts/{action}.svg').getroot()
        assert not any(node.tag.rsplit('}', 1)[-1] in ('text', 'image', 'script')
                       for node in source.iter()), action
        print('PASS packaged wordless grayscale asset', action)


if __name__ == '__main__':
    asset_checks()
    reader_checks()
    top_level_signal_checks()
    selection_checks()
    lifecycle_checks()
    stock_screen_checks()
    logging_checks()
