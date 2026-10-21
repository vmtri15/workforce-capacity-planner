import asyncio
import hashlib
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ask_the_planner'))
from planner_agent import ask, build_planner
from readonly_sql import ReadOnlySqlRunner, ReadOnlyViolation, check_select_only, connect_read_only
from scoring import frames_match
from scripted_llm import ScriptedLlm
from vanna.capabilities.sql_runner import RunSqlToolArgs


def make_db(folder):
    path = Path(folder) / 'tiny.db'
    with sqlite3.connect(path) as c:
        c.execute('CREATE TABLE sites (site_id TEXT, allocation_share REAL)')
        c.executemany('INSERT INTO sites VALUES (?, ?)', [('joliet', 0.43), ('ohare', 0.42), ('kenosha', 0.15)])
    return path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class ReadOnlyTest(unittest.TestCase):
    def test_only_a_single_select_is_accepted(self):
        for ok in ['SELECT 1', 'select * from sites;', 'WITH x AS (SELECT 1) SELECT * FROM x']:
            check_select_only(ok)
        for bad in ['DELETE FROM sites', 'DROP TABLE sites', 'UPDATE sites SET allocation_share = 1',
                    'INSERT INTO sites VALUES (1, 2)', 'PRAGMA table_info(sites)', 'ATTACH DATABASE "x" AS y',
                    'SELECT 1; DELETE FROM sites', 'WITH x AS (SELECT 1) INSERT INTO sites SELECT * FROM x']:
            with self.assertRaises(ReadOnlyViolation, msg=bad):
                check_select_only(bad)

    def test_runner_reads_and_never_changes_the_file(self):
        with tempfile.TemporaryDirectory() as folder:
            db = make_db(folder)
            before = digest(db)
            runner = ReadOnlySqlRunner(db)
            frame = asyncio.run(runner.run_sql(RunSqlToolArgs(sql='SELECT * FROM sites'), None))
            self.assertEqual(len(frame), 3)
            with self.assertRaises(ReadOnlyViolation):
                asyncio.run(runner.run_sql(RunSqlToolArgs(sql='DELETE FROM sites'), None))
            self.assertEqual(digest(db), before)
            self.assertIsNotNone(runner.log[-1]['error'])

    def test_the_connection_itself_refuses_writes(self):
        with tempfile.TemporaryDirectory() as folder:
            db = make_db(folder)
            connection = connect_read_only(db)
            with self.assertRaises(sqlite3.OperationalError):
                connection.execute('DELETE FROM sites')
            connection.close()


class ScoringTest(unittest.TestCase):
    def test_names_order_and_percent_do_not_matter_but_values_do(self):
        gold = pd.DataFrame({'site': ['joliet', 'ohare'], 'share': [0.43, 0.42]})
        self.assertTrue(frames_match(pd.DataFrame({'pct': [42.0, 43.0], 'name': ['ohare', 'joliet']}), gold, percent_ok=True)[0])
        self.assertFalse(frames_match(pd.DataFrame({'pct': [42.0, 43.0], 'name': ['ohare', 'joliet']}), gold)[0])
        self.assertFalse(frames_match(pd.DataFrame({'site': ['joliet', 'ohare'], 'share': [0.42, 0.43]}), gold)[0])
        self.assertFalse(frames_match(pd.DataFrame({'site': ['joliet'], 'share': [0.43]}), gold)[0])


class AgentTest(unittest.TestCase):
    def run_agent(self, db, use_glossary, sql):
        llm = ScriptedLlm(sql, 'Answer.')
        planner = build_planner(db, use_glossary=use_glossary, llm=llm)
        return asyncio.run(ask(planner, 'question')), llm

    def test_agent_runs_sql_through_the_read_only_runner(self):
        with tempfile.TemporaryDirectory() as folder:
            db = make_db(folder)
            before = digest(db)
            result, _ = self.run_agent(db, True, 'SELECT site_id FROM sites ORDER BY allocation_share DESC LIMIT 1')
            self.assertEqual(result['queries'][0]['result'].iloc[0, 0], 'joliet')
            self.assertEqual(result['answer'], 'Answer.')
            result, _ = self.run_agent(db, True, 'DROP TABLE sites')
            self.assertIn('ReadOnlyViolation', result['queries'][0]['error'])
            self.assertEqual(digest(db), before)
        shutil.rmtree(ROOT / 'ask_the_planner/.run_data', ignore_errors=True)

    def test_the_two_conditions_differ_only_by_the_glossary(self):
        with tempfile.TemporaryDirectory() as folder:
            db = make_db(folder)
            _, without = self.run_agent(db, False, 'SELECT 1')
            _, with_glossary = self.run_agent(db, True, 'SELECT 1')
            a, b = without.system_prompts[0], with_glossary.system_prompts[0]
            self.assertTrue(b.startswith(a))
            self.assertIn('Business glossary', b)
            self.assertNotIn('Business glossary', a)
        shutil.rmtree(ROOT / 'ask_the_planner/.run_data', ignore_errors=True)


    def test_guided_adds_the_base_case_rule_and_views(self):
        with tempfile.TemporaryDirectory() as folder:
            db = make_db(folder)
            with sqlite3.connect(db) as c:
                c.execute("CREATE VIEW base_case_sites AS SELECT * FROM sites")
            llm = ScriptedLlm('SELECT 1', 'Answer.')
            asyncio.run(ask(build_planner(db, use_glossary=True, llm=llm, guided=True), 'question'))
            _, glossary_only = self.run_agent(db, True, 'SELECT 1')
            guided, plain = llm.system_prompts[0], glossary_only.system_prompts[0]
            self.assertIn('base_case_sites', guided)
            self.assertNotIn('base_case_sites', plain)  # the older conditions see the schema they were scored on
            self.assertIn('Never add up rows across runs', guided)
        shutil.rmtree(ROOT / 'ask_the_planner/.run_data', ignore_errors=True)


class FailingLlm(ScriptedLlm):
    async def send_request(self, request):
        raise RuntimeError('400 INVALID_ARGUMENT from the model')


class ErrorCaptureTest(unittest.TestCase):
    def test_a_model_error_is_reported_not_hidden(self):
        with tempfile.TemporaryDirectory() as folder:
            planner = build_planner(make_db(folder), use_glossary=True, llm=FailingLlm('SELECT 1'))
            result = asyncio.run(ask(planner, 'question'))
            self.assertIn('400 INVALID_ARGUMENT', result['error'] or '')
        shutil.rmtree(ROOT / 'ask_the_planner/.run_data', ignore_errors=True)


class GeminiFixTest(unittest.TestCase):
    def test_tool_results_use_a_valid_role_and_keep_the_signature(self):
        from types import SimpleNamespace as NS
        from gemini_fix import FixedGeminiLlmService
        from vanna.core.llm import LlmMessage, LlmRequest
        from vanna.core.user import User
        service = FixedGeminiLlmService(model='test-model', api_key='not-a-real-key')  # no network call is made
        call = NS(name='run_sql', args={'sql': 'SELECT 1'})
        reply = NS(candidates=[NS(content=NS(parts=[NS(text=None, thought=False, function_call=call, thought_signature=b'sig')]))])
        _, tool_calls = service._parse_response(reply)
        second = service._parse_response(reply)[1][0]
        self.assertNotEqual(tool_calls[0].id, second.id)  # ids no longer collide
        request = LlmRequest(user=User(id='t'), messages=[
            LlmMessage(role='user', content='question'),
            LlmMessage(role='assistant', content='', tool_calls=tool_calls),
            LlmMessage(role='tool', content='{"rows": 1}', tool_call_id=tool_calls[0].id)])
        contents, _ = service._build_payload(request)
        self.assertEqual([c.role for c in contents], ['user', 'model', 'user'])
        self.assertEqual(contents[1].parts[0].thought_signature, b'sig')
        self.assertEqual(contents[2].parts[0].function_response.name, 'run_sql')


class EnvFileTest(unittest.TestCase):
    def test_env_file_is_read_and_the_shell_value_wins(self):
        import os
        from planner_agent import load_env_file
        with tempfile.TemporaryDirectory() as folder:
            env = Path(folder) / '.env'
            env.write_text('# comment\nASK_TEST_A="from file"\nexport ASK_TEST_B=file\n')
            os.environ['ASK_TEST_B'] = 'shell'
            try:
                load_env_file(env)
                self.assertEqual(os.environ['ASK_TEST_A'], 'from file')
                self.assertEqual(os.environ['ASK_TEST_B'], 'shell')
            finally:
                os.environ.pop('ASK_TEST_A', None)
                os.environ.pop('ASK_TEST_B', None)


class QuestionSetTest(unittest.TestCase):
    def test_question_set_is_complete(self):
        questions = yaml.safe_load((ROOT / 'ask_the_planner/questions.yaml').read_text())
        self.assertEqual(len(questions), 30)
        self.assertEqual(len({q['id'] for q in questions}), 30)
        answerable = [q for q in questions if q.get('answerable', True)]
        self.assertEqual(len(answerable), 28)
        for q in questions:
            self.assertTrue(q.get('expected'), q['id'])
        for q in answerable:
            self.assertTrue(q['gold_sql'].strip().upper().startswith('SELECT'), q['id'])


if __name__ == '__main__':
    unittest.main()
