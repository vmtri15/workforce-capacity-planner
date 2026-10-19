import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'ask_the_planner'))
import serve_dashboard as server
from planner_agent import build_planner
from scripted_llm import ScriptedLlm


class AskEndpointTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.db = Path(self.folder) / 'tiny.db'
        with sqlite3.connect(self.db) as c:
            c.execute('CREATE TABLE sites (site_id TEXT, allocation_share REAL)')
            c.executemany('INSERT INTO sites VALUES (?, ?)', [('joliet', 0.43), ('ohare', 0.42)])
        self.available = {'available': True, 'model': 'test', 'database': 'tiny.db'}

    def tearDown(self):
        server._ask['planner'] = None
        shutil.rmtree(self.folder, ignore_errors=True)
        shutil.rmtree(ROOT / 'ask_the_planner/.run_data', ignore_errors=True)

    def test_question_length_is_checked(self):
        for bad in ['', 'hi', 'x' * 501, None, 5]:
            with self.assertRaises(ValueError):
                server.run_question(bad)

    def test_unavailable_setup_gives_a_clear_reason(self):
        with mock.patch.object(server, 'ask_status', return_value={'available': False, 'reason': 'No Gemini key.'}):
            with self.assertRaisesRegex(RuntimeError, 'No Gemini key'):
                server.run_question('Which site is largest?')

    def test_answer_and_sql_come_back_as_json_ready_values(self):
        server._ask['planner'] = build_planner(self.db, llm=ScriptedLlm(
            'SELECT site_id, allocation_share FROM sites ORDER BY allocation_share DESC LIMIT 1', 'Joliet, 43%.'))
        with mock.patch.object(server, 'ask_status', return_value=self.available):
            result = server.run_question('Which site is largest?')
        self.assertEqual(result['answer'], 'Joliet, 43%.')
        self.assertEqual(result['queries'][0]['columns'], ['site_id', 'allocation_share'])
        self.assertEqual(result['queries'][0]['rows'], [['joliet', 0.43]])

    def test_a_write_attempt_is_rejected_and_reported(self):
        server._ask['planner'] = build_planner(self.db, llm=ScriptedLlm('DELETE FROM sites', 'Done.'))
        with mock.patch.object(server, 'ask_status', return_value=self.available):
            result = server.run_question('Delete the sites')
        self.assertIn('ReadOnlyViolation', result['queries'][0]['error'])
        with sqlite3.connect(self.db) as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM sites').fetchone()[0], 2)


if __name__ == '__main__':
    unittest.main()
