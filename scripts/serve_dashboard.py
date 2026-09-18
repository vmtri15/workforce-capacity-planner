"""Serve the read-only planning dashboard on localhost."""
import argparse
import csv
import hashlib
import json
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


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


class Handler(BaseHTTPRequestHandler):
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
