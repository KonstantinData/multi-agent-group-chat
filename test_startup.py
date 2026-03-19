"""End-to-end test: preflight -> start Streamlit -> HTTP check -> open browser."""
import subprocess
import sys
import os
import time
import socket
import urllib.request
import webbrowser

os.chdir(os.path.dirname(os.path.abspath(__file__)))
PYTHON = sys.executable
PORT = 8501
URL = f"http://localhost:{PORT}"
ERRORS = []


def step(num, total, label):
    print(f"\n[{num}/{total}] {label}")


def kill_port(port):
    try:
        out = subprocess.check_output(
            f'netstat -ano | findstr ":{port}" | findstr "ABHÖREN"',
            shell=True, text=True,
        )
        for line in out.strip().splitlines():
            pid = line.strip().split()[-1]
            if pid.isdigit():
                subprocess.run(f"taskkill /PID {pid} /F", shell=True, capture_output=True)
                print(f"  Killed PID {pid}")
    except subprocess.CalledProcessError:
        print("  No old process found.")


# ---- STEP 1: Preflight ----
step(1, 5, "Preflight checks")
r = subprocess.run([PYTHON, "preflight.py"], capture_output=True, text=True)
if r.returncode != 0:
    print(r.stdout)
    ERRORS.append("Preflight failed")
else:
    print("  PASS - all checks OK")

# ---- STEP 2: Kill old processes ----
step(2, 5, "Kill old Streamlit processes on port 8501")
kill_port(PORT)
time.sleep(1)

# Verify port is free
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    s.bind(("127.0.0.1", PORT))
    s.close()
    print("  PASS - port is free")
except OSError:
    s.close()
    ERRORS.append(f"Port {PORT} still in use after kill")
    print(f"  FAIL - port {PORT} still in use")

# ---- STEP 3: Start Streamlit ----
step(3, 5, "Start Streamlit subprocess")
if not ERRORS:
    proc = subprocess.Popen(
        [PYTHON, "-m", "streamlit", "run", "ui/app.py",
         "--server.headless", "true", "--server.port", str(PORT)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
    )
    print(f"  Started PID {proc.pid}")
else:
    proc = None
    print("  SKIPPED (previous errors)")

# ---- STEP 4: Wait for server ----
step(4, 5, "Wait for server to accept connections")
if proc:
    ready = False
    for i in range(30):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            s.connect(("127.0.0.1", PORT))
            s.close()
            ready = True
            print(f"  PASS - server ready after {i+1}s")
            break
        except (ConnectionRefusedError, OSError):
            time.sleep(1)
    if not ready:
        ERRORS.append("Server did not start within 30s")
        print("  FAIL - timeout")
        proc.kill()
else:
    print("  SKIPPED")

# ---- STEP 5: HTTP check ----
step(5, 5, "HTTP response check")
if proc and not ERRORS:
    try:
        resp = urllib.request.urlopen(URL, timeout=5)
        if resp.status == 200:
            print(f"  PASS - HTTP {resp.status}")
        else:
            ERRORS.append(f"HTTP {resp.status}")
            print(f"  FAIL - HTTP {resp.status}")
    except Exception as e:
        ERRORS.append(f"HTTP error: {e}")
        print(f"  FAIL - {e}")
else:
    print("  SKIPPED")

# ---- SUMMARY ----
print("\n" + "=" * 60)
if ERRORS:
    print(f"FAILED - {len(ERRORS)} error(s):")
    for e in ERRORS:
        print(f"  - {e}")
    if proc and proc.poll() is None:
        proc.kill()
    sys.exit(1)
else:
    print("ALL 5 STEPS PASSED")
    print(f"Streamlit running at {URL} (PID {proc.pid})")
    print("Opening browser now...")
    webbrowser.open(URL)
    print("=" * 60)
    # Leave server running
    sys.exit(0)
