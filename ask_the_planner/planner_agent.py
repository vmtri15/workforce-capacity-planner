"""Build a Vanna 2.0 agent that answers questions about the planner database, read only, with Gemini.

The Gemini key is never in the code. Either put it in a .env file in the project root (gitignored):
    GEMINI_API_KEY=your key
or set it in your shell: export GEMINI_API_KEY="your key". GOOGLE_API_KEY also works.
Optional: GEMINI_MODEL to pick a model. The default is gemini-3.8-flash.
"""
import logging
import os
import uuid
from dataclasses import dataclass
from pathlib import Path

from vanna import Agent, AgentConfig
from vanna.core.registry import ToolRegistry
from vanna.core.user import RequestContext, User, UserResolver
from vanna.integrations.local import LocalFileSystem
from vanna.integrations.local.agent_memory import DemoAgentMemory
from vanna.tools import RunSqlTool

from prompt import PlannerPromptBuilder
from readonly_sql import ReadOnlySqlRunner

HERE = Path(__file__).resolve().parent
DEFAULT_DB = HERE.parent / 'data/workforce_planner.db'
DEFAULT_MODEL = 'gemini-3.8-flash'  # gemini-2.5-flash is closed to new accounts


def load_env_file(path=HERE.parent / '.env'):
    """Read KEY=VALUE lines from the project's .env file. A value already set in the shell wins."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            key = key.strip().removeprefix('export ').strip()
            os.environ.setdefault(key, value.strip().strip('"').strip("'"))


class LocalUserResolver(UserResolver):
    """One local analyst. There is no login, the tool runs on your own machine."""

    async def resolve_user(self, request_context: RequestContext) -> User:
        return User(id='analyst', username='analyst', group_memberships=['user'])


@dataclass
class Planner:
    agent: Agent
    runner: ReadOnlySqlRunner


def gemini_service(model=None):
    load_env_file()
    from gemini_fix import FixedGeminiLlmService  # Vanna's own Gemini service fails on current models
    return FixedGeminiLlmService(model=model or os.getenv('GEMINI_MODEL', DEFAULT_MODEL), temperature=0.0)


def build_planner(database_path=DEFAULT_DB, use_glossary=True, llm=None, model=None) -> Planner:
    runner = ReadOnlySqlRunner(database_path)
    registry = ToolRegistry()
    # results saved by the SQL tool go to a gitignored scratch folder
    tool = RunSqlTool(sql_runner=runner, file_system=LocalFileSystem(working_directory=str(HERE / '.run_data')))
    registry.register_local_tool(tool, access_groups=['user'])  # the 2.0.2 name; the README and examples say register()
    agent = Agent(
        llm_service=llm or gemini_service(model),
        tool_registry=registry,
        user_resolver=LocalUserResolver(),
        agent_memory=DemoAgentMemory(),
        config=AgentConfig(stream_responses=False, temperature=0.0, max_tool_iterations=6),
        system_prompt_builder=PlannerPromptBuilder(database_path, use_glossary),
    )
    return Planner(agent=agent, runner=runner)


def component_text(component) -> str:
    """The readable text of a streamed UI component, if it has any."""
    for holder in (getattr(component, 'simple_component', None), getattr(component, 'rich_component', None)):
        for field in ('text', 'content', 'message'):
            value = getattr(holder, field, None)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ''


class _ErrorCollector(logging.Handler):
    """Keeps Vanna's error log lines. Vanna catches agent errors and only shows 'Error occurred'."""

    def __init__(self):
        super().__init__(logging.ERROR)
        self.messages = []

    def emit(self, record):
        message = record.getMessage()
        if record.exc_info and record.exc_info[1] is not None:
            message += f' | {type(record.exc_info[1]).__name__}: {record.exc_info[1]}'
        self.messages.append(message)


async def ask(planner: Planner, question: str) -> dict:
    """Ask one question. Returns the answer text and every SQL statement the model ran."""
    planner.runner.log.clear()
    texts = []
    collector = _ErrorCollector()
    vanna_log = logging.getLogger('vanna')
    vanna_log.addHandler(collector)
    try:
        async for component in planner.agent.send_message(RequestContext(), question, conversation_id=str(uuid.uuid4())):
            text = component_text(component)
            if text:
                texts.append(text)
        error = None
    except Exception as exc:  # a failed run is a result too
        error = f'{type(exc).__name__}: {exc}'
    finally:
        vanna_log.removeHandler(collector)
    error = error or (collector.messages[-1] if collector.messages else None)
    return dict(question=question, answer=texts[-1] if texts else '', all_text=texts,
                queries=list(planner.runner.log), error=error)
