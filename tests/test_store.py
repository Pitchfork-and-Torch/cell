import unittest

import harness  # noqa: F401
from cell.models import Message
from cell.store import bump_usage, connect, known_sids, list_local, upsert_message, usage_today
from harness import FROM_N, TO_N, CellHomeCase


class TestStore(CellHomeCase):
    def test_upsert_and_thread_filter(self):
        con = connect(self.home / "state.sqlite")
        upsert_message(
            con,
            Message(
                sid="SMin",
                direction="inbound",
                from_n=TO_N,
                to=FROM_N,
                body="hi",
                status="received",
                created="2026-01-01T00:00:00Z",
            ),
            source="local",
        )
        upsert_message(
            con,
            Message(
                sid="SMout",
                direction="outbound",
                from_n=FROM_N,
                to=TO_N,
                body="yo",
                status="sent",
                created="2026-01-01T00:01:00Z",
            ),
            source="outbound",
        )
        upsert_message(
            con,
            Message(
                sid="SMother",
                direction="inbound",
                from_n="+15125550999",
                to=FROM_N,
                body="nope",
                status="received",
                created="2026-01-01T00:02:00Z",
            ),
            source="local",
        )
        all_msgs = list_local(con, limit=20)
        self.assertEqual(len(all_msgs), 3)
        thread = list_local(con, limit=20, with_n=TO_N)
        bodies = {m.body for m in thread}
        self.assertEqual(bodies, {"hi", "yo"})
        self.assertEqual(known_sids(con), {"SMin", "SMout", "SMother"})
        con.close()

    def test_usage_counters(self):
        con = connect(self.home / "state.sqlite")
        self.assertEqual(usage_today(con, "sms"), 0)
        self.assertEqual(bump_usage(con, "sms"), 1)
        self.assertEqual(bump_usage(con, "sms"), 2)
        self.assertEqual(usage_today(con, "sms"), 2)
        self.assertEqual(usage_today(con, "call"), 0)
        con.close()


if __name__ == "__main__":
    unittest.main()
