#!/usr/bin/env python3
"""Run: python3 tests/powerd-mode.py (host sh; no Kindle or network needed).

Drives TRMNL_powerd.sh (SLEEP_MODE=powerd) through scripted powerd events with the device
commands faked, and checks what it asks powerd and the screen to do.
"""
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]

STUB = r'''#!/usr/bin/env python3
import json, os, pathlib, sys
p = pathlib.Path(os.environ['CASE_DIR'])
name, args = pathlib.Path(sys.argv[0]).name, sys.argv[1:]
st = json.loads((p/'state').read_text())
def save(): (p/'state').write_text(json.dumps(st))
def event(*v):
    with (p/'events').open('a') as f: f.write(json.dumps(list(v))+'\n')
connected = lambda: st['wifi'] == 1 and st['pd'] == 'active'   # Wi-Fi joins only when active
if name == 'lipc-get-prop':
    prop = args[-1]
    if prop == 'state': print(st['pd'])
    elif prop == 'cmState': print('CONNECTED' if connected() else 'NA')
    elif prop == 'profileCount': print(1)
    elif prop == 'status': print('Battery Level: 50%')
    elif prop == 'wirelessEnable': print(st['wifi'])
elif name == 'lipc-set-prop':
    prop, val = args[-2], args[-1]
    if prop == 'wirelessEnable': st['wifi'] = int(val)
    elif prop == 'wakeUp': st['pd'] = 'active'; event('wakeUp')
    elif prop == 'rtcWakeup': event('rtcWakeup', int(val))
    save()
elif name == 'powerd_test':
    st['pd'] = 'screenSaver'; save(); event('to-screensaver')
elif name == 'ping':
    sys.exit(0 if connected() else 1)
elif name == 'curl':
    assert connected(), 'fetch without network'
    if '-o' in args:
        pathlib.Path(args[args.index('-o')+1]).write_text('png'); event('image')
    else:
        print('{"image_url":"https://example.invalid/i.png","refresh_rate":900}'); event('metadata')
elif name == 'eips':
    if '-g' in args: event('draw', st['pd'])
elif name == 'lipc-wait-event':
    script = json.loads(os.environ['EVENTS'])
    if st['ev'] >= len(script):                          # script done: end the client
        import signal; os.killpg(os.getpgid(0), signal.SIGTERM)
    e = script[st['ev']]; st['ev'] += 1
    if e == 'wakeupFromSuspend': st['wifi'] = 0; st['clock'] += 900   # timed wake, radio off
    if e == 'outOfScreenSaver': st['pd'] = 'active'      # power button
    save(); event('event', e); print(e + ' 0')
elif name == 'date':
    if args == ['+%s']: print(st['clock'])
    else: os.execvp('/bin/date', ['date'] + args)
elif name == 'sleep':
    pass
elif name == 'setsid':
    event('ui-stand-in', *[pathlib.Path(a).name for a in args])
elif name in ('stop', 'initctl'):
    event('ui-stop', args[-1])
'''


def run(name, events, expect, stop_ui=0):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d)
        (p/'bin').mkdir()
        for c in ['lipc-get-prop', 'lipc-set-prop', 'lipc-wait-event', 'powerd_test', 'ping', 'curl', 'eips', 'sleep',
                  'date', 'setsid', 'stop', 'start', 'initctl', 'pkill', 'lua']:
            (p/'bin'/c).write_text(STUB)
            (p/'bin'/c).chmod(0o755)
        (p/'state').write_text(json.dumps(dict(pd='active', wifi=1, ev=0, clock=1_000_000)))
        (p/'events').touch()
        for f in ['TRMNL.sh', 'TRMNL_powerd.sh', 'utils.sh', 'wifi-error.png']:
            data = (ROOT/'zip_example'/f).read_bytes()
            if f.endswith('.sh'):
                s = data.decode()
                s = s.replace('/var/local/', str(p/'var')+'/').replace('/sys/', str(p/'sys')+'/')
                s = s.replace('export PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin', 'true')
                s = s.replace('MAC_ADDRESS=$(get_mac_address)', 'MAC_ADDRESS=TEST_MAC')
                s = s.replace('/etc/init.d/framework', 'false')
                assert '/var/local/' not in s and '/sys/' not in s.replace(str(p/'sys')+'/', ''), f
                data = s.encode()
            (p/f).write_bytes(data)
        (p/'var/system').mkdir(parents=True)
        (p/'TRMNL_config.sh').write_text(f'API_KEY=TEST_ONLY\nSLEEP_MODE=powerd\nSTOP_UI={stop_ui}\n')
        env = dict(os.environ, PATH=str(p/'bin')+':'+os.environ['PATH'], CASE_DIR=str(p), EVENTS=json.dumps(events))
        # Started through TRMNL.sh, as KUAL does: SLEEP_MODE=powerd must hand over.
        r = subprocess.run(['sh', './TRMNL.sh'], cwd=p, env=env, capture_output=True, text=True, timeout=60,
                           start_new_session=True)
        got = [json.loads(l) for l in (p/'events').read_text().splitlines()]
        assert r.returncode == -15 and not r.stderr, (name, r.returncode, r.stderr)
        assert got == expect, (name, got)
        print('PASS', name)


if __name__ == '__main__':
    # Kindle UI kept running (STOP_UI=0).
    start = [['metadata'], ['image'], ['to-screensaver'], ['draw', 'screenSaver']]
    run('start: fetch, hand over to the screensaver, draw', [], start)
    run('before suspend: ask powerd to wake us at the next refresh', ['readyToSuspend'],
        start + [['event', 'readyToSuspend'], ['rtcWakeup', 900]])
    run('timed wake: wake powerd so Wi-Fi joins, fetch, back to screensaver, draw', ['wakeupFromSuspend'],
        start + [['event', 'wakeupFromSuspend'], ['wakeUp'], ['metadata'], ['image'], ['to-screensaver'],
                 ['draw', 'screenSaver']])
    run('screensaver: redraw the dashboard over the Kindle screensaver', ['goingToScreenSaver'],
        start + [['event', 'goingToScreenSaver'], ['draw', 'screenSaver']])
    # Kindle UI stopped (STOP_UI=1, the default).
    ui = [['ui-stop', 'framework'], ['ui-stop', 'lab126_gui'], ['ui-stop', 'webreader'],
          ['ui-stand-in', 'lua', 'kaf.lua']]
    start1 = ui + [['metadata'], ['image'], ['draw', 'active'], ['to-screensaver'], ['draw', 'screenSaver']]
    run('no UI: stop it, start the stand-in, fetch, draw, screensaver', [], start1, stop_ui=1)
    run('no UI: power button refreshes now', ['outOfScreenSaver'],
        start1 + [['event', 'outOfScreenSaver'], ['metadata'], ['image'], ['draw', 'active'], ['to-screensaver'],
                  ['draw', 'screenSaver']], stop_ui=1)
    run('no UI: timed wake refreshes', ['readyToSuspend', 'wakeupFromSuspend'],
        start1 + [['event', 'readyToSuspend'], ['rtcWakeup', 900], ['event', 'wakeupFromSuspend'], ['wakeUp'],
                  ['metadata'], ['image'], ['draw', 'active'], ['to-screensaver'], ['draw', 'screenSaver']], stop_ui=1)
