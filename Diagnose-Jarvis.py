from pathlib import Path

from jarvis_os.diagnostics import run_diagnostics


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    failures = 0
    for item in run_diagnostics(root):
        label = "PASS" if item.success else "FAIL"
        print(f"[{label}] {item.name}: {item.detail}")
        failures += int(not item.success)
    raise SystemExit(1 if failures else 0)
