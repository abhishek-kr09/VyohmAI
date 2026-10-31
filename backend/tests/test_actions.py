import os
import tempfile
import unittest
from datetime import datetime, timezone
from unittest import mock

from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from app import models  # noqa: F401
from app.database import Base, SessionLocal, engine as default_engine
from app.main import app
from app.models import ActionItem, CalendarEvent, EmailDraft, Recording
from app.services import action_agent_service
from app.services.action_agent_service import AgentPlan


class ActionAgentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_dir = tempfile.TemporaryDirectory()
        cls.engine = create_engine(
            f"sqlite:///{os.path.join(cls.db_dir.name, 'test_actions.db')}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(bind=cls.engine)
        SessionLocal.configure(bind=cls.engine)
        cls.client = TestClient(app)
        with SessionLocal() as db:
            recording = Recording(
                device_id="rec-demo",
                filename="rec_01_vendor_call.wav",
                file_path="missing.wav",
                recorded_at=datetime(2026, 11, 3, 10, 5, tzinfo=timezone.utc),
                duration_ms=60000,
                status="completed",
            )
            db.add(recording)
            db.flush()
            item = ActionItem(recording_id=recording.id, person="Priya", task="Send revised quote")
            db.add(item)
            db.commit()
            cls.recording_id = recording.id
            cls.item_id = item.id

    @classmethod
    def tearDownClass(cls):
        SessionLocal.configure(bind=default_engine)
        cls.engine.dispose()
        cls.db_dir.cleanup()

    def _counts(self):
        with SessionLocal() as db:
            return db.query(CalendarEvent).count(), db.query(EmailDraft).count()

    def test_agent_plans_calendar_without_writing_until_confirmed(self):
        plan = AgentPlan(
            action_type="create_calendar",
            title="Vendor follow-up",
            start_time=datetime(2026, 11, 5, 10, 0, tzinfo=timezone.utc),
        )
        before = self._counts()
        with mock.patch.object(action_agent_service, "_plan", return_value=plan):
            response = self.client.post(
                "/actions/agent",
                json={"instruction": "Schedule the vendor follow-up", "recording_id": self.recording_id},
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["requires_confirmation"])
        self.assertEqual(self._counts(), before)

        confirm = self.client.post(
            "/actions/agent/confirm",
            json={"plan": response.json()["plan"], "recording_id": self.recording_id},
        )
        self.assertEqual(confirm.status_code, 200)
        self.assertEqual(self._counts()[0], before[0] + 1)
        events = self.client.get("/actions/calendar-events").json()
        self.assertTrue(any(event["title"] == "Vendor follow-up" for event in events))

    def test_email_is_saved_as_draft_only(self):
        plan = {
            "action_type": "create_email",
            "recipient": "priya@example.com",
            "subject": "Follow-up",
            "body": "Thanks for the call.",
        }
        response = self.client.post(
            "/actions/agent/confirm", json={"plan": plan, "recording_id": self.recording_id}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["email_draft"]["status"], "draft")

    def test_email_without_address_is_rejected(self):
        plan = {"action_type": "create_email", "recipient": "Priya", "subject": "Hi", "body": "Body"}
        response = self.client.post("/actions/agent/confirm", json={"plan": plan})
        self.assertEqual(response.status_code, 422)

    def test_action_item_run_requires_confirmation(self):
        plan = AgentPlan(action_type="complete_action", action_item_id=self.item_id)
        with mock.patch.object(action_agent_service, "_plan", return_value=plan):
            response = self.client.post(f"/actions/items/{self.item_id}/run")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["requires_confirmation"])
        with SessionLocal() as db:
            self.assertEqual(db.get(ActionItem, self.item_id).status, "pending")


if __name__ == "__main__":
    unittest.main()
