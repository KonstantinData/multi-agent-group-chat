"""Preflight check: validates everything needed before starting Streamlit."""
import sys
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

PASS = 0
FAIL = 0

def check(label, fn):
    global PASS, FAIL
    try:
        result = fn()
        print(f"  [OK] {label}: {result}")
        PASS += 1
    except Exception as e:
        print(f"  [FAIL] {label}: {e}")
        FAIL += 1

print("=" * 60)
print("PREFLIGHT CHECK")
print("=" * 60)

# 1. Python
print("\n1. Python")
check("Version", lambda: sys.version.split()[0])
check("Executable", lambda: sys.executable)

# 2. Required packages
print("\n2. Packages")
for pkg, imp in [
    ("streamlit", "streamlit"),
    ("autogen (pyautogen)", "autogen"),
    ("pydantic", "pydantic"),
    ("python-dotenv", "dotenv"),
    ("fpdf2", "fpdf"),
]:
    check(pkg, lambda i=imp: (m := __import__(i)) and getattr(m, "__version__", "ok"))

# 3. Project files
print("\n3. Project files")
for f in [
    "ui/app.py",
    "src/pipeline_runner.py",
    "src/config/settings.py",
    "src/agents/definitions.py",
    "src/models/schemas.py",
    "src/exporters/pdf_report.py",
    "src/exporters/json_export.py",
    ".env",
    ".streamlit/config.toml",
]:
    check(f, lambda f=f: "exists" if os.path.isfile(f) else (_ for _ in ()).throw(FileNotFoundError(f"NOT FOUND: {f}")))

# 4. .env has API key
print("\n4. Environment")
check("OPENAI_API_KEY in .env", lambda: (
    "set" if any("OPENAI_API_KEY" in line for line in open(".env")) else
    (_ for _ in ()).throw(ValueError("OPENAI_API_KEY not found in .env"))
))

# 5. Import chain (what Streamlit actually does)
print("\n5. Import chain (simulates Streamlit loading app.py)")
sys.path.insert(0, os.getcwd())
check("src.config", lambda: __import__("src.config") and "ok")
check("src.models.schemas", lambda: __import__("src.models.schemas") and "ok")
check("src.agents.definitions", lambda: __import__("src.agents.definitions") and "ok")
check("src.pipeline_runner", lambda: __import__("src.pipeline_runner") and "ok")
check("src.exporters.pdf_report", lambda: __import__("src.exporters.pdf_report") and "ok")
check("src.exporters.json_export", lambda: __import__("src.exporters.json_export") and "ok")

# 6. Port 8501
print("\n6. Port 8501")
import socket
def check_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", 8501))
        s.close()
        return "free"
    except OSError:
        s.close()
        raise OSError("PORT 8501 IS IN USE - kill the old process first!")
check("Port 8501", check_port)

# 7. Streamlit CLI
print("\n7. Streamlit CLI")
check("streamlit.web.cli", lambda: __import__("streamlit.web.cli") and "ok")

# Summary
print("\n" + "=" * 60)
if FAIL == 0:
    print(f"ALL {PASS} CHECKS PASSED - ready to start Streamlit!")
else:
    print(f"{FAIL} CHECK(S) FAILED out of {PASS + FAIL} - fix before starting!")
print("=" * 60)

sys.exit(FAIL)
