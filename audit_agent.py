from __future__ import annotations

import argparse
import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from deepagents import create_deep_agent
from loguru import logger

ROOT = Path(__file__).resolve().parent
ENV_PATH = ROOT / ".env"
DEFAULT_MODEL = "openrouter:inclusionai/ring-2.6-1t:free"

CONTRACTS_DIR = ROOT / "contracts"
DB_PATH = ROOT / "ap_ledger.db"
DELIVERY_LOG_PATH = ROOT / "warehouse_receipts_fy26.csv"

SYSTEM_PROMPT = """
You are the Senior Financial Auditor for Shree Manufacturing Pvt. Ltd.
You MUST use write_todos to outline a 3-step audit plan before taking any other action.
Use query_ledger for accounts payable data, check_delivery_log for warehouse receipts, and read_file for legal contracts.
Use the penalty_logic skill when penalty calculation is required. Report any discrepancy greater than INR 0.
""".strip()


def _connect():
    import sqlite3
    return sqlite3.connect(DB_PATH)


def query_ledger(sql: str) -> str:
    """Execute a read-only SQL query against the accounts payable ledger."""
    lowered = sql.strip().lower()
    if not lowered.startswith("select"):
        raise ValueError("Only SELECT statements are allowed")
    with _connect() as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(sql).fetchall()
    return json.dumps([dict(row) for row in rows])


def check_delivery_log(vendor_id: str) -> str:
    """Return warehouse receipt rows for a vendor without exposing unrelated rows."""
    import pandas as pd
    frame = pd.read_csv(DELIVERY_LOG_PATH)
    rows = frame.loc[frame["Vendor_ID"] == vendor_id].copy()
    rows["days_late"] = (
        pd.to_datetime(rows["Actual_Delivery"]) - pd.to_datetime(rows["Expected_Delivery"])
    ).dt.days
    return rows.to_json(orient="records")


def find_contract(vendor_name: str) -> Path:
    path = CONTRACTS_DIR / (vendor_name.replace(" ", "_") + "_Contract.txt")
    if not path.exists():
        raise FileNotFoundError(path)
    return path


def read_contract(vendor_name: str) -> str:
    return find_contract(vendor_name).read_text(encoding="utf-8")


def get_vendor_id(vendor_name: str) -> str:
    rows = json.loads(query_ledger(f"select Vendor_ID from Vendors where Vendor_Name = '{vendor_name}'"))
    if not rows:
        raise ValueError(f"Unknown vendor: {vendor_name}")
    return rows[0]["Vendor_ID"]


def build_discrepancy_summary(vendor_name: str) -> dict[str, Any]:
    vendor_id = get_vendor_id(vendor_name)
    invoices = json.loads(query_ledger(f"select Invoice_ID, Vendor_ID, Amount, Status from Invoices where Vendor_ID = '{vendor_id}'"))
    deliveries = json.loads(check_delivery_log(vendor_id))
    max_late = max(row["days_late"] for row in deliveries)
    invoice_amount = float(invoices[0]["Amount"])
    penalty = invoice_amount * 0.05 if max_late > 7 and "5% penalty" in read_contract(vendor_name) else 0.0
    return {
        "vendor_id": vendor_id,
        "vendor_name": vendor_name,
        "invoice_amount": invoice_amount,
        "days_late": int(max_late),
        "penalty_amount_inr": penalty,
        "action_required": "Recover Funds" if penalty else "None",
    }


def build_agent(model_name: str):
    return create_deep_agent(
        model=model_name,
        tools=[query_ledger, check_delivery_log],
        system_prompt=SYSTEM_PROMPT,
        skills=["./skills/penalty_logic/"],
    )


def run_self_check() -> str:
    return json.dumps(build_discrepancy_summary("Gujarat Steel Corp"), indent=2)


def load_model_name() -> str:
    load_dotenv(ENV_PATH)
    return os.getenv("OPENROUTER_MODEL") or os.getenv("MODEL_NAME") or DEFAULT_MODEL


def invoke_agent(prompt: str) -> str:
    agent = build_agent(load_model_name())
    result = agent.invoke({"messages": [{"role": "user", "content": prompt}]})
    messages = result.get("messages", [])
    if not messages:
        return ""
    final = messages[-1]
    return str(getattr(final, "content", final))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt", nargs="?", default="What is your job?")
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args(argv)

    if args.self_check:
        print(run_self_check())
        return 0

    print(invoke_agent(args.prompt))
    return 0
