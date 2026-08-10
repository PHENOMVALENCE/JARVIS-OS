import unittest
from unittest.mock import Mock, patch

from jarvis_os.user_presence import SecuritySession


class UserPresenceTests(unittest.TestCase):
    def test_unexpired_session_does_not_prompt(self):
        verifier = Mock()
        session = SecuritySession(verifier, timeout_minutes=15)
        self.assertTrue(session.authorize("test"))
        verifier.verify.assert_not_called()

    def test_locked_session_fails_closed(self):
        verifier = Mock()
        verifier.verify.return_value = False
        session = SecuritySession(verifier)
        session.lock()
        self.assertFalse(session.authorize("test"))

    def test_successful_verification_unlocks_session(self):
        verifier = Mock()
        verifier.verify.return_value = True
        session = SecuritySession(verifier, always_verify=True)
        self.assertTrue(session.authorize("test"))
        verifier.verify.assert_called_once()


if __name__ == "__main__":
    unittest.main()
