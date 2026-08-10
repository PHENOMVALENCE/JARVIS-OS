"""Windows Hello user-presence checks and inactivity security sessions."""

from __future__ import annotations

import asyncio
import time


class WindowsHelloVerifier:
    def available(self) -> bool:
        try:
            from winrt.windows.security.credentials.ui import UserConsentVerifier, UserConsentVerifierAvailability
            result = asyncio.run(UserConsentVerifier.check_availability_async())
            return result == UserConsentVerifierAvailability.AVAILABLE
        except Exception:
            return False

    def verify(self, message: str = "Approve this J.A.R.V.I.S action") -> bool:
        try:
            from winrt.windows.security.credentials.ui import UserConsentVerifier, UserConsentVerificationResult
            result = asyncio.run(UserConsentVerifier.request_verification_async(message))
            return result == UserConsentVerificationResult.VERIFIED
        except Exception:
            return False


class SecuritySession:
    def __init__(self, verifier=None, timeout_minutes: int = 15, always_verify: bool = False):
        self.verifier = verifier or WindowsHelloVerifier()
        self.timeout_seconds = max(1, timeout_minutes) * 60
        self.always_verify = always_verify
        self.last_activity = time.monotonic()
        self.force_locked = False

    def touch(self) -> None:
        self.last_activity = time.monotonic()

    def lock(self) -> None:
        self.force_locked = True

    def authorize(self, message: str) -> bool:
        expired = time.monotonic() - self.last_activity >= self.timeout_seconds
        if not (self.always_verify or expired or self.force_locked):
            return True
        approved = self.verifier.verify(message)
        if approved:
            self.force_locked = False
            self.touch()
        return approved
