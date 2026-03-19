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
    }
]


messages = [
    {
        "role": "user",
        "content": "Create a table named test with columns id and name."
    }
]

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

if message.tool_calls:
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

    final_response = client.chat.completions.create(
        model=model,
        messages=messages,
        tools=tools,
        tool_choice="auto",
    )

    print("\nRISPOSTA FINALE:\n")
    print(final_response.choices[0].message.content)
else:
    print("\nNessun tool call richiesto.")
