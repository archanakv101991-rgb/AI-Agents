# Natural Language SQL Insight Chatbot

Ask a question in plain English. The agent:

1. **Matches** the question to the most relevant pre-written SQL query in `query_repository.json` (LLM-based routing on each query's description and example questions).
2. **Executes** that query against a SQLite database, read-only.
3. **Answers** by having the LLM turn the raw rows into a plain-English reply.

## Setup

```bash
pip install -r requirements.txt
set ANTHROPIC_API_KEY=your-key-here        # Windows (PowerShell: $env:ANTHROPIC_API_KEY="...")
python database.py                         # builds sample.db (optional; agent builds it if missing)
```

Optional: `SQL_AGENT_MODEL` overrides the model (default `claude-haiku-5-5`).

## Run

```bash
python agent.py
```

```
You: Which country buys the most?

[matched query: revenue_by_country]
[SQL: SELECT c.country, ROUND(SUM(oi.quantity * oi.unit_price), 2) AS revenue FROM ...]

Bot: Australia leads with $93,540.00 in revenue from delivered orders, followed by ...
```

## Tests

```bash
python -m unittest test_agent -v
```

The tests use a stub in place of the LLM, so they run without an API key.

## Files

| File | Purpose |
|---|---|
| `agent.py` | Matching, execution and answer generation, plus the chat loop |
| `database.py` | Builds the sample store database and runs SQL in read-only mode |
| `query_repository.json` | Pre-written queries with descriptions and example questions |
| `test_agent.py` | Unit tests, including read-only enforcement |

## Adding a query

Append an entry to `query_repository.json`:

```json
{
  "id": "unique_snake_case_id",
  "description": "What this query answers, in one sentence.",
  "example_questions": ["A question a user might ask", "Another way to ask it"],
  "sql": "SELECT ... ;"
}
```

The matcher only sees the description and example questions, so write them the way users would phrase questions.

## Safety

- Queries come from the repository, not from the LLM. The LLM only chooses an existing `id`.
- The database connection is opened with `mode=ro`, so SQLite rejects any write.
- Only statements starting with `SELECT` or `WITH` are accepted.
