import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from jarvis_os.commands import ActionResult
from jarvis_os.storage import Database, SettingsRepository
from jarvis_os.workflows import WorkflowEngine, WorkflowRepository


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = Database(Path(self.temp.name) / "state.db")
        self.repository = WorkflowRepository(self.database)
        self.executor = Mock()
        self.executor.execute.return_value = ActionResult(True, "opened")
        self.engine = WorkflowEngine(self.repository, self.executor, self.database, SettingsRepository(self.database))

    def tearDown(self):
        self.temp.cleanup()

    def test_voice_workflow_runs_actions(self):
        workflow = self.repository.create(
            "Study", {"type": "voice", "phrase": "start study mode"},
            [{"type": "action", "action": "open_app", "arguments": {"name": "notepad"}}],
        )
        self.assertEqual(self.engine.match_voice("Start study mode").id, workflow.id)
        self.assertTrue(self.engine.run(workflow).success)
        self.executor.execute.assert_called_once()
        self.assertEqual(self.engine.recent_runs()[0]["status"], "completed")

    def test_failed_action_stops_workflow(self):
        self.executor.execute.return_value = ActionResult(False, "blocked")
        workflow = self.repository.create(
            "Unsafe", {"type": "manual"}, [{"action": "delete_path", "risk": "high", "arguments": {"path": "x"}}]
        )
        self.assertFalse(self.engine.run(workflow).success)
        self.assertEqual(self.engine.recent_runs()[0]["status"], "failed")

    def test_condition_can_skip_next_step(self):
        workflow = self.repository.create(
            "Conditional", {"type": "manual"},
            [{"type": "condition", "setting": "privacy_mode", "equals": True}, {"action": "screenshot"}],
        )
        self.assertTrue(self.engine.run(workflow).success)
        self.executor.execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
