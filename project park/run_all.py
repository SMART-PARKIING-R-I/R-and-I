"""
One-command launcher for the Smart Parking system.

Starts the Flask backend, waits until it (and MySQL) are healthy, then starts
the detector. Ctrl+C (or closing the window) stops everything.

Usage (from the "project park" folder):
    python run_all.py                 # backend + detector
    python run_all.py --no-detector   # backend only (e.g. when using a simulator)
"""
import argparse
import os
import subprocess
import sys
import time
import urllib.request
import webbrowser

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HEALTH_URL = "http://127.0.0.1:5000/api/health"
PAGE_URL = "http://127.0.0.1:5000/static/lot_view.html"


def mysql_ok():
    try:
        from db import get_connection
        conn = get_connection()
        conn.close()
        return True
    except Exception as exc:
        print(f"[LAUNCHER] MySQL check failed: {exc}")
        return False


def wait_for_backend(proc, timeout=40):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(HEALTH_URL, timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(1)
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-detector", action="store_true")
    ap.add_argument("--no-browser", action="store_true", help="do not open the lot view page")
    args = ap.parse_args()

    os.chdir(BASE_DIR)
    sys.path.insert(0, BASE_DIR)

    print("[LAUNCHER] Checking MySQL...")
    if not mysql_ok():
        print("[LAUNCHER] Start the MySQL service first (Services > MySQL80 > Start), "
              "and check your .env file.")
        input("Press Enter to close...")
        return 1

    # Make sure tables, lots and bays exist (safe to repeat; keeps live status).
    for script in ("init_db.py", "seed_lot_view.py"):
        result = subprocess.run([sys.executable, script], cwd=BASE_DIR)
        if result.returncode != 0:
            print(f"[LAUNCHER] Warning: {script} failed. See the error above.")

    procs = []
    try:
        print("[LAUNCHER] Starting backend...")
        backend = subprocess.Popen([sys.executable, "backend.py"], cwd=BASE_DIR)
        procs.append(backend)

        if not wait_for_backend(backend):
            print("[LAUNCHER] Backend did not become healthy. See the errors above.")
            return 1
        print("[LAUNCHER] Backend is up.")

        if not args.no_detector:
            print("[LAUNCHER] Starting detector...")
            procs.append(subprocess.Popen([sys.executable, "detector.py"], cwd=BASE_DIR))

        if not args.no_browser:
            webbrowser.open(PAGE_URL)

        print("[LAUNCHER] Running. Press Ctrl+C to stop everything.")
        while True:
            for p in procs:
                if p.poll() is not None:
                    print(f"[LAUNCHER] A process exited (code {p.returncode}); shutting down.")
                    return p.returncode or 0
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[LAUNCHER] Stopping...")
    finally:
        for p in procs:
            if p.poll() is None:
                p.terminate()
        for p in procs:
            try:
                p.wait(timeout=8)
            except subprocess.TimeoutExpired:
                p.kill()
    return 0


if __name__ == "__main__":
    sys.exit(main())
