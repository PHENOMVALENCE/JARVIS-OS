"""Windows Credential Manager storage and secret redaction."""

from __future__ import annotations

import re


PREFIX = "JARVIS/"


class CredentialStore:
    def set(self, name: str, secret: str, username: str = "JARVIS") -> None:
        import win32cred
        win32cred.CredWrite({
            "Type": win32cred.CRED_TYPE_GENERIC,
            "TargetName": PREFIX + name,
            "UserName": username,
            "CredentialBlob": secret,
            "Persist": win32cred.CRED_PERSIST_LOCAL_MACHINE,
        }, 0)

    def get(self, name: str) -> str:
        import win32cred
        try:
            credential = win32cred.CredRead(PREFIX + name, win32cred.CRED_TYPE_GENERIC, 0)
        except win32cred.error:
            return ""
        blob = credential.get("CredentialBlob", b"")
        return blob.decode("utf-16-le") if isinstance(blob, bytes) else str(blob)

    def delete(self, name: str) -> None:
        import win32cred
        try:
            win32cred.CredDelete(PREFIX + name, win32cred.CRED_TYPE_GENERIC, 0)
        except win32cred.error:
            pass


def redact_secrets(text: str, known_secrets: list[str] | None = None) -> str:
    redacted = text
    for secret in known_secrets or []:
        if secret:
            redacted = redacted.replace(secret, "[REDACTED]")
    patterns = (
        r"(?i)(api[_ -]?key|token|password|secret)(\s*[:=]\s*)[^\s,;]+",
        r"\b(?:ghp|github_pat|sk)-[A-Za-z0-9_-]{12,}\b",
    )
    redacted = re.sub(patterns[0], r"\1\2[REDACTED]", redacted)
    redacted = re.sub(patterns[1], "[REDACTED]", redacted)
    return redacted
