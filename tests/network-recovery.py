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
    return plans[state['cycle']][state['retry']]
def update_interface():
    if state['wifi'] == 1 and mode() != 'bad':
        interface.mkdir(parents=True, exist_ok=True)
    elif interface.exists():
        interface.rmdir()
if name == 'ping':
    sys.exit(0 if interface.exists() and mode() != 'icmp' else 1)
elif name == 'lipc-get-prop':
    if args[-1] == 'wirelessEnable':
        if state.pop('empty_read', False): save()
        else: print(state['wifi'])
    elif args[-1] == 'status': print('Battery Level: 50%')
elif name == 'lipc-set-prop' and args[-2] == 'wirelessEnable':
    state['wifi'] = int(args[-1]); save(); update_interface()
    event('wifi', state['wifi'])
elif name == 'eips':
    if args == ['-i']: print('xres: 600 yres: 800')
    elif not args: print('usage -y')
    # Native eips on the tested Kindle rejects !: character not available.
    elif args == ['0', '0', '!']: sys.exit(1)
    else:
        if args[0] == '-g':
            assert pathlib.Path(args[1]).is_file(), 'display image missing'
        event('screen', *args)
elif name == 'curl':
    assert state['wifi'] == 1 and interface.exists(), 'fetch without network'
    event('image' if '-o' in args else 'metadata')
    if '-o' in args:
        pathlib.Path(args[args.index('-o')+1]).write_text('image')
    else:
        print('{"image_url":"https://example.invalid/image","filename":"display.png","refresh_rate":900}')
elif name == 'sleep':
    event('sleep', int(args[0]))
    if args == ['20']:
        state['retry'] += 1; save()
        assert state['retry'] == 1, 'more than one activation retry'
elif name == 'test-suspend':
    event('suspend', (p/'sys/class/rtc/rtc1/wakealarm').read_text().strip(), state['wifi'])
    state['cycle'] += 1; state['retry'] = 0; save()
    if state['cycle'] == len(plans): sys.exit(99)
    update_interface()
'''


def run_case(name, plans, delays, policy=2, initial=1, debug=False, empty_read=False):
    with tempfile.TemporaryDirectory() as directory:
        p = Path(directory)
        (p/'bin').mkdir()
        for command in ['ping', 'lipc-get-prop', 'lipc-set-prop', 'eips', 'curl', 'sleep', 'test-suspend', 'initctl']:
            path = p/'bin'/command
            path.write_text(STUB)
            path.chmod(0o755)
        (p/'state').write_text(json.dumps(dict(cycle=0, retry=0, wifi=initial, empty_read=empty_read)))
        if initial == 1 and plans[0][0] != 'bad':
            (p/'sys/class/net/wlan0').mkdir(parents=True)
        (p/'events').touch()
        (p/'wifi-error.png').write_bytes((ROOT/'zip_example/wifi-error.png').read_bytes())
        for filename in ['sys/class/rtc/rtc1/wakealarm', 'sys/devices/system/cpu/cpu0/cpufreq/scaling_governor']:
            (p/filename).parent.mkdir(parents=True, exist_ok=True)
        # Copy only known source files, never credentials or a user's config.
        for filename in ['TRMNL.sh', 'utils.sh', 'wait-for-wifi.sh']:
            script = (ROOT/'zip_example'/filename).read_text()
            if filename == 'TRMNL.sh':
                replacements = {
                    '/etc/init.d/framework stop': ':',
                    'MAC_ADDRESS=$(get_mac_address)': 'MAC_ADDRESS=TEST_MAC',
                    'echo "mem" > /sys/power/state': 'test-suspend || exit $?',
                    '/sys/': str(p/'sys')+'/',
                    '/tmp/trmnl-kindle': str(p/'cache'),
                }
                for old, new in replacements.items():
                    assert old in script, f'hardware substitution missing: {old}'
                    script = script.replace(old, new)
            else:
                script = script.replace('/sys/', str(p/'sys')+'/')
            # Any remaining hardware paths must be inside the disposable directory.
            assert '/etc/init.d/' not in script
            assert '/sys/' not in script.replace(str(p/'sys')+'/', ''), filename
            (p/filename).write_text(script)
        (p/'wait-for-wifi.sh').chmod(0o755)
        (p/'TRMNL_config.sh').write_text(
            f'API_KEY=TEST_ONLY\nMIN_REFRESH_RATE=420\nWIFI_MANAGEMENT={policy}\nDEBUG_MODE={str(debug).lower()}\n')
        env = dict(os.environ, PATH=str(p/'bin')+':'+os.environ['PATH'], CASE_DIR=str(p), PLANS=json.dumps(plans))
        result = subprocess.run(['bash', './TRMNL.sh'], cwd=p, env=env, capture_output=True, text=True, timeout=30)
        assert result.returncode == 99 and not result.stderr, (name, result.returncode, result.stderr)
        events = [json.loads(line) for line in (p/'events').read_text().splitlines()]
        for cycle, (plan, delay) in enumerate(zip(plans, delays)):
            actual = [e[1:] for e in events if e[0] == cycle]
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
    run_case('unknown initial auto state sleeps with Wi-Fi off', [['up']], [900], policy=0, empty_read=True)
