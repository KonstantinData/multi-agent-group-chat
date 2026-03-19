"""Launcher: preflight check, start Streamlit, open browser automatically."""
import subprocess
import sys
import os
import time
import socket
import webbrowser
import signal

os.chdir(os.path.dirname(os.path.abspath(__file__)))
PYTHON = sys.executable
PORT = 8501
URL = f"http://localhost:{PORT}"


def kill_port(port):
    """Kill any process using the given port."""
    try:
        out = subprocess.check_output(
            f'netstat -ano | findstr ":{port}" | findstr "ABHÖREN"',
            shell=True, text=True,
        )
        for line in out.strip().splitlines():
            pid = line.strip().split()[-1]
            if pid.isdigit():
                subprocess.run(f"taskkill /PID {pid} /F", shell=True,
                               capture_output=True)
                print(f"  Killed old process PID {pid}")
    except subprocess.CalledProcessError:
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


def main():
    print("=" * 60)
    print("  Liquisto Market Intelligence Pipeline")
    print("=" * 60)

    # Step 1: Preflight
    print("\n[1/4] Running preflight checks...")
    ret = subprocess.run([PYTHON, "preflight.py"], capture_output=True, text=True)
    if ret.returncode != 0:
        print(ret.stdout)
        print(ret.stderr)
        print("\nPreflight FAILED. Cannot start.")
        input("Press Enter to exit...")
        sys.exit(1)
    print("  All checks passed.")

    # Step 2: Free port
    print(f"\n[2/4] Ensuring port {PORT} is free...")
    if not port_free(PORT):
        kill_port(PORT)
        time.sleep(1)
        if not port_free(PORT):
            print(f"  ERROR: Port {PORT} still in use. Cannot start.")
            input("Press Enter to exit...")
            sys.exit(1)
    print(f"  Port {PORT} is free.")

    # Step 3: Start Streamlit
    print(f"\n[3/4] Starting Streamlit server...")
    proc = subprocess.Popen(
        [PYTHON, "-m", "streamlit", "run", "ui/app.py",
         "--server.headless", "true", "--server.port", str(PORT)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
    )

    print(f"  Waiting for server (PID {proc.pid})...")
    if not wait_for_server(PORT, timeout=30):
        print("  ERROR: Server did not start within 30 seconds.")
        proc.kill()
        input("Press Enter to exit...")
        sys.exit(1)
    print(f"  Server is running on {URL}")

    # Step 4: Open browser
    print(f"\n[4/4] Opening browser...")
    webbrowser.open(URL)
    print(f"  Browser opened.")

    print("\n" + "=" * 60)
    print(f"  Streamlit running at {URL}")
    print("  Press Ctrl+C to stop the server.")
    print("=" * 60)

    # Keep running until Ctrl+C or process dies
    try:
        while proc.poll() is None:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        proc.terminate()
        proc.wait(timeout=5)

    print("Server stopped.")


if __name__ == "__main__":
    main()
