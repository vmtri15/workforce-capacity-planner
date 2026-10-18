"""The system prompt: the database schema, plus the business glossary when it is switched on.

Both conditions in the evaluation get the same instructions and the same schema. The only difference is
the glossary, so any change in accuracy comes from the glossary alone.
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


def schema_text(database_path) -> str:
    connection = connect_read_only(database_path)
    try:
        rows = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type IN ('table', 'view') AND sql IS NOT NULL ORDER BY type, name"
        ).fetchall()
    finally:
        connection.close()
    return '\n\n'.join(row[0] for row in rows)


class PlannerPromptBuilder(SystemPromptBuilder):
    def __init__(self, database_path, use_glossary: bool):
        self.schema = schema_text(database_path)
        self.glossary = GLOSSARY_PATH.read_text() if use_glossary else None

    async def build_system_prompt(self, user, tools: List) -> Optional[str]:
        parts = [INSTRUCTIONS, 'Database schema:\n' + self.schema]
        if self.glossary:
            parts.append('Business glossary. Use these definitions when a question uses these terms:\n' + self.glossary)
        return '\n\n'.join(parts)
