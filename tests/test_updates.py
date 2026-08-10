import unittest

from jarvis_os.updates import UpdateChecker


class UpdateTests(unittest.TestCase):
    def test_semantic_version_comparison(self):
        self.assertGreater(UpdateChecker._version("7.1.0"), UpdateChecker._version("7.0.9"))
        self.assertEqual(UpdateChecker._version("v7.0.0"), (7, 0, 0))


if __name__ == "__main__":
    unittest.main()
