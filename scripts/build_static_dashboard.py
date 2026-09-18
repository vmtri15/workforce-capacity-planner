"""Build the API-free data bundle used by the public portfolio dashboard."""
import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'tableau' / 'data'
DESTINATION = ROOT / 'dashboard' / 'data' / 'portfolio.json'
NETWORK_SOURCE = ROOT / 'data' / 'processed' / 'network_capacity_2023.json'
NETWORK_DESTINATION = ROOT / 'dashboard' / 'data' / 'network_capacity_2023.json'
DECISION_SOURCE = ROOT / 'data' / 'processed' / 'decision_answer.json'
DECISION_DESTINATION = ROOT / 'dashboard' / 'data' / 'decision_answer.json'
EXPLORATORY_SOURCE = (
    ROOT / 'data' / 'processed' / 'recommendation_validation'
    / 'exploratory_replacement_cases.csv'
)


def read_csv(name):
    with (SOURCE / name).open(newline='', encoding='utf-8') as handle:
        return list(csv.DictReader(handle))


def read_exploratory_scenarios():
    with EXPLORATORY_SOURCE.open(newline='', encoding='utf-8') as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        row['case_key'] = '|'.join([
            row['period'], row['policy'], row['basis'], row['rate'],
            row['absent'], row['lead_days'],
        ])
        row['demand_start'] = '2023-08-21'
        row['demand_end'] = '2023-10-19'
        row['cost_end'] = '2023-11-16'
        row['target_share'] = '0.95'
        row['evidence'] = 'Post-hoc exploratory later-period policy search'
    return rows


def main():
    scenario_results = read_csv('scenario_results.csv')
    scenario_results.extend(read_exploratory_scenarios())
    payload = {
        'demand_daily': read_csv('demand_daily.csv'),
        'scenario_results': scenario_results,
        'policies': read_csv('policies.csv'),
        'price_sensitivity': read_csv('price_sensitivity.csv'),
    }
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    DESTINATION.write_text(json.dumps(payload, separators=(',', ':')), encoding='utf-8')
    network = json.loads(NETWORK_SOURCE.read_text(encoding='utf-8'))
    NETWORK_DESTINATION.write_text(json.dumps(network, separators=(',', ':')), encoding='utf-8')
    decision = json.loads(DECISION_SOURCE.read_text(encoding='utf-8'))
    DECISION_DESTINATION.write_text(json.dumps(decision, separators=(',', ':')), encoding='utf-8')
    print(f'Wrote {DESTINATION.relative_to(ROOT)} with '
          f'{len(payload["demand_daily"]):,} demand rows and '
          f'{len(payload["scenario_results"]):,} scenario rows.')


if __name__ == '__main__':
    main()
