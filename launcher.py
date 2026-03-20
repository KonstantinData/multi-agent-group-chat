"""Launcher: preflight check, start Streamlit, open browser automatically."""
from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
import socket
import webbrowser
from typing import Iterable

os.chdir(os.path.dirname(os.path.abspath(__file__)))
PYTHON = sys.executable
PORT = 8501
URL = f"http://localhost:{PORT}"


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


def _listening_pids(port: int) -> list[int]:
    if os.name == "nt":
        return _listening_pids_windows(port)
    return _listening_pids_posix(port)


def _terminate_pids(pids: Iterable[int]) -> None:
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
            print(f"  Killed old process PID {pid}")
        except OSError:
            continue


def kill_port(port):
    """Kill any process using the given port."""
    try:
        _terminate_pids(_listening_pids(port))
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass


def port_free(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def wait_for_server(port, timeout=30):
    """Wait until the server accepts connections."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            s.connect(("127.0.0.1", port))
            s.close()
            return True
        except (ConnectionRefusedError, OSError):
            time.sleep(0.5)
    return False


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch the Streamlit UI for the Liquisto pipeline.")
    parser.add_argument(
        "--foreground",
        action="store_true",
        help="Keep the launcher attached to the Streamlit process instead of exiting after startup.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    print("=" * 60)
    print("  Liquisto Market Intelligence Pipeline")
    print("=" * 60)

    # Step 1: Free port
    print(f"\n[1/4] Ensuring port {PORT} is free...")
    if not port_free(PORT):
        kill_port(PORT)
        time.sleep(1)
        if not port_free(PORT):
            print(f"  ERROR: Port {PORT} still in use. Cannot start.")
            return 1
    print(f"  Port {PORT} is free.")

    # Step 2: Preflight
    print("\n[2/4] Running preflight checks...")
    ret = subprocess.run([PYTHON, "preflight.py"], capture_output=True, text=True)
    if ret.returncode != 0:
        print(ret.stdout)
        print(ret.stderr)
        print("\nPreflight FAILED. Cannot start.")
        return 1
    print("  All checks passed.")

    # Step 3: Start Streamlit
    print(f"\n[3/4] Starting Streamlit server...")
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
    proc = subprocess.Popen(**popen_kwargs)

    print(f"  Waiting for server (PID {proc.pid})...")
    if not wait_for_server(PORT, timeout=30):
        print("  ERROR: Server did not start within 30 seconds.")
        proc.kill()
        return 1
    print(f"  Server is running on {URL}")

    # Step 4: Open browser
    print(f"\n[4/4] Opening browser...")
    webbrowser.open(URL)
    print(f"  Browser opened.")

    print("\n" + "=" * 60)
    print(f"  Streamlit running at {URL}")
    if args.foreground:
        print("  Press Ctrl+C to stop the server.")
    else:
        print("  Launcher exits now. Streamlit continues in the background.")
    print("=" * 60)

    if not args.foreground:
        return 0

    try:
        while proc.poll() is None:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        proc.terminate()
        proc.wait(timeout=5)

    print("Server stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
