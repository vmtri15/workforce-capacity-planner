"""Synthesize the project's evidence into a direct, auditable decision answer."""
from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NETWORK = ROOT / "data/processed/network_capacity_2023.json"
VALIDATION = ROOT / "data/processed/recommendation_validation/summary.json"
REPLACEMENTS = ROOT / "data/processed/recommendation_validation/exploratory_replacement_cases.csv"
QWI = ROOT / "data/processed/qwi_2021q1_latest_naics493.csv"
SOTO = ROOT / "data/processed/soto_pinedo_profile.json"
JSON_OUTPUT = ROOT / "data/processed/decision_answer.json"
MARKDOWN_OUTPUT = ROOT / "DECISION_ANSWER.md"


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as source:
        return list(csv.DictReader(source))


def policy_metrics(rows: list[dict], policy: str) -> dict:
    selected = [row for row in rows if row["policy"] == policy]
    base = next(row for row in selected if row["basis"] == "retained"
                and float(row["rate"]) == 40 and int(row["absent"]) == 0
                and int(row["lead_days"]) == 1)
    worst = min(selected, key=lambda row: float(row["on_time_unit_share"]))
    return {
        "policy": policy,
        "scheduled_workers": int(base["workers"]),
        "overtime_limit_hours": int(policy.split("_ot")[1].split("_")[0]),
        "temporary_worker_limit": int(policy.rsplit("temps", 1)[1]),
        "base_on_time_share": round(float(base["on_time_unit_share"]), 6),
        "base_modeled_cost": round(float(base["total_cost"]), 2),
        "base_peak_backlog": int(base["peak_backlog"]),
        "stress_cases_passed": sum(row["target_met"] == "True" for row in selected),
        "stress_cases_tested": len(selected),
        "worst_on_time_share": round(float(worst["on_time_unit_share"]), 6),
        "worst_modeled_cost": round(max(float(row["total_cost"]) for row in selected), 2),
        "evidence_status": "Exploratory later-period search; not an untouched holdout result",
    }


def qwi_context() -> dict:
    rows = read_csv(QWI)
    quarters = sorted({row["quarter"] for row in rows}, reverse=True)
    complete_quarter = next(quarter for quarter in quarters if all(
        all(row[field] for field in ("beginning_employment", "end_employment", "hires", "separations", "stable_employment"))
        for row in rows if row["quarter"] == quarter
    ))
    current = [row for row in rows if row["quarter"] == complete_quarter]
    by_county = {row["county_fips"]: row for row in current}

    def combine(counties):
        selected = [by_county[county] for county in counties]
        return {
            "beginning_employment": sum(int(row["beginning_employment"]) for row in selected),
            "end_employment": sum(int(row["end_employment"]) for row in selected),
            "hires": sum(int(row["hires"]) for row in selected),
            "separations": sum(int(row["separations"]) for row in selected),
        }

    return {
        "latest_api_quarter": quarters[0],
        "latest_complete_quarter": complete_quarter,
        "latest_quarter_limit": "The latest API quarter has publication-lag blanks; labor-flow comparisons use the latest complete quarter.",
        "sites": {
            "joliet": combine(["197"]),
            "ohare": combine(["031", "043"]),
            "kenosha": combine(["059"]),
        },
        "interpretation": "County-level NAICS 493 context only; not facility staffing, applicant supply, or time-to-hire.",
    }


def build() -> dict:
    network = json.loads(NETWORK.read_text(encoding="utf-8"))
    validation = json.loads(VALIDATION.read_text(encoding="utf-8"))
    replacement_rows = read_csv(REPLACEMENTS)
    soto = json.loads(SOTO.read_text(encoding="utf-8"))
    cases = {case["productivity_case"]: case for case in network["cases"]}
    sites = []
    for base in cases["base"]["site_summary"]:
        low = next(row for row in cases["low"]["site_summary"] if row["site_id"] == base["site_id"])
        high = next(row for row in cases["high"]["site_summary"] if row["site_id"] == base["site_id"])
        sites.append({
            "site_id": base["site_id"],
            "site_name": base["site_name"],
            "modeled_positions": base["scheduled_headcount"],
            "base_gap_hours": base["gap_hours"],
            "low_gap_hours": low["gap_hours"],
            "high_gap_hours": high["gap_hours"],
            "base_target_met_role_day_share": base["target_met_share"],
            "answer": "Mostly, but not completely" if base["gap_hours"] > 0 else "Yes under the modeled base case",
            "reason": "The modeled site clears the 95% daily coverage threshold on most direct-role days, but still records positive shortfall hours.",
        })
    affordable = policy_metrics(replacement_rows, validation["exploratory_replacement"]["base"])
    resilient = policy_metrics(replacement_rows, validation["exploratory_replacement"]["robust"])
    return {
        "question": "Can each location complete the expected workload with the available workforce, and what is the least risky and most affordable action if it cannot?",
        "answer": "Under the modeled staffing plan, every site covers at least 95% of workload on most direct-role days, but no site eliminates shortfall hours across the recorded 2023 workload. Use six workers with capped overtime as the affordable base-case response; use ten workers with capped overtime when protection across every listed productivity and absence stress is required.",
        "site_results": sites,
        "actions": {
            "affordable_base_case": affordable,
            "lowest_risk_tested": resilient,
            "decision_rule": "Choose the affordable action only when productivity is near 40 units per productive hour and attendance is stable. Escalate to the stress-resistant action when low productivity or two-worker absence is plausible.",
        },
        "frozen_policy_validation": validation["evaluation"],
        "labor_market_context": qwi_context(),
        "external_benchmark": {
            "source": "Soto-Pinedo 2025 preparation records",
            "valid_intervals": soto["preparation_2025"]["valid_preparation_intervals"],
            "median_cycle_hours": soto["preparation_2025"]["preparation_cycle_hours"]["median"],
            "p95_cycle_hours": soto["preparation_2025"]["preparation_cycle_hours"]["p95"],
            "use": "Tail-risk context only; excluded from U.S. staffing calculations pending license and provenance confirmation.",
        },
        "evidence_boundary": [
            "Observed: retained 2023 order dates, units, and order mix.",
            "Modeled: site allocation, staffing, productivity, attendance, completion timing, service, and cost.",
            "External context: QWI labor flows and Soto-Pinedo process timing do not describe the modeled facilities.",
            "Therefore the result is a conditional planning answer, not proof of actual staffing sufficiency or guaranteed savings.",
        ],
    }


def markdown(result: dict) -> str:
    site_rows = "\n".join(
        f'| {site["site_name"]} | {site["answer"]} | {site["modeled_positions"]} | '
        f'{site["base_gap_hours"]:.1f} h | {100 * site["base_target_met_role_day_share"]:.1f}% |'
        for site in result["site_results"]
    )
    affordable = result["actions"]["affordable_base_case"]
    resilient = result["actions"]["lowest_risk_tested"]
    return f'''# Final Decision Answer

## Question

{result["question"]}

## Answer

{result["answer"]}

| Modeled location | Capacity answer | Fixed positions | Base shortfall | Direct-role days meeting target |
| --- | --- | ---: | ---: | ---: |
{site_rows}

## Actions

- **Affordable base case:** {affordable["scheduled_workers"]} workers with up to {affordable["overtime_limit_hours"]} overtime hours. It reaches {100 * affordable["base_on_time_share"]:.1f}% on-time units in the later-period base case at a modeled cost of ${affordable["base_modeled_cost"]:,.0f}, but passes only {affordable["stress_cases_passed"]}/{affordable["stress_cases_tested"]} listed stress cases.
- **Lowest-risk tested action:** {resilient["scheduled_workers"]} workers with up to {resilient["overtime_limit_hours"]} overtime hours. It passes {resilient["stress_cases_passed"]}/{resilient["stress_cases_tested"]} later-period stress cases; the worst service result is {100 * resilient["worst_on_time_share"]:.1f}% and the maximum modeled cost is ${resilient["worst_modeled_cost"]:,.0f}.
- **Decision rule:** {result["actions"]["decision_rule"]}

## Evidence Boundary

''' + "\n".join(f"- {item}" for item in result["evidence_boundary"]) + "\n"


if __name__ == "__main__":
    result = build()
    JSON_OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    MARKDOWN_OUTPUT.write_text(markdown(result), encoding="utf-8")
    print(f"Wrote {JSON_OUTPUT.relative_to(ROOT)} and {MARKDOWN_OUTPUT.relative_to(ROOT)}")
