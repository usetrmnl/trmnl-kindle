#!/usr/bin/env python3
"""Run: python3 tests/network-recovery.py (host bash; no Kindle or network needed)."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]

# Only device commands are faked; the production loop and readiness helper run.
STUB = r'''#!/usr/bin/env python3
import json, os, pathlib, sys
p = pathlib.Path(os.environ['CASE_DIR'])
name, args = pathlib.Path(sys.argv[0]).name, sys.argv[1:]
state = json.loads((p/'state').read_text())
plans = json.loads(os.environ['PLANS'])
interface = p/'sys/class/net/wlan0'
def save():
    (p/'state').write_text(json.dumps(state))
def event(*value):
    with (p/'events').open('a') as f:
        f.write(json.dumps([state['cycle'], *value])+'\n')
def mode():
    return plans[min(state['cycle'], len(plans)-1)][state['retry']]
def update_interface():
    if state['wifi'] == 1 and mode() != 'bad':
        interface.mkdir(parents=True, exist_ok=True)
    elif interface.exists():
        interface.rmdir()
if name == 'cat' and args == [str(p/'fb')]:
    event('snapshot-read')
    sys.stdout.buffer.write((p/'fb').read_bytes())
elif name == 'cat':
    os.execv('/bin/cat', ['cat', *args])
elif name == 'ping':
    sys.exit(0 if interface.exists() and mode() != 'icmp' else 1)
elif name == 'lipc-get-prop':
    if args[-1] == 'wirelessEnable':
        if state.pop('empty_read', False): save()
        else: print(state['wifi'])
    elif args[-1] == 'status': print('Battery Level: 50%')
    elif args[-1] == 'preventScreenSaver': print(0)
elif name == 'lipc-set-prop' and args[-2] == 'wirelessEnable':
    state['wifi'] = int(args[-1]); save(); update_interface()
    event('wifi', state['wifi'])
elif name == 'eips':
    if args == ['-i']:
        print('smem_len: 16\nxres: 4 yres: 4\nbits_per_pixel: 8 grayscale: 1\nrotate: 0\n'
              'ywrapstep: 0 line_length: 4\nxres_virtual: 4 yres_virtual: 4\nxoffset: 0 yoffset: 0')
    elif not args: print('usage -y')
    # Native eips on the tested Kindle rejects !: character not available.
    elif args == ['0', '0', '!']: sys.exit(1)
    else:
        if args[0] == '-g':
            assert pathlib.Path(args[1]).is_file(), 'display image missing'
        event('screen', *args)
        if args[0] == '-s':
            assert (p/'fb').read_bytes() == b'0123456789abcdef', 'stock restore before refresh'
        else:
            (p/'fb').write_bytes(b'dashboard-bytes!')
elif name == 'curl':
    assert state['wifi'] == 1 and interface.exists(), 'fetch without network'
    event('image' if '-o' in args else 'metadata')
    if '-o' in args:
        if os.environ.get('FAILED_IMAGE') == '1' and state['cycle'] == 1:
            pathlib.Path(args[args.index('-o')+1]).write_text('partial')
            event('failed-image')
            sys.exit(7)
        pathlib.Path(args[args.index('-o')+1]).write_text('image')
    else:
        print('{"image_url":"https://example.invalid/image","filename":"display.png","refresh_rate":900}')
elif name == 'sleep':
    event('sleep', int(args[0]))
    if args == ['20']:
        state['retry'] += 1; save()
        assert state['retry'] == 1, 'more than one activation retry'
    if args == ['60'] and os.environ.get('FAILED_IMAGE') == '1':
        cache = list((p/'cache').glob('.dashboard-*.png'))
        assert len(cache) == 1 and cache[0].read_text() == 'image', 'failed download replaced dashboard'
        event('cache-preserved')
        state['cycle'] += 1; state['retry'] = 0; save(); update_interface()
elif name == 'test-suspend':
    event('suspend', (p/'sys/class/rtc/rtc1/wakealarm').read_text().strip(), state['wifi'])
    state['cycle'] += 1; state['retry'] = 0; save()
    if state['cycle'] == len(plans): sys.exit(99)
    update_interface()
elif name == 'initctl' and args[0] == 'status':
    print(args[1], 'start/running')
'''


def run_case(name, plans, delays, policy=2, initial=1, debug=False, empty_read=False, failed_image=False):
    with tempfile.TemporaryDirectory() as directory:
        p = Path(directory)
        (p/'bin').mkdir()
        for command in ['cat', 'ping', 'lipc-get-prop', 'lipc-set-prop', 'eips', 'curl', 'sleep', 'test-suspend', 'initctl']:
            path = p/'bin'/command
            path.write_text(STUB)
            path.chmod(0o755)
        (p/'state').write_text(json.dumps(dict(cycle=0, retry=0, wifi=initial, empty_read=empty_read)))
        if initial == 1 and plans[0][0] != 'bad':
            (p/'sys/class/net/wlan0').mkdir(parents=True)
        (p/'events').touch()
        (p/'fb').write_bytes(b'0123456789abcdef')
        (p/'wifi-error.png').write_bytes((ROOT/'zip_example/wifi-error.png').read_bytes())
        for filename in ['sys/class/rtc/rtc1/wakealarm', 'sys/devices/system/cpu/cpu0/cpufreq/scaling_governor']:
            (p/filename).parent.mkdir(parents=True, exist_ok=True)
        (p/'sys/devices/system/cpu/cpu0/cpufreq/scaling_governor').write_text('ondemand')
        # Copy only known source files, never credentials or a user's config.
        for filename in ['TRMNL.sh', 'utils.sh', 'wait-for-wifi.sh']:
            script = (ROOT/'zip_example'/filename).read_text()
            if filename == 'TRMNL.sh':
                replacements = {
                    '/etc/init.d/framework': str(p/'framework'),
                    'MAC_ADDRESS=$(get_mac_address)': 'MAC_ADDRESS=TEST_MAC',
                    'echo "mem" > /sys/power/state': 'test-suspend || exit $?',
                    '/sys/': str(p/'sys')+'/',
                    '/tmp/trmnl-kindle': str(p/'cache'),
                }
                for old, new in replacements.items():
                    assert old in script, f'hardware substitution missing: {old}'
                    script = script.replace(old, new)
            else:
                script = script.replace('/sys/', str(p/'sys')+'/').replace('/etc/init.d/framework', str(p/'framework'))
            script = script.replace('/dev/fb0', str(p/'fb'))
            # Any remaining hardware paths must be inside the disposable directory.
            assert '/etc/init.d/' not in script
            assert '/sys/' not in script.replace(str(p/'sys')+'/', ''), filename
            (p/filename).write_text(script)
        (p/'wait-for-wifi.sh').chmod(0o755)
        (p/'TRMNL_config.sh').write_text(
            f'API_KEY=TEST_ONLY\nMIN_REFRESH_RATE=420\nWIFI_MANAGEMENT={policy}\nDEBUG_MODE={str(debug).lower()}\n')
        env = dict(os.environ, PATH=str(p/'bin')+':'+os.environ['PATH'], CASE_DIR=str(p), PLANS=json.dumps(plans), FAILED_IMAGE=str(int(failed_image)))
        result = subprocess.run(['bash', './TRMNL.sh'], cwd=p, env=env, capture_output=True, text=True, timeout=30)
        expected_stderr = ('TRMNL: exit confirmation unavailable (original state unavailable)\n'
                           'TRMNL: restoration incomplete (original state unavailable or restore failed)\n') if empty_read else ''
        assert result.returncode == 99 and result.stderr == expected_stderr, (name, result.returncode, result.stderr)
        if empty_read:
            assert 'Tap anywhere' not in (p/'events').read_text(), 'capture failure offered exit'
        events = [json.loads(line) for line in (p/'events').read_text().splitlines()]
        assert sum(e[1] == 'snapshot-read' for e in events) == 1, events
        capture = next(i for i, e in enumerate(events) if e[1] == 'snapshot-read')
        assert all(i > capture for i, e in enumerate(events) if e[1] == 'screen'), events
        assert not list((p/'cache').glob('.stock-*.fb')), 'snapshot leaked at exit'
        for cycle, (plan, delay) in enumerate(zip(plans, delays)):
            actual = [e[1:] for e in events if e[0] == cycle]
            if failed_image and cycle == 1:
                assert ['failed-image'] in actual and ['cache-preserved'] in actual, (name, actual)
                assert not any(e[0] in ('screen', 'suspend') for e in actual), (name, actual)
                continue
            failed = plan[-1] == 'bad'
            assert [e[1] for e in actual if e[0] == 'suspend'] == [f'+{delay}'], (name, actual)
            assert actual.count(['sleep', 20]) == (1 if plan[0] == 'bad' else 0), (name, actual)
            if plan[0] == 'bad':
                retry = actual.index(['sleep', 20])
                assert actual[retry-1:retry+2] == [['wifi', 0], ['sleep', 20], ['wifi', 1]], (name, actual)
            assert actual.count(['metadata']) == (0 if failed else 1), (name, actual)
            screens = [e for e in actual if e[0] == 'screen']
            if failed:
                if debug:
                    assert screens[0] == ['screen', '-c'], (name, screens)
                    assert ['screen', '0', '0', 'TRMNL Kindle Debug Script'] in screens, (name, screens)
                    assert ['screen', '-g', './wifi-error.png'] in screens, (name, screens)
                else:
                    assert screens == [['screen', '-g', './wifi-error.png']], (name, screens)
                assert actual[-1][-1] == 0, (name, actual)  # failed attempts sleep with radio off
            else:
                assert ['screen', '-g', './wifi-error.png'] not in screens, (name, screens)
                assert ['screen', '-c'] in screens and any(e[1] == '-g' for e in screens), (name, screens)
                assert screens.index(['screen', '-c']) < next(i for i, e in enumerate(screens) if e[1] == '-g')
                policy_state = (0 if empty_read else initial) if policy == 0 else int(policy == 1)
                assert actual[-1][-1] == policy_state, (name, actual)
        print('PASS', name)


if __name__ == '__main__':
    run_case('failure then next-wake recovery', [['bad', 'bad'], ['up']], [420, 900])
    run_case('one retry recovers', [['bad', 'up']], [900])
    run_case('filtered ICMP', [['icmp', 'icmp']], [900])
    run_case('last refresh interval reused', [['up'], ['bad', 'bad'], ['up']], [900, 900, 900])
    for policy, initial in [(1, 1), (0, 1), (0, 0)]:
        run_case(f'policy {policy}, initial {initial}', [['bad', 'bad'], ['up']], [420, 900], policy, initial)
    run_case('debug failure retains upstream diagnostics', [['up'], ['bad', 'bad']], [900, 900], debug=True)
    run_case('unknown initial auto state keeps recovery and disables exit', [['bad', 'bad'], ['up']], [420, 900], policy=0, empty_read=True)
    run_case('failed nonempty download preserves last dashboard', [['up'], ['up'], ['up']], [900, 900, 900], failed_image=True)
