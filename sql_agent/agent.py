"""Natural-language -> pre-written SQL -> plain-English answer agent.

Flow for each question:
  1. Match: the LLM picks the query from the repository that best fits the question.
  2. Execute: the chosen SQL runs against the database (read-only).
  3. Answer: the LLM turns the raw rows into a natural-language answer.
"""

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

import anthropic

from database import DB_PATH, build_sample_db, run_query

HERE = Path(__file__).parent
REPO_PATH = HERE / "query_repository.json"
MODEL = os.environ.get("SQL_AGENT_MODEL", "claude-haiku-5-5")
MAX_ROWS_FOR_ANSWER = 50


@dataclass
class QueryResult:
    query_id: str | None
    sql: str | None
    columns: list[str]
    rows: list[tuple]
    answer: str


def load_repository(path: Path = REPO_PATH) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)["queries"]


def _ask(client: anthropic.Anthropic, system: str, user: str, max_tokens: int = 500) -> str:
    response = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(block.text for block in response.content if block.type == "text").strip()


def match_query(client: anthropic.Anthropic, question: str, repository: list[dict]) -> str | None:
    """Ask the LLM which repository query best answers the question. Returns its id or None."""
    catalog = "\n".join(
        f"- id: {q['id']}\n  description: {q['description']}\n"
        f"  example questions: {' | '.join(q['example_questions'])}"
        for q in repository
    )
    system = (
        "You route user questions to pre-written SQL queries. "
        "Pick the single query whose description and example questions best match the user's intent. "
        "If none of the queries is a reasonable match, choose null. "
        'Reply with only JSON, like {"query_id": "<id>"} or {"query_id": null}.'
    )
    user = f"Available queries:\n{catalog}\n\nUser question: {question}"

    raw = _ask(client, system, user, max_tokens=100)
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return None
    query_id = json.loads(match.group(0)).get("query_id")
    valid_ids = {q["id"] for q in repository}
    return query_id if query_id in valid_ids else None


def answer_from_rows(client: anthropic.Anthropic, question: str, columns: list[str], rows: list[tuple]) -> str:
    """Ask the LLM to write a plain-English answer grounded only in the query results."""
    shown = rows[:MAX_ROWS_FOR_ANSWER]
    table = "\n".join([" | ".join(columns)] + [" | ".join(str(v) for v in row) for row in shown])
    if not rows:
        table = "(no rows returned)"
    system = (
        "You answer business questions using query results. "
        "Use only the data provided; do not invent numbers. "
        "Answer in a few clear sentences or a short list. Round money to two decimals."
    )
    user = f"Question: {question}\n\nQuery results:\n{table}"
    return _ask(client, system, user, max_tokens=600)


def answer_question(question: str, client: anthropic.Anthropic | None = None,
                    repository: list[dict] | None = None, db_path: Path = DB_PATH) -> QueryResult:
    client = client or anthropic.Anthropic()
    repository = repository or load_repository()

    query_id = match_query(client, question, repository)
    if query_id is None:
        return QueryResult(None, None, [], [],
                           "I couldn't find a pre-written query that answers that. "
                           "Try asking about revenue, products, customers, countries, categories, or orders.")

    sql = next(q["sql"] for q in repository if q["id"] == query_id)
    columns, rows = run_query(sql, db_path=db_path)
    answer = answer_from_rows(client, question, columns, rows)
    return QueryResult(query_id, sql, columns, rows, answer)


def main() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("Set the ANTHROPIC_API_KEY environment variable first.")

    if not DB_PATH.exists():
        build_sample_db()
        print(f"Created sample database at {DB_PATH}")

    client = anthropic.Anthropic()
    repository = load_repository()
    print("SQL Insight Chatbot (type 'exit' to quit)\n")

    while True:
        try:
            question = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not question:
            continue
        if question.lower() in {"exit", "quit"}:
            break

        result = answer_question(question, client=client, repository=repository)
        if result.query_id:
            print(f"\n[matched query: {result.query_id}]")
            print(f"[SQL: {result.sql}]")
        print(f"\nBot: {result.answer}\n")


if __name__ == "__main__":
    main()
