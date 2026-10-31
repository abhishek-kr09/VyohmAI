import unittest

from app.services.chat_service import _bulletize, _clean_answer


class AnswerFormatTests(unittest.TestCase):
    def test_inline_numbered_list_becomes_bullets_without_segment_refs(self):
        text = (
            "You promised to: 1) fill in the gaps for John (segment 14\u201315); "
            "2) talk to John today (segment 18\u201319); and 3) try a pancake breakfast (segment 5\u20136)."
        )
        result = _clean_answer(text)
        self.assertEqual(
            result.splitlines(),
            [
                "You promised to:",
                "- Fill in the gaps for John",
                "- Talk to John today",
                "- Try a pancake breakfast",
            ],
        )

    def test_flat_promise_sentence_becomes_bullets(self):
        result = _bulletize(
            "You promised to talk to John today, help with his family's childcare needs, "
            "and find free or low-cost resources for him."
        )
        lines = result.splitlines()
        self.assertEqual(lines[0], "You promised:")
        self.assertEqual(len(lines), 4)
        self.assertTrue(all(line.startswith("- ") for line in lines[1:]))

    def test_short_answers_and_existing_bullets_are_unchanged(self):
        self.assertEqual(_bulletize("Rikado Elevator"), "Rikado Elevator")
        bulleted = "Here are your tasks:\n- One\n- Two"
        self.assertEqual(_bulletize(_clean_answer(bulleted)), bulleted)

    def test_evidence_markers_are_removed(self):
        self.assertEqual(_clean_answer("It was Friday [3] and Monday [1, 2]."), "It was Friday and Monday.")


if __name__ == "__main__":
    unittest.main()
