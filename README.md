# Chapter 5: Deep Agent + Skills

Moves penalty calculation rules into a reusable skill.

## Setup

```bash
uv sync
cp .env.example .env
```

Set `OPENROUTER_API_KEY` and `OPENROUTER_MODEL` in `.env`.

## Run

```bash
uv run python main.py --self-check
uv run python main.py "Audit the account for Gujarat Steel Corp."
uv run pytest
```
