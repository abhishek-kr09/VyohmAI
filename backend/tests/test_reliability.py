import asyncio
import tempfile
import unittest
import wave
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException

from app.routes.upload import _read_wav, _validate_metadata
from app.services.chat_service import answer_question


class ReliabilityTests(unittest.TestCase):
    def test_upload_metadata_rejects_timezone_less_timestamp(self):
        with self.assertRaises(HTTPException) as context:
            _validate_metadata("device-1", datetime(2026, 11, 1), 1000, None)
        self.assertEqual(context.exception.status_code, 422)

    def test_upload_metadata_rejects_invalid_battery(self):
        with self.assertRaises(HTTPException):
            _validate_metadata(
                "device-1",
                datetime.fromisoformat("2026-11-01T10:00:00+05:30"),
                1000,
                101,
            )

    def test_valid_wav_is_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.wav"
            with wave.open(str(path), "wb") as audio:
                audio.setnchannels(1)
                audio.setsampwidth(2)
                audio.setframerate(16000)
                audio.writeframes(b"\x00\x00" * 100)

            class Upload:
                filename = path.name
                content_type = "audio/wav"

                async def read(self, _limit):
                    return path.read_bytes()

            data, name = asyncio.run(_read_wav(Upload()))
            self.assertEqual(name, "sample.wav")
            self.assertTrue(data.startswith(b"RIFF"))

    def test_unknown_chat_question_is_honest(self):
        answer, evidence = answer_question("What happened in an unrelated xyzzy conversation?")
        self.assertFalse(evidence)
        self.assertIn("not provide enough evidence", answer)


if __name__ == "__main__":
    unittest.main()
