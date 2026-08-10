"""J.A.R.V.I.S Mark 6 desktop entry point."""

import ctypes

from jarvis_os.app import run


if __name__ == "__main__":
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "JARVIS_MARK_6_SINGLE_INSTANCE")
    if ctypes.windll.kernel32.GetLastError() != 183:
        run()
