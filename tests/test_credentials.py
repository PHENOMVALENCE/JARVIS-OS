import unittest

from jarvis_os.credentials import redact_secrets


class CredentialTests(unittest.TestCase):
    def test_redacts_known_and_pattern_secrets(self):
        text = "token=abc123 password: hunter2 known-value"
        result = redact_secrets(text, ["known-value"])
        self.assertNotIn("abc123", result)
        self.assertNotIn("hunter2", result)
        self.assertNotIn("known-value", result)


if __name__ == "__main__":
    unittest.main()
