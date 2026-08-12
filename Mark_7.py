"""J.A.R.V.I.S desktop entry point."""

import ctypes
import os
import sys


def main():
    # The release build runs this to prove the bundle can load every
    # subsystem, which a successful PyInstaller run does not guarantee.
    if os.environ.get("JARVIS_SELFTEST"):
        from jarvis_os.selftest import run as selftest

        sys.exit(selftest())

    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "JARVIS_MARK_7_SINGLE_INSTANCE")
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        # Exiting in silence looks identical to a crash: someone double-clicks
        # the shortcut and nothing happens. Show the instance already running.
        _raise_existing_window()
        return

    from jarvis_os.app import run

    run()


def _raise_existing_window() -> None:
    """Bring the running instance forward instead of exiting quietly."""
    user32 = ctypes.windll.user32
    found = []

    def visit(handle, _extra):
        length = user32.GetWindowTextLengthW(handle)
        if length and user32.IsWindowVisible(handle):
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(handle, buffer, length + 1)
            if "J.A.R.V.I.S" in buffer.value:
                found.append(handle)
        return True

    try:
        callback = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(visit)
        user32.EnumWindows(callback, 0)
        if found:
            user32.ShowWindow(found[0], 9)  # SW_RESTORE
            user32.SetForegroundWindow(found[0])
    except Exception:
        # Nothing useful to do if the window cannot be raised; the running
        # instance is still there and still working.
        pass


if __name__ == "__main__":
    main()
