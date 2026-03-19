import argparse
import json
import os
import shlex
import sqlite3
import subprocess
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv
from openai import OpenAI


BASE_DIR = Path(__file__).resolve().parent

SYSTEM_PROMPT = (
    "You are a careful data assistant that must use tools for external data and SQL execution. "
    "When asked to fetch URLs, call wget. "
    "When asked to create or query tables, call execute_sql. "
    "Return one SQL statement per tool call whenever possible. "
    "After completing all tool work, provide a concise final summary."
)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "wget",
            "description": (
                "Fetch content from a URL using system wget. "
                "This tool requires explicit user approval before running."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Absolute URL to fetch, for example https://example.com/data.json",
                    },
                    "flags": {
                        "type": "string",
                        "description": "Optional wget flags. Default is '-q -O -'.",
                    },
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "execute_sql",
            "description": (
                "Run SQL against local SQLite database.db. "
                "Use this tool to CREATE, INSERT, UPDATE, DELETE, and SELECT."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "SQL statement to execute on SQLite database.db",
                    }
                },
                "required": ["query"],
            },
        },
    },
]


def get_db_path() -> Path:
    db_from_env = os.getenv("DATABASE_PATH")
    if db_from_env:
        return Path(db_from_env)
    return BASE_DIR / "database.db"


def json_result(ok: bool, data: Any = None, error: str | None = None) -> str:
    payload = {"ok": ok, "data": data, "error": error}
    return json.dumps(payload, ensure_ascii=True)


def preview_text(text: str, limit: int = 500) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[:limit] + "...(truncated)"


def run_wget(
    url: str,
    flags: str = "-q -O -",
    confirm_policy: str = "prompt",
    timeout_seconds: int = 30,
) -> str:
    cmd = ["wget", *shlex.split(flags), url]
    command_text = shlex.join(cmd)
    print(f"[confirm] LLM wants to run: {command_text}")

    if confirm_policy == "always":
        approved = True
        print("[confirm] Auto-approval policy active: yes")
    elif confirm_policy == "never":
        approved = False
        print("[confirm] Auto-deny policy active: no")
    else:
        answer = input("Allow command? (y/n): ").strip().lower()
        approved = answer == "y"

    if not approved:
        return json_result(
            False,
            data={"command": command_text},
            error="USER DENIED: command was not executed.",
        )

    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except Exception as exc:
        return json_result(False, data={"command": command_text}, error=f"wget execution error: {exc}")

    if completed.returncode != 0:
        return json_result(
            False,
            data={"command": command_text, "returncode": completed.returncode},
            error=f"wget failed: {(completed.stderr or completed.stdout).strip()}",
        )

    return json_result(
        True,
        data={
            "command": command_text,
            "returncode": completed.returncode,
            "stdout": completed.stdout,
        },
    )


def execute_sql(query: str) -> str:
    sql = query.strip()
    if not sql:
        return json_result(False, error="SQL query is empty")

    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            try:
                cursor.execute(sql)
            except sqlite3.ProgrammingError as exc:
                if "one statement at a time" in str(exc).lower():
                    cursor.executescript(sql)
                    conn.commit()
                    return json_result(True, data={"message": "SQL script executed"})
                raise

            sql_lower = sql.lower()
            if sql_lower.startswith(("select", "pragma", "with")):
                rows = [dict(row) for row in cursor.fetchall()]
                columns = list(rows[0].keys()) if rows else []
                return json_result(
                    True,
                    data={
                        "columns": columns,
                        "rows": rows,
                        "rowcount": len(rows),
                    },
                )

            conn.commit()
            return json_result(
                True,
                data={
                    "rowcount": cursor.rowcount,
                    "lastrowid": cursor.lastrowid,
                },
            )
    except Exception as exc:
        return json_result(False, error=f"SQL error: {exc}")


TOOL_DISPATCH: dict[str, Callable[..., str]] = {
    "wget": run_wget,
    "execute_sql": execute_sql,
}


def build_client() -> OpenAI:
    load_dotenv(BASE_DIR / ".env")

    api_key = os.getenv("OPENAI_API_KEY")
    endpoint = os.getenv("OPENAI_API_ENDPOINT")

    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is missing in .env")

    if endpoint:
        return OpenAI(api_key=api_key, base_url=endpoint)
    return OpenAI(api_key=api_key)


def run_loop(
    client: OpenAI,
    model: str,
    user_prompt: str,
    confirm_policy: str,
    max_rounds: int,
    temperature: float,
    preview_limit: int,
) -> dict[str, Any]:
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    for iteration in range(1, max_rounds + 1):
        print(f"\n=== Iteration {iteration} ===")

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=TOOLS,
            temperature=temperature,
        )

        message = response.choices[0].message

        if not message.tool_calls:
            final_text = message.content or ""
            print("[assistant-final]")
            print(final_text)
            return {
                "iterations": iteration,
                "final_text": final_text,
                "messages": messages,
            }

        print(f"[assistant] Requested {len(message.tool_calls)} tool call(s)")
        messages.append(
            {
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in message.tool_calls
                ],
            }
        )

        for tc in message.tool_calls:
            tool_name = tc.function.name
            raw_args = tc.function.arguments or "{}"

            print(f"[tool-call] id={tc.id} name={tool_name}")
            print(f"[tool-args] {raw_args}")

            try:
                parsed_args = json.loads(raw_args)
            except json.JSONDecodeError as exc:
                tool_result = json_result(
                    False,
                    data={"raw_arguments": raw_args},
                    error=f"Invalid JSON arguments: {exc}",
                )
            else:
                handler = TOOL_DISPATCH.get(tool_name)
                if handler is None:
                    tool_result = json_result(False, error=f"Unknown tool: {tool_name}")
                else:
                    try:
                        if tool_name == "wget":
                            tool_result = handler(confirm_policy=confirm_policy, **parsed_args)
                        else:
                            tool_result = handler(**parsed_args)
                    except Exception as exc:
                        tool_result = json_result(False, error=f"Tool execution error: {exc}")

            print(f"[tool-result-preview] {preview_text(tool_result, limit=preview_limit)}")

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": tool_name,
                    "content": tool_result,
                }
            )

    limit_msg = f"Stopped after max_rounds={max_rounds} without final assistant text."
    print(f"[warning] {limit_msg}")
    return {
        "iterations": max_rounds,
        "final_text": limit_msg,
        "messages": messages,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Week-04 function-calling loop with wget + sqlite tools")
    parser.add_argument(
        "--prompt",
        type=str,
        default=(
            "Fetch https://jsonplaceholder.typicode.com/users and store the id, name, email, "
            "and city of every user in a SQLite table called users. Show me the final contents of the table."
        ),
        help="User prompt to send to the model",
    )
    parser.add_argument(
        "--prompt-file",
        type=str,
        default=None,
        help="Read user prompt from text file",
    )
    parser.add_argument(
        "--confirm-policy",
        choices=["prompt", "always", "never"],
        default="prompt",
        help="Control wget confirmation flow",
    )
    parser.add_argument("--max-rounds", type=int, default=20, help="Maximum loop iterations")
    parser.add_argument("--temperature", type=float, default=0.0, help="Model temperature")
    parser.add_argument(
        "--preview-limit",
        type=int,
        default=650,
        help="Character limit for printed tool result preview",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Override model from .env (MODEL=...)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    load_dotenv(BASE_DIR / ".env")
    model = args.model or os.getenv("MODEL", "gpt-4.1-mini")
    endpoint = os.getenv("OPENAI_API_ENDPOINT", "https://api.openai.com/v1")
    db_path = get_db_path()

    print("Week-04 Tool Loop Agent")
    print(f"Model: {model}")
    print(f"Endpoint: {endpoint}")
    print(f"Database: {db_path}")
    print(f"Confirm policy: {args.confirm_policy}")
    if args.prompt_file:
        prompt_path = Path(args.prompt_file)
        args.prompt = prompt_path.read_text(encoding="utf-8").strip()
    print(f"Prompt: {args.prompt}")

    client = build_client()
    summary = run_loop(
        client=client,
        model=model,
        user_prompt=args.prompt,
        confirm_policy=args.confirm_policy,
        max_rounds=args.max_rounds,
        temperature=args.temperature,
        preview_limit=args.preview_limit,
    )
    print(
        f"\n[summary] iterations={summary['iterations']} final_text_preview={preview_text(summary['final_text'], 180)}"
    )


if __name__ == "__main__":
    main()
