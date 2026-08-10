"""J.A.R.V.I.S Mark 7 desktop entry point."""

import ctypes

from jarvis_os.app import run


def main():
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "JARVIS_MARK_7_SINGLE_INSTANCE")
    if ctypes.windll.kernel32.GetLastError() != 183:
        run()


if __name__ == "__main__":
    main()
