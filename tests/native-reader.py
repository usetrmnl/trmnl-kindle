#!/usr/bin/env python3
"""Run in a Linux build container: python3 tests/native-reader.py.
Exercises the real C helper with simulated device input.
Use device tests to check that the Kindle UI does not receive the gesture.
"""
import os
import ctypes
from pathlib import Path
import signal
import struct
import subprocess
import tempfile
import time

assert ctypes.CDLL(None).prctl(36, 1, 0, 0, 0) == 0  # reap orphaned test descendants

ROOT = Path(__file__).resolve().parents[1]

def event(code=330, value=1, kind=1):
    return struct.pack('<IIHHi', 0, 0, kind, code, value)
SYN = event(0, 0, 0)

class Run:
    def __init__(self, binary, directory, held=(), **env):
        self.path = Path(directory)
        self.input = self.path/'input'
        os.mkfifo(self.input)
        self.trace = self.path/'trace'
        self.trace.touch()
        self.state = self.path/'state'
        self.keys(*held)
        self.env = dict(os.environ, INPUT=str(self.input), TRACE=str(self.trace),
                        STATE=str(self.state), **env)
        self.started = time.monotonic()
        self.proc = subprocess.Popen([str(binary), str(self.input), env.get('KEY', '330'), 'prompt.png'],
                                     env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.writer = os.open(self.input, os.O_RDWR | os.O_NONBLOCK)
    def keys(self, *codes):
        bits = bytearray(96)
        for code in codes: bits[code//8] |= 1 << (code%8)
        tmp = self.path/'state.new'; tmp.write_bytes(bits); tmp.replace(self.state)
    def wait(self, marker, limit=2):
        until = time.monotonic()+limit
        while time.monotonic() < until:
            if marker in self.trace.read_text(): return
            if self.proc.poll() is not None: break
            time.sleep(.005)
        trace, status = self.trace.read_text(), self.proc.poll()
        hint = 'Empty trace/status 7: run the container with --init (test parent must not be PID 1).' if status == 7 and not trace else ''
        raise AssertionError((marker, trace, status, hint))
    def emit(self, value, code=330, report=True):
        self.keys(code) if value else self.keys()
        os.write(self.writer, event(code, value)+(SYN if report else b''))
    def done(self, expected, limit=3):
        stdout, stderr = self.proc.communicate(timeout=limit)
        elapsed = time.monotonic()-self.started
        trace = self.trace.read_text()
        os.close(self.writer)
        assert self.proc.returncode == expected, (self.proc.returncode, expected, trace, stderr)
        assert not stdout and not stderr, (stdout, stderr)
        assert 'leaked-input' not in trace, trace
        if 'grab' in trace:
            assert f'{self.proc.pid} close-input' in trace or expected == -signal.SIGKILL, trace
        # A renderer must be gone before shell cleanup could run.
        for line in trace.splitlines():
            pid, what = line.split()
            if what == 'draw':
                if expected == -signal.SIGKILL:
                    until = time.monotonic()+1
                    while time.monotonic() < until:
                        try:
                            if os.waitpid(int(pid), os.WNOHANG)[0]: break
                        except ChildProcessError: break
                        time.sleep(.005)
                assert not Path(f'/proc/{pid}').exists(), ('renderer survived', trace)
        return elapsed, trace

with tempfile.TemporaryDirectory() as tmp:
    build = Path(tmp)
    renderer = build/'renderer'
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                    str(ROOT/'tests/native/renderer.c'), '-o', str(renderer)], check=True)
    helper = build/'exit-input'
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-DEXIT_INPUT_TEST',
                    f'-DEXIT_EIPS_PATH="{renderer}"', str(ROOT/'native/exit-input.c'),
                    str(ROOT/'tests/native/io.c'), '-Wl,--wrap=open,--wrap=fstat,--wrap=ioctl,--wrap=close',
                    '-o', str(helper)], check=True)
    with tempfile.TemporaryDirectory() as case:
        run = Run(helper, case)
        run.wait('draw-done')
        time.sleep(.04)
        run.emit(1)
        time.sleep(.04)
        assert run.proc.poll() is None, 'down alone confirmed'
        run.emit(0, report=False)
        time.sleep(.04)
        assert run.proc.poll() is None, 'release without report confirmed'
        os.write(run.writer, SYN)
        _, trace = run.done(0)
        assert trace.index('grab') < trace.index('draw'), trace
        print('PASS native IO grab-before-draw, complete release, child FD closure')

    for env, expected, draw in [
        ({'GRAB_FAIL': '1'}, 2, False), ({'OPEN_FAIL': '1'}, 9, False),
        ({'NOT_CHAR': '1'}, 9, False), ({'POWER_NODE': '116'}, 9, False),
        ({'KEYS_FAIL': '1'}, 3, False), ({'held': (330,)}, 10, False),
        ({'DRAW_FAIL': '1'}, 6, True), ({'DRAW_BLOCK': '1'}, 6, True),
    ]:
        with tempfile.TemporaryDirectory() as case:
            run = Run(helper, case, **env)
            elapsed, trace = run.done(expected)
            assert (' draw\n' in trace) == draw, trace
            assert elapsed < .7, elapsed
            print('PASS native failure', next(iter(env)))

    for code in (1, 98, 102, 104, 109, 124, 193, 255):
        with tempfile.TemporaryDirectory() as case:
            run = Run(helper, case, KEY='0'); run.wait('draw-done'); time.sleep(.04)
            run.emit(1, code); time.sleep(.03)
            assert run.proc.poll() is None, 'button down alone confirmed'
            run.emit(0, code, report=False); time.sleep(.03)
            assert run.proc.poll() is None, 'button release without report confirmed'
            os.write(run.writer, SYN); run.done(0)
            print('PASS native any button', code)

    for code in (0, 116, 142, 143, 205, 330):
        with tempfile.TemporaryDirectory() as case:
            run = Run(helper, case, KEY='0'); run.wait('draw-done'); time.sleep(.04)
            run.emit(1, code); run.emit(0, code); run.done(1)
            print('PASS native excluded button event', code)

    for power in (116, 142, 143, 205):
        with tempfile.TemporaryDirectory() as case:
            run = Run(helper, case, KEY='0', POWER_NODE=str(power))
            _, trace = run.done(9)
            assert 'grab' not in trace
            print('PASS native excludes mixed power node', power)

    with tempfile.TemporaryDirectory() as case:
        run = Run(helper, case, KEY='0'); run.wait('draw-done'); time.sleep(.04)
        run.emit(1, 104)
        os.write(run.writer, event(109, 0)+SYN); time.sleep(.04)
        assert run.proc.poll() is None, 'different button release confirmed'
        run.emit(0, 104); run.done(0)
        print('PASS native button release must match press')

    for name in ('silence', 'wrong-key', 'release-only', 'repeat-only',
                 'partial', 'dropped', 'drop-after-release', 'held-cutoff', 'release-in-grace', 'late-release', 'flood'):
        with tempfile.TemporaryDirectory() as case:
            run = Run(helper, case); run.wait('draw-done'); time.sleep(.04)
            expected = 1
            if name == 'wrong-key': run.emit(1, 104); run.emit(0, 104)
            elif name == 'release-only': run.emit(0)
            elif name == 'repeat-only': os.write(run.writer, event(value=2)+SYN)
            elif name == 'partial': os.write(run.writer, b'x'); expected = 5
            elif name == 'drop-after-release':
                os.write(run.writer, event()+SYN+event(value=0)+SYN+event(3, 0, 0)+SYN); expected = 4
            elif name == 'dropped':
                os.write(run.writer, event()+SYN+event(3, 0, 0)+SYN); expected = 4
            elif name in ('held-cutoff', 'release-in-grace', 'late-release'):
                if name == 'late-release': time.sleep(.57)
                run.emit(1)
                if name != 'held-cutoff':
                    time.sleep(.14 if name == 'late-release' else .72); run.emit(0)
                else: expected = 8
            elif name == 'flood':
                end = time.monotonic()+1.1
                while run.proc.poll() is None and time.monotonic() < end:
                    try: os.write(run.writer, (event(53, 1, 3)+SYN)*64)
                    except BlockingIOError: time.sleep(.001)
            elapsed, _ = run.done(expected)
            if name in ('silence', 'flood'): assert .65 <= elapsed < 1.15, (name, elapsed)
            if name == 'held-cutoff': assert .85 <= elapsed < 1.25, elapsed
            print('PASS native protocol', name)

    with tempfile.TemporaryDirectory() as case:
        run = Run(helper, case, DRAW_DELAY_US='120000'); run.wait(' draw\n')
        run.emit(1); run.wait('draw-done'); time.sleep(.04)
        run.emit(0); time.sleep(.04)
        assert run.proc.poll() is None, 'drawing-period contact confirmed'
        run.emit(1); time.sleep(.03); run.emit(0); run.done(0)
        print('PASS native drawing-period hold requires a fresh gesture')

    for sig, drawing, held in [(signal.SIGTERM, False, False), (signal.SIGINT, False, False),
                               (signal.SIGHUP, False, False), (signal.SIGTERM, True, False),
                               (signal.SIGTERM, False, True), (signal.SIGKILL, True, False)]:
        with tempfile.TemporaryDirectory() as case:
            run = Run(helper, case, **({'DRAW_BLOCK': '1'} if drawing else {}))
            run.wait(' draw\n' if drawing else 'draw-done'); time.sleep(.03)
            if held: run.emit(1); time.sleep(.02)
            run.proc.send_signal(sig)
            run.done(-sig if sig == signal.SIGKILL else 7)
            print('PASS native cancellation', sig.name, 'drawing' if drawing else 'listening', held)

    # Killing the parent cancels the real helper; the test process is a subreaper.
    with tempfile.TemporaryDirectory() as case:
        path = Path(case); fifo = path/'input'; os.mkfifo(fifo)
        (path/'state').write_bytes(bytes(96)); (path/'trace').touch()
        env = dict(os.environ, INPUT=str(fifo), STATE=str(path/'state'), TRACE=str(path/'trace'))
        parent = os.fork()
        if parent == 0:
            child = os.fork()
            if child == 0: os.execve(helper, [str(helper), str(fifo), '330', 'prompt.png'], env)
            (path/'pid').write_text(str(child))
            while True: signal.pause()
        until = time.monotonic()+2
        while time.monotonic() < until and 'draw-done' not in (path/'trace').read_text(): time.sleep(.005)
        assert 'draw-done' in (path/'trace').read_text()
        child = int((path/'pid').read_text())
        os.kill(parent, signal.SIGKILL); os.waitpid(parent, 0)
        until = time.monotonic()+1
        while time.monotonic() < until:
            ended, status = os.waitpid(child, os.WNOHANG)
            if ended: break
            time.sleep(.005)
        assert ended and os.waitstatus_to_exitcode(status) == 7, (ended, status)
        assert f'{child} close-input' in (path/'trace').read_text()
        print('PASS native parent-death cancellation and FD closure')

    with tempfile.TemporaryDirectory() as case:
        run = Run(helper, case, KEYS_DELAY_AT='4'); run.wait('draw-done'); time.sleep(.56)
        run.emit(1); time.sleep(.025); run.emit(0)
        run.done(1)
        print('PASS native deadline rechecked after neutral ioctl')
    with tempfile.TemporaryDirectory() as case:
        run = Run(helper, case, DRAW_DELAY_US='150000'); run.wait(' draw\n')
        run.emit(1); time.sleep(.02); run.emit(0); run.wait('draw-done')
        run.done(1)
        print('PASS native complete gesture during rendering cannot confirm')

    with tempfile.TemporaryDirectory() as case:
        run = Run(helper, case, DRAW_DELAY_US='120000'); run.wait(' draw\n')
        run.proc.send_signal(signal.SIGSTOP)
        time.sleep(.36)
        run.proc.send_signal(signal.SIGCONT)
        run.done(6)
        print('PASS native renderer deadline checked after delayed reap')
