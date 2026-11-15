"""Muestrea cgroup v2 del contenedor durante sondas HTTP reales (sin secretos)."""
import argparse
import json
import subprocess
import threading
import time
from pathlib import Path


def inspect(name):
    value = json.loads(subprocess.check_output(['docker', 'inspect', name]))[0]
    return {'State': value['State'], 'limits': {key: value['HostConfig'][key] for key in ('Memory', 'MemorySwap', 'NanoCpus')}, 'Image': value['Image']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--container', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    before = inspect(args.container)
    pid = before['State']['Pid']
    relative = Path(f'/proc/{pid}/cgroup').read_text().strip().split('::')[1]
    directory = Path('/sys/fs/cgroup') / relative.lstrip('/')
    samples = []
    stop = threading.Event()

    def sample():
        while not stop.is_set():
            try:
                row = {'elapsed_s': round(time.monotonic() - started, 3)}
                for filename in ('memory.current', 'memory.peak', 'memory.events', 'memory.swap.current', 'cpu.stat'):
                    row[filename] = (directory / filename).read_text().strip()
                samples.append(row)
            except OSError:
                pass
            stop.wait(0.1)

    started = time.monotonic()
    thread = threading.Thread(target=sample)
    thread.start()
    try:
        command = args.command[1:] if args.command[:1] == ['--'] else args.command
        result = subprocess.run(command, check=False)
    finally:
        stop.set()
        thread.join()
    output = {'before': before, 'after': inspect(args.container), 'elapsed_s': time.monotonic() - started, 'returncode': result.returncode, 'samples': samples, 'max_current_bytes': max((int(s['memory.current']) for s in samples), default=None), 'max_peak_bytes': max((int(s['memory.peak']) for s in samples), default=None)}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(output, indent=2))
    print(json.dumps({k: v for k, v in output.items() if k != 'samples'}, indent=2))


if __name__ == '__main__':
    main()
