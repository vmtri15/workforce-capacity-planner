"""Serve the read-only planning dashboard on localhost."""
import argparse
import asyncio
import csv
import hashlib
import json
import os
import sqlite3
import sys
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASK_DIR = ROOT / 'ask_the_planner'
_ask = {'planner': None, 'lock': threading.Lock()}


def read_csv(name):
    path = ROOT / 'tableau' / 'data' / name
    with path.open(newline='', encoding='utf-8') as handle:
        return list(csv.DictReader(handle))


def portfolio_snapshot():
    path = ROOT / 'dashboard/data/portfolio.json'
    return json.loads(path.read_text(encoding='utf-8'))


def network_capacity_snapshot():
    path = ROOT / 'data/processed/network_capacity_2023.json'
    return json.loads(path.read_text(encoding='utf-8'))


def decision_answer_snapshot():
    path = ROOT / 'data/processed/decision_answer.json'
    return json.loads(path.read_text(encoding='utf-8'))


def build_explanation_prompt(payload):
    audience = payload.get('audience', 'operations manager')
    decision = payload.get('decision')
    if audience not in {'operations manager', 'executive'} or not isinstance(decision, dict):
        raise ValueError('A valid audience and decision object are required.')
    return (
        'Explain the following warehouse-capacity recommendation to an '
        f'{audience}. Use only the supplied facts. Write 2 short paragraphs followed '
        'by exactly 3 bullets: decision, evidence, and limitation. Clearly distinguish '
        'observed demand from modeled assumptions. Do not invent savings, actual '
        'headcount, operational performance, or guaranteed service.\n\n'
        f'DECISION DATA:\n{json.dumps(decision, separators=(",", ":"), sort_keys=True)}'
    )


def request_ai_explanation(payload):
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        raise RuntimeError('OPENAI_API_KEY is not configured on the server.')
    body = json.dumps({
        'model': os.environ.get('OPENAI_MODEL', 'gpt-5-mini'),
        'input': build_explanation_prompt(payload),
        'max_output_tokens': 500,
        'store': False,
    }).encode()
    request = urllib.request.Request(
        'https://api.openai.com/v1/responses', data=body, method='POST',
        headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.loads(response.read())
    parts = [content.get('text', '') for item in result.get('output', [])
             for content in item.get('content', []) if content.get('type') == 'output_text']
    explanation = ''.join(parts).strip()
    if not explanation:
        raise RuntimeError('OpenAI returned no explanation text.')
    return {'explanation': explanation, 'model': result.get('model', 'OpenAI model')}


def snapshot():
    database = ROOT / 'data/workforce_planner.db'
    with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as conn:
        conn.row_factory = sqlite3.Row
        tables = ['sites', 'roles', 'planning_runs', 'staffing_plans',
                  'modeled_daily_workload', 'daily_capacity_results',
                  'scenario_assumptions', 'source_registry',
                  'data_quality_results', 'planning_quality_results']
        data = {table: [dict(row) for row in conn.execute('SELECT * FROM ' + table)]
                for table in tables}
    optimizer = json.loads((ROOT / 'data/processed/network_optimization_results.json').read_text())
    data['optimizer'] = optimizer
    data['optimizer_current'] = hashlib.sha256(database.read_bytes()).hexdigest() == optimizer['database_sha256']
    packing_path = ROOT / 'data/processed/packing_optimization_results.json'
    if packing_path.exists():
        data['packing'] = json.loads(packing_path.read_text())
        data['packing_current'] = all((ROOT / path).exists() and
            hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
            for path, digest in data['packing']['input_hashes'].items())
    return data


def ask_database():
    """The database Ask the Planner reads. The evaluation copy has the planning results; ASK_DB overrides."""
    if os.environ.get('ASK_DB'):
        return Path(os.environ['ASK_DB'])
    copy = ASK_DIR / 'eval_db/planner_for_eval.db'
    return copy if copy.exists() else ROOT / 'data/workforce_planner.db'


def ask_status():
    if str(ASK_DIR) not in sys.path:
        sys.path.insert(0, str(ASK_DIR))
    try:
        from planner_agent import DEFAULT_MODEL, load_env_file
    except ImportError:
        return {'available': False, 'reason': 'Vanna is not installed here. Start the server with .venv/bin/python.'}
    load_env_file()
    if not (os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')):
        return {'available': False, 'reason': 'No Gemini key. Add GEMINI_API_KEY to the .env file.'}
    database = ask_database()
    if not database.exists():
        return {'available': False, 'reason': f'{database.name} not found. Run ask_the_planner/build_eval_db.py.'}
    return {'available': True, 'model': os.environ.get('GEMINI_MODEL', DEFAULT_MODEL), 'database': database.name}


def run_question(question):
    """Answer one plain English question, read only. Returns the answer and every SQL statement run."""
    if not isinstance(question, str) or not 3 <= len(question.strip()) <= 500:
        raise ValueError('Ask a question between 3 and 500 characters.')
    status = ask_status()
    if not status['available']:
        raise RuntimeError(status['reason'])
    from planner_agent import ask, build_planner
    with _ask['lock']:  # one question at a time; the agent keeps a log of the SQL it runs
        if _ask['planner'] is None:
            _ask['planner'] = build_planner(ask_database(), use_glossary=True)
        result = asyncio.run(ask(_ask['planner'], question.strip()))
    queries = []
    for q in result['queries']:
        table = json.loads(q['result'].head(50).to_json(orient='split', index=False)) if q['result'] is not None else None
        queries.append({'sql': q['sql'], 'error': q['error'], 'columns': table['columns'] if table else [],
                        'rows': table['data'] if table else []})
    return {'answer': result['answer'], 'error': result['error'], 'queries': queries,
            'model': status['model'], 'database': status['database']}


class Handler(BaseHTTPRequestHandler):
    def send_json(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path.split('?')[0] == '/api/ask':
            self.answer_question()
            return
        if self.path.split('?')[0] != '/api/explain-recommendation':
            self.send_error(404)
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if length < 1 or length > 16384:
                raise ValueError('Request body must be between 1 byte and 16 KB.')
            result = request_ai_explanation(json.loads(self.rfile.read(length)))
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json(400, {'error': str(error)})
            return
        except RuntimeError as error:
            self.send_json(503, {'error': str(error)})
            return
        except urllib.error.HTTPError as error:
            self.send_json(502, {'error': f'OpenAI request failed with status {error.code}.'})
            return
        except (urllib.error.URLError, TimeoutError):
            self.send_json(502, {'error': 'OpenAI could not be reached. Try again later.'})
            return
        self.send_json(200, result)

    def answer_question(self):
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if length < 1 or length > 4096:
                raise ValueError('Request body must be between 1 byte and 4 KB.')
            result = run_question(json.loads(self.rfile.read(length)).get('question'))
        except (ValueError, json.JSONDecodeError, AttributeError) as error:
            self.send_json(400, {'error': str(error)})
            return
        except RuntimeError as error:
            self.send_json(503, {'error': str(error)})
            return
        except Exception as error:  # the model or API failed; report it instead of crashing the server
            self.send_json(502, {'error': f'The question could not be answered: {type(error).__name__}.'})
            return
        self.send_json(200, result)

    def do_GET(self):
        path = self.path.split('?')[0]
        if path == '/api/data':
            try:
                body = json.dumps(snapshot()).encode()
            except (OSError, sqlite3.Error, ValueError, KeyError):
                self.send_error(503, 'Planning data unavailable. Check the local database and saved results.')
                return
            content_type = 'application/json'
        elif path == '/api/portfolio':
            try:
                body = json.dumps(portfolio_snapshot()).encode()
            except (OSError, ValueError):
                self.send_error(503, 'Portfolio data unavailable. Rebuild the Tableau exports, then reload.')
                return
            content_type = 'application/json'
        elif path == '/api/network-capacity':
            try:
                body = json.dumps(network_capacity_snapshot()).encode()
            except (OSError, ValueError):
                self.send_error(503, 'Network capacity data unavailable. Rebuild the 2023 replay, then reload.')
                return
            content_type = 'application/json'
        elif path in ('/api/decision-answer', '/data/decision_answer.json'):
            try:
                body = json.dumps(decision_answer_snapshot()).encode()
            except (OSError, ValueError):
                self.send_error(503, 'Decision answer unavailable. Rebuild the decision artifact, then reload.')
                return
            content_type = 'application/json'
        elif path == '/api/ask-status':
            self.send_json(200, ask_status())
            return
        elif path == '/api/ai-status':
            self.send_json(200, {'available': bool(os.environ.get('OPENAI_API_KEY')),
                                 'model': os.environ.get('OPENAI_MODEL', 'gpt-5-mini')})
            return
        elif path in ('/', '/app.js', '/portfolio.js', '/style.css', '/published.css', '/portfolio.css'):
            name = 'index.html' if path == '/' else path[1:]
            body = (ROOT / 'dashboard' / name).read_bytes()
            content_type = {'index.html': 'text/html', 'app.js': 'text/javascript',
                            'portfolio.js': 'text/javascript', 'style.css': 'text/css',
                            'published.css': 'text/css', 'portfolio.css': 'text/css'}[name]
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Type', content_type + '; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    print(f'Dashboard: http://127.0.0.1:{args.port}', flush=True)
    server.serve_forever()
