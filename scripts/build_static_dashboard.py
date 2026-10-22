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
FORECAST = ROOT / 'data' / 'processed' / 'demand_forecast'
MIDDLE_MILE = ROOT / 'middle_mile' / 'connected' / 'results'
ASK_RESULTS = ROOT / 'ask_the_planner' / 'results' / 'gemini-3.5-flash-lite'  # the latest full run of all three conditions
STORY_DESTINATION = ROOT / 'dashboard' / 'data' / 'story.json'
ASK_EXAMPLES = ['Q01', 'Q07', 'Q12', 'Q15', 'Q20', 'Q30']  # a spread of question types shown on the public site
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


def read_any_csv(path):
    with path.open(newline='', encoding='utf-8') as handle:
        return list(csv.DictReader(handle))


def ask_story():
    """Accuracy and a few saved answers from the evaluation, so the public site can show them without a key."""
    summary = json.loads((ASK_RESULTS / 'summary.json').read_text(encoding='utf-8'))
    records = [json.loads(line) for line in (ASK_RESULTS / 'transcript.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    best = 'guided' if 'guided' in summary['accuracy_answerable'] else 'glossary'
    examples = []
    for question_id in ASK_EXAMPLES:
        record = next((r for r in records if r['id'] == question_id and r['condition'] == best and r['passed']), None)
        if record:
            examples.append({'question': record['question'], 'answer': record['answer'], 'sql': record['final_sql']})
    return {'model': summary['models'][-1], 'best_condition': best,
            'accuracy': summary['accuracy_answerable'], 'examples': examples}


def fred_story():
    """FRED series without their raw values, plus the demand lead check."""
    fred = json.loads((ROOT / 'data/processed/fred_benchmarks.json').read_text(encoding='utf-8'))
    return dict(series={k: {f: v for f, v in s.items() if f != 'values'} for k, s in fred['series'].items()},
                demand_vs_shoe_stores=fred['demand_vs_shoe_stores'])


def story():
    """The three part series in one bundle: forecast, staffing link and middle mile."""
    return {
        'forecast': {
            'summary': json.loads((FORECAST / 'summary.json').read_text(encoding='utf-8')),
            'model_scores': read_any_csv(FORECAST / 'model_scores.csv'),
            'staffing_link': read_any_csv(FORECAST / 'staffing_link_summary.csv'),
            'latest': read_any_csv(FORECAST / 'latest_forecast.csv'),
        },
        'middle_mile': {
            'summary': json.loads((MIDDLE_MILE / 'summary.json').read_text(encoding='utf-8')),
            'at_risk_trucks': read_any_csv(MIDDLE_MILE / 'at_risk_trucks.csv'),
            'routes': read_any_csv(MIDDLE_MILE / 'routes.csv'),
            'network': {key: value for key, value in json.loads((MIDDLE_MILE.parent / 'config.json').read_text(encoding='utf-8')).items()
                        if key in ('sites', 'sort_centers', 'stations')},
        },
        'ask': ask_story(),
        'checks': {
            'bls': json.loads((ROOT / 'data/processed/bls_2023_benchmarks.json').read_text(encoding='utf-8'))['checks'],
            'road_check': read_any_csv(MIDDLE_MILE / 'road_check.csv'),
            'fred': fred_story(),
            'real_cost': read_any_csv(ROOT / 'data/processed/real_cost_check.csv'),
        },
        'inventory': json.loads((ROOT / 'inventory/results/summary.json').read_text(encoding='utf-8')),
        'last_mile': {
            'summary': json.loads((ROOT / 'last_mile/results/summary.json').read_text(encoding='utf-8')),
            'by_station': read_any_csv(ROOT / 'last_mile/results/fleet_by_station.csv'),
        },
    }


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
    STORY_DESTINATION.write_text(json.dumps(story(), separators=(',', ':')), encoding='utf-8')
    print(f'Wrote {DESTINATION.relative_to(ROOT)} with '
          f'{len(payload["demand_daily"]):,} demand rows and '
          f'{len(payload["scenario_results"]):,} scenario rows.')


if __name__ == '__main__':
    main()
