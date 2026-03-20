"""End-to-end startup check: preflight -> start Streamlit -> HTTP check -> cleanup."""
from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request

os.chdir(os.path.dirname(os.path.abspath(__file__)))
PYTHON = sys.executable
PORT = 8501
URL = f"http://localhost:{PORT}"


def step(num: int, total: int, label: str) -> None:
    print(f"\n[{num}/{total}] {label}")


def _listening_pids_windows(port: int) -> list[int]:
    out = subprocess.check_output(
        ["netstat", "-ano"],
        text=True,
        stderr=subprocess.DEVNULL,
    )
    pids = []
    for line in out.splitlines():
        if f":{port}" not in line:
            continue
        upper = line.upper()
        if "LISTENING" not in upper and "ABH" not in upper:
            continue
        parts = line.split()
        if parts and parts[-1].isdigit():
            pids.append(int(parts[-1]))
    return pids


def _listening_pids_posix(port: int) -> list[int]:
    proc = subprocess.run(
        ["lsof", "-ti", f"tcp:{port}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return [int(pid) for pid in proc.stdout.split() if pid.isdigit()]


def listening_pids(port: int) -> list[int]:
    if os.name == "nt":
        return _listening_pids_windows(port)
    return _listening_pids_posix(port)


def kill_port(port: int) -> None:
    try:
        pids = listening_pids(port)
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("  Could not inspect port owners.")
        return

    if not pids:
        print("  No old process found.")
        return

    for pid in pids:
        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/F"],
                    capture_output=True,
                    check=False,
                )
            else:
                os.kill(pid, signal.SIGTERM)
            print(f"  Killed PID {pid}")
        except OSError:
            continue


def port_is_free(port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def _popen_streamlit() -> subprocess.Popen:
    popen_kwargs = {
        "args": [
            PYTHON, "-m", "streamlit", "run", "ui/app.py",
            "--server.headless", "true", "--server.port", str(PORT),
        ],
        "stdout": subprocess.PIPE,
        "stderr": subprocess.STDOUT,
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_kwargs["start_new_session"] = True
    return subprocess.Popen(**popen_kwargs)


def main() -> int:
    errors: list[str] = []
    proc: subprocess.Popen | None = None

    step(1, 5, f"Kill old Streamlit processes on port {PORT}")
    kill_port(PORT)
    time.sleep(1)
    if port_is_free(PORT):
        print("  PASS - port is free")
    else:
        errors.append(f"Port {PORT} still in use after cleanup")
        print(f"  FAIL - port {PORT} still in use")

    step(2, 5, "Preflight checks")
    if not errors:
        preflight = subprocess.run([PYTHON, "preflight.py"], capture_output=True, text=True)
        if preflight.returncode != 0:
            print(preflight.stdout)
            if preflight.stderr:
                print(preflight.stderr)
            errors.append("Preflight failed")
        else:
            print("  PASS - all checks OK")
    else:
        print("  SKIPPED (previous errors)")

    step(3, 5, "Start Streamlit subprocess")
    if not errors:
        proc = _popen_streamlit()
        print(f"  Started PID {proc.pid}")
    else:
        print("  SKIPPED (previous errors)")

    step(4, 5, "Wait for server to accept connections")
    if proc:
        ready = False
        for i in range(30):
            probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                probe.settimeout(1)
                probe.connect(("127.0.0.1", PORT))
                ready = True
                print(f"  PASS - server ready after {i + 1}s")
                break
            except (ConnectionRefusedError, OSError):
                time.sleep(1)
            finally:
                probe.close()
        if not ready:
            errors.append("Server did not start within 30s")
            print("  FAIL - timeout")
            proc.kill()
            proc = None
    else:
        print("  SKIPPED")

    step(5, 5, "HTTP response check")
    if proc and not errors:
        try:
            resp = urllib.request.urlopen(URL, timeout=5)
            if resp.status == 200:
                print(f"  PASS - HTTP {resp.status}")
            else:
                errors.append(f"HTTP {resp.status}")
                print(f"  FAIL - HTTP {resp.status}")
        except Exception as exc:
            errors.append(f"HTTP error: {exc}")
            print(f"  FAIL - {exc}")
    else:
        print("  SKIPPED")

    print("\n" + "=" * 60)
    if errors:
        print(f"FAILED - {len(errors)} error(s):")
        for error in errors:
            print(f"  - {error}")
        if proc and proc.poll() is None:
            proc.kill()
        return 1

    print("ALL 5 STEPS PASSED")
    print(f"Streamlit reachable at {URL} (PID {proc.pid})")
    if proc and proc.poll() is None:
        proc.kill()
        print("Test server stopped.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
