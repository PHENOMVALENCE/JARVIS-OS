import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from jarvis_os.commands import ActionResult, Command, Risk
from jarvis_os.security import AuditLog, SecureExecutor
from jarvis_os.storage import Database, PermissionRepository


class SecureExecutorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.audit = AuditLog(Path(self.temp.name) / "audit.db")
        self.actions = Mock()
        self.actions.execute.return_value = ActionResult(True, "done")

    def tearDown(self):
        self.temp.cleanup()

    def test_low_risk_action_runs_without_prompt(self):
        confirm = Mock()
        result = SecureExecutor(self.actions, self.audit, confirm).execute(Command("open_app"))
        self.assertTrue(result.success)
        confirm.assert_not_called()

    def test_sensitive_action_can_be_cancelled(self):
        command = Command("delete_path", {"path": "notes"}, Risk.HIGH)
        result = SecureExecutor(self.actions, self.audit, lambda _: False).execute(command)
        self.assertFalse(result.success)
        self.actions.execute.assert_not_called()
        self.assertEqual(self.audit.recent()[0]["approved"], 0)

    def test_approved_action_is_executed_and_logged(self):
        command = Command("close_app", {"name": "spotify"}, Risk.MEDIUM)
        result = SecureExecutor(self.actions, self.audit, lambda _: True).execute(command)
        self.assertTrue(result.success)
        self.assertEqual(self.audit.recent()[0]["success"], 1)

    def test_permission_repository_can_deny_low_risk_action(self):
        permissions = PermissionRepository(Database(Path(self.temp.name) / "settings.db"))
        permissions.set("open_app", "deny")
        result = SecureExecutor(self.actions, self.audit, permissions=permissions).execute(Command("open_app"))
        self.assertFalse(result.success)
        self.actions.execute.assert_not_called()

    def test_permission_repository_can_allow_sensitive_action(self):
        permissions = PermissionRepository(Database(Path(self.temp.name) / "settings.db"))
        permissions.set("close_app", "allow")
        result = SecureExecutor(self.actions, self.audit, permissions=permissions).execute(
            Command("close_app", {"name": "spotify"}, Risk.MEDIUM)
        )
        self.assertTrue(result.success)

    def test_audit_chain_detects_tampering(self):
        SecureExecutor(self.actions, self.audit).execute(Command("open_app"))
        self.assertTrue(self.audit.verify())
        with self.audit._connect() as database:
            database.execute("UPDATE actions SET message='changed' WHERE id=1")
        self.assertFalse(self.audit.verify())


if __name__ == "__main__":
    unittest.main()
