import unittest

from techdigest.feedback import summary, weekly_status


def vote(day, v, title="T", source="simon"):
    return {"digest": day, "harvested": day, "issue": 1, "kind": "vote", "vote": v, "id": "x" * 10,
            "title": title, "source": source}


class WeeklyStatusTest(unittest.TestCase):
    MONDAY, TUESDAY = "2026-10-26", "2026-10-27"

    def test_due_on_monday_with_new_feedback(self):
        due, _ = weekly_status(self.MONDAY, {}, [vote("2026-10-24", 1)])
        self.assertTrue(due)

    def test_not_due_on_other_days(self):
        self.assertFalse(weekly_status(self.TUESDAY, {}, [vote("2026-10-24", 1)])[0])

    def test_not_due_without_new_feedback(self):
        lines = [vote("2026-10-18", 1)]
        self.assertFalse(weekly_status(self.MONDAY, {"last_proposal": "2026-10-19"}, lines)[0])
        self.assertFalse(weekly_status(self.MONDAY, {}, [{"digest": "2026-10-24", "kind": "harvested"}])[0])

    def test_not_twice_in_a_week(self):
        self.assertFalse(weekly_status(self.MONDAY, {"last_proposal": "2026-10-24"},
                                       [vote("2026-10-25", 1)])[0])

    def test_feedback_harvested_on_review_day_counts_next_week(self):
        # Monday's run proposes before delivery; Monday's delivery then harvests Sunday's issue.
        lines = [{**vote("2026-10-25", 1), "harvested": "2026-10-26"}]
        self.assertTrue(weekly_status("2026-11-02", {"last_proposal": "2026-10-26"}, lines)[0])

    def test_catches_up_after_a_missed_monday(self):
        self.assertTrue(weekly_status(self.TUESDAY, {"last_proposal": "2026-10-19"},
                                      [vote("2026-10-25", -1)])[0])


class SummaryTest(unittest.TestCase):
    def test_summary_groups_votes_and_quotes_comments(self):
        lines = [vote("2026-10-20", 1, "Harness post"), vote("2026-10-21", -1, "Funding news", "hn-front"),
                 {"digest": "2026-10-21", "kind": "comment", "text": "More\nTCG policy please"},
                 {"digest": "2026-10-21", "kind": "reaction", "vote": 1},
                 {"digest": "2026-10-21", "kind": "harvested"},
                 vote("2026-08-01", 1, "Too old")]
        s = summary(lines, "2026-10-23", 30)
        self.assertIn("(4 signals)", s)
        self.assertIn("- simon: 1/0", s)
        self.assertIn("Liked:\n- Harness post (simon, 2026-10-20)", s)
        self.assertIn("Disliked:\n- Funding news (hn-front, 2026-10-21)", s)
        self.assertIn("- 2026-10-21: More TCG policy please", s)
        self.assertNotIn("Too old", s)

    def test_no_feedback(self):
        self.assertEqual(summary([], "2026-10-23"), "No feedback in the last 30 days.")


if __name__ == "__main__":
    unittest.main()
