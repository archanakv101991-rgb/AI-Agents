"""Tests that run without an API key: a stub client stands in for the LLM."""

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import agent
from database import build_sample_db, run_query


class StubClient:
    """Mimics the parts of anthropic.Anthropic that agent.py uses."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        text = self.replies.pop(0)
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)])


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.repo = agent.load_repository()
        self.db = Path(tempfile.mkdtemp()) / "test.db"
        build_sample_db(self.db)

    def test_every_repository_query_runs(self):
        for q in self.repo:
            with self.subTest(query=q["id"]):
                columns, _ = run_query(q["sql"], db_path=self.db)
                self.assertTrue(columns)

    def test_match_returns_valid_id(self):
        client = StubClient(['{"query_id": "monthly_revenue"}'])
        self.assertEqual(agent.match_query(client, "sales per month?", self.repo), "monthly_revenue")

    def test_match_rejects_unknown_id(self):
        client = StubClient(['{"query_id": "made_up_query"}'])
        self.assertIsNone(agent.match_query(client, "anything", self.repo))

    def test_match_handles_null(self):
        client = StubClient(['{"query_id": null}'])
        self.assertIsNone(agent.match_query(client, "what is the weather?", self.repo))

    def test_answer_question_end_to_end(self):
        client = StubClient([
            '{"query_id": "orders_by_status"}',
            "There are 689 delivered orders.",
        ])
        result = agent.answer_question("How many orders are delivered?", client=client,
                                       repository=self.repo, db_path=self.db)
        self.assertEqual(result.query_id, "orders_by_status")
        self.assertIn("689", result.answer)
        self.assertEqual(result.columns, ["status", "order_count"])

    def test_no_match_skips_database(self):
        client = StubClient(['{"query_id": null}'])
        result = agent.answer_question("Tell me a joke", client=client,
                                       repository=self.repo, db_path=self.db)
        self.assertIsNone(result.query_id)
        self.assertIsNone(result.sql)


class ReadOnlyTests(unittest.TestCase):
    def setUp(self):
        self.db = Path(tempfile.mkdtemp()) / "ro.db"
        build_sample_db(self.db)

    def test_rejects_non_select(self):
        with self.assertRaises(ValueError):
            run_query("DELETE FROM orders", db_path=self.db)

    def test_write_inside_with_is_blocked_by_read_only_mode(self):
        with self.assertRaises(sqlite3.OperationalError):
            run_query("WITH x AS (SELECT 1) DELETE FROM orders", db_path=self.db)

        columns, rows = run_query("SELECT COUNT(*) FROM orders", db_path=self.db)
        self.assertEqual(rows[0][0], 800)


if __name__ == "__main__":
    unittest.main()
