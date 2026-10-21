"""The system prompt: the database schema, plus the business glossary when it is switched on.

Three conditions in the evaluation. schema_only and glossary get the same instructions and schema and
differ only by the glossary. guided adds what FAILURE_REVIEW.md proposed: the base case views
(build_eval_db.py), the base case rule in the main instructions, and worked examples. The examples use
questions that are not in the test set.
"""
from pathlib import Path
from typing import List, Optional

from vanna.core.system_prompt import SystemPromptBuilder

from readonly_sql import connect_read_only

GLOSSARY_PATH = Path(__file__).resolve().parent / 'glossary.md'

INSTRUCTIONS = """You are a data analyst assistant for a workforce capacity planning database (SQLite).
Answer business questions by writing a SQL SELECT and running it with the run_sql tool.

Rules:
- Only SELECT queries. The database is read only.
- Use only the tables and columns in the schema below. Do not invent columns.
- Keep the SQL simple. Run one query at a time and check the result before you answer.
- When you have the result, answer in one or two plain sentences with the key numbers and their unit.
- If the question is ambiguous, pick the most standard reading and say which one you used.
- If the database cannot answer the question, say so. Do not guess and do not make up numbers.
"""


GUIDED_RULES = """
Most important rule: the database holds every plan three times, once per productivity case (low, base,
high). Unless the question names a case, use the base case only. The base_case_* views already hold only
the base run, so query them first: base_case_staffing, base_case_capacity, base_case_workload,
base_case_summary. Use the full tables only for a question about the low or high case, or comparing cases.
Never add up rows across runs.

Questions about the original source data (workload_daily_source) mean the planning window,
2011-10-14 to 2011-12-08, unless the question asks for the whole source history.

Worked examples:
Q: What is the average coverage rate for packing at O'Hare?
SQL: SELECT AVG(coverage_rate) FROM base_case_capacity WHERE site_id = 'ohare' AND role_id = 'packing_associate'
Q: How many units are planned for Kenosha over the window?
SQL: SELECT SUM(modeled_units) FROM base_case_workload WHERE site_id = 'kenosha'
Q: What is the average coverage in the high productivity case?
SQL: SELECT AVG(coverage_rate) FROM daily_capacity_results WHERE run_id = 'base_demand_high_productivity'
"""


def schema_text(database_path, include_base_views=False) -> str:
    connection = connect_read_only(database_path)
    try:
        rows = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type IN ('table', 'view') AND sql IS NOT NULL "
            "AND (? OR name NOT LIKE 'base\\_case\\_%' ESCAPE '\\') ORDER BY type, name", (include_base_views,)
        ).fetchall()
    finally:
        connection.close()
    return '\n\n'.join(row[0] for row in rows)


class PlannerPromptBuilder(SystemPromptBuilder):
    def __init__(self, database_path, use_glossary: bool, guided: bool = False):
        self.schema = schema_text(database_path, include_base_views=guided)
        self.glossary = GLOSSARY_PATH.read_text() if use_glossary else None
        self.guided = guided

    async def build_system_prompt(self, user, tools: List) -> Optional[str]:
        parts = [INSTRUCTIONS + (GUIDED_RULES if self.guided else ''), 'Database schema:\n' + self.schema]
        if self.glossary:
            parts.append('Business glossary. Use these definitions when a question uses these terms:\n' + self.glossary)
        return '\n\n'.join(parts)
