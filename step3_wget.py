import json
import os
import sqlite3
import subprocess

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
base_url = os.getenv("OPENAI_BASE_URL")
model = os.getenv("OPENAI_MODEL")

client = OpenAI(
    api_key=api_key,
    base_url=base_url,
)


def execute_sql(query: str) -> str:
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute(query)

        if query.strip().lower().startswith("select"):
            rows = cursor.fetchall()
            conn.close()
            return json.dumps(rows, ensure_ascii=False)

        conn.commit()
        conn.close()
        return "Query eseguita correttamente."
    except Exception as e:
        return f"SQL ERROR: {e}"


def wget_url(url: str) -> str:
    command = ["wget", "-q", "-O", "-", url]

    print("\nCOMANDO DA ESEGUIRE:")
    print(" ".join(command))

    confirm = input("Vuoi eseguire questo comando? (y/n): ").strip().lower()

    if confirm != "y":
        return "USER DENIED"

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            return f"WGET ERROR: {result.stderr.strip()}"

        return result.stdout
    except Exception as e:
        return f"WGET ERROR: {e}"


tools = [
    {
        "type": "function",
        "function": {
            "name": "execute_sql",
            "description": "Execute an SQL query on a local SQLite database.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The SQL query to execute"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "wget_url",
            "description": "Download the content of a URL using wget and return it as text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to download"
                    }
                },
                "required": ["url"]
            }
        }
    }
]

messages = [
    {
        "role": "system",
        "content": (
            "You are a helpful assistant with two tools: "
            "execute_sql for SQLite queries and wget_url for downloading URL content. "
            "When data from a URL must be stored in the database, first call wget_url, "
            "then use execute_sql step by step. "
            "If a tool returns USER DENIED or an error, explain it clearly and do not invent results."
        )
    },
    {
        "role": "user",
        "content": (
            "Download the JSON from https://jsonplaceholder.typicode.com/users. "
            "Create a table named users with columns id, name, email, city. "
            "Insert all users into the database. "
            "Then show me all rows from the table."
        )
    }
]

while True:
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        tools=tools,
        tool_choice="auto",
    )

    message = response.choices[0].message
    messages.append(message)

    print("\nMODELLO:\n")
    print(message)

    if not message.tool_calls:
        print("\nRISPOSTA FINALE:\n")
        print(message.content)
        break

    for tool_call in message.tool_calls:
        function_name = tool_call.function.name
        arguments = json.loads(tool_call.function.arguments)

        if function_name == "execute_sql":
            result = execute_sql(arguments["query"])

            print("\nTOOL CHIAMATO:", function_name)
            print("ARGOMENTI:", arguments)
            print("RISULTATO:", result)

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                }
            )

        elif function_name == "wget_url":
            result = wget_url(arguments["url"])

            print("\nTOOL CHIAMATO:", function_name)
            print("ARGOMENTI:", arguments)

            preview = result[:500] + "..." if len(result) > 500 else result
            print("RISULTATO:", preview)

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                }
            )
