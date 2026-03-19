# Week 4 — Function Calling in Practice: From One Call to Many

## Part 1: Lecture — Refresher and New Pattern

**Quick Review: What Function Calling Is**

Last week you learned the fundamentals. Let’s recap the three things that make function calling work:

**1. Tool definitions** — JSON schemas that describe what tools the model can use.

**{**
"type" **:** "function" **,**
"function" **:{**
"name" **:** "execute_sql" **,**
"description" **:** "Run a SQL statement against the local SQLite database." **,**
"parameters" **:{**
"type" **:** "object" **,**
"properties" **: {**
"query" **: {**
"type" **:** "string" **,**
"description" **:** "The SQL statement to execute."
**}
},**
"required" **:** ["query"]
**}
}
}**

The model never sees your Python code. It only sees these schemas. That means: - Good descriptions →
good tool choices. - Vague descriptions → the model guesses and often guesses wrong.

**2. The API request** — your program sendsmessagesandtoolstogether.

response **=** client.chat.completions.create(
model **=** MODEL,
messages **=** messages,
tools **=** tools,
)

**3. The response** — the model either returns plain text or atool_callslist.

message **=** response.choices[ 0 ].message

**if** message.tool_calls:
_# The model wants you to execute something_
**for** tc **in** message.tool_calls:
name **=** tc.function.name _# e.g. "execute_sql"_
args **=** json.loads(tc.function.arguments) _# e.g. {"query": "SELECT ..."}_
**else** :
_# The model is done — this is the final answer_
print(message.content)

Your program decides whether to execute the tool. The model only _asks_.


**New This Week: Multiple Rounds**

Last week the pattern was: one user message → one tool call → one final answer. That works for simple
cases, but real tasks often need many steps.

Consider this prompt:

```
“Fetch the list of users from this API and store them in a database.”
```
The model needs to: 1. Download the data (tool call) 2. Create a table (tool call) 3. Insert each row (tool
call, possibly multiple) 4. Query the table to confirm (tool call) 5. Summarise the result (final text answer)

That is **at least four rounds** of tool calls before the model can answer.

**The Loop Pattern**

The solution is awhileloop:

**while** True:
response **=** client.chat.completions.create(
model **=** MODEL,
messages **=** messages,
tools **=** tools,
)

```
message = response.choices[ 0 ].message
```
```
if not message.tool_calls:
# No tools requested — we have the final answer
print(message.content)
break
```
```
# Append the assistant message (with its tool_calls) to the conversation
messages.append({
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
})
```
```
# Execute each tool call and append the result
for tc in message.tool_calls:
name = tc.function.name
args = json.loads(tc.function.arguments)
```
```
result = dispatch[name]( ** args) # call the real function
```
```
messages.append({
```

```
"role": "tool",
"tool_call_id": tc.id,
"name": name,
"content": result,
})
```
```
# Loop continues — the model gets all results and decides what to do next
```
```
The key insight: the model decides when to stop. Your program just keeps executing whatever the
model asks for, and stops when the model responds with text instead of tool calls.
```
```
The Dispatch Table
```
When you have multiple tools, you need a way to map a tool name (a string from the API) to the actual
Python function. A dictionary works perfectly:
**def** tool_wget(url, flags **=** "-q -O -"):
_# ... run wget ..._
**return** output

```
def tool_execute_sql(query):
# ... run SQL ...
return result
```
```
dispatch = {
"wget": tool_wget,
"execute_sql": tool_execute_sql,
}
```
```
Then calling the right function is just:
handler = dispatch[tool_name]
result = handler( ** arguments)
```
```
Noif/elifchain needed. This pattern scales cleanly to any number of tools.
```
```
The Message Protocol
```
```
Pay attention to how messages flow in the conversation when tools are involved:
```
```
# Role Content
0 system “You are a helpful assistant...”
1 user “Fetch the data and store it”
2 assistant (empty content, but hastool_calls)
3 tool Result of wget call
4 assistant (empty content, anothertool_calls)
5 tool Result of CREATE TABLE
6 assistant (empty content, anothertool_calls)
7 tool Result of INSERT
8 assistant “Done! I fetched 10 users and stored them.”
```
```
Row 8 has notool_calls— that is how your loop knows to stop.
Every tool result must include thetool_call_idthat matches the request. The API will reject messages
with mismatched IDs.
```

**Human in the Loop**
Some tools are safe to run automatically (a SQL SELECT on a local database). Others are dangerous
(downloading arbitrary URLs from the internet). A simple but effective pattern:

```
def tool_wget(url, flags = "-q -O -"):
cmd = f"wget { flags } { url } "
print(f"The LLM wants to run: { cmd } ")
answer = input("Allow? (y/n): ")
if answer != "y":
return "USER DENIED: command was not executed."
# ... proceed with subprocess ...
```
```
The model receives the denial message and can adapt — it might rephrase, try a different approach, or
simply explain that it could not complete the task.
```
## Part 2: The Exercise — Build It, Step by Step

```
What You Will Build
A Python program that gives an LLM access to two tools:
```
1. **wget** — fetches a URL using the systemwgetcommand. The user must approve every execution.
2. **execute_sql** — runs SQL statements against a local SQLite database (database.db).
The program runs the LLM in a loop: call the model, execute any tool calls, feed the results back, repeat —
until the model responds with plain text.

```
The Test
Your default test prompt:
“Fetch https://jsonplaceholder.typicode.com/users and store the id, name, email, and city of
every user in a SQLite table calledusers. Show me the final contents of the table.”
```
```
Step 0: Research — Know Your Tools Before You Code
```
```
Before writing a single line of Python, you need to understand the three building blocks you will use. Do
some research, try them out on the command line, and write up what you learned.
SQLite and thesqlite3CLI tool
SQLite is not a server — it is a library that stores an entire database in a single file. You need to understand
how this differs from a full database engine like PostgreSQL or MySQL.
Try it yourself on the terminal:
sqlite3 test.db
```
```
Inside the SQLite shell, run:
CREATE TABLE demo ( id INTEGER PRIMARYKEY , name TEXT);
INSERT INTO demo VALUES ( 1 ,'Alice');
INSERT INTO demo VALUES ( 2 ,'Bob');
SELECT *FROM demo;
```
. **tables**
. **schema** demo
.quit


Then check your filesystem — you will seetest.dbis just a regular file. That is the entire database. No
server process, no port, no configuration.
Think about: where are the tables stored? Where are the indexes? What happens if two programs try to
write to the same file at the same time? What can PostgreSQL do that SQLite cannot — and when does
that matter?
**Running terminal commands from Python**
Yourwgettool will need to run a shell command from inside a Python script. Research thesubprocess
module — specificallysubprocess.run(). Understand whatcapture_output=Truedoes, whattext=True
does, and whattimeoutdoes.
Think about: doessubprocess.run()block until the command finishes, or does it return immediately?
What is the difference betweensubprocess.run()andsubprocess.Popen()? When would you want asyn-
chronous execution, and when is synchronous enough?
**wget**
Make surewgetis installed on your system. Try fetching a URL:
**wget** -q -O -https://jsonplaceholder.typicode.com/users **|head** -

```
The flags-q -O -mean: quiet mode, output to stdout (instead of saving to a file). Understand what
happens without those flags. Understand whatwgetdoes when the URL does not exist, when the server is
slow, and when the output is very large.
In your PDF: write a short section covering these three topics. Explain what SQLite is and how it differs
from a server-based database. Explain howsubprocess.run()works and whether it is synchronous or
asynchronous. Explain whatwgetdoes and what flags you will use. Use your own words — this section is
about demonstrating that you understand the tools, not about producing polished prose.
```
```
The 5 Steps
You must build the program incrementally. Document each step in your PDF report — show the code
you wrote, what you tested, and what happened.
```
```
Step 1: Project Setup and a Single Tool Call Create auvproject. Installopenaiandpython-dotenv.
Load your API credentials from a.envfile.
Define theexecute_sqltool schema. Write a Python function that runs a SQL statement ondatabase.db
using thesqlite3module.
Send a hardcoded prompt to the LLM:
“Create a table called test with columns: id INTEGER, name TEXT.”
Confirm that the model responds with atool_callsentry. Execute the SQL. Print the result.
In your PDF: show the tool schema, the code that handles the response, and a screenshot or terminal
output proving the table was created.
```

```
Step 2: The Loop — Multiple Tool Calls in Sequence Wrap your LLM call in awhileloop. After
executing each tool call, append the result to the conversation and call the model again.
Test with a prompt that requires two steps:
“Create a table called cities with columns id and name. Then insert three Spanish cities.”
The model should make at least two tool calls (CREATE TABLE, then INSERT). Your loop must handle
both before the model produces a final text answer.
In your PDF: show the loop code. Show the terminal output with both tool calls visible. Explain how
your program knows when to stop looping.
```
**Step 3: ThewgetTool with User Confirmation** Add the second tool:wget. Use Python’ssubprocess
module to run the realwgetcommand.
Before every execution, display the exact command to the user and ask for confirmation. If the user types
y, run it. If not, return a denial message to the model.
Test with a simple prompt:
“Download the content from https://jsonplaceholder.typicode.com/users”
Approve the wget command when asked. Verify that the JSON content is returned to the model.
**In your PDF:** show the wget tool schema, the confirmation code, and the output when the user approves
— and also what happens when the user denies the command.

```
Step 4: The Full Test — Fetch, Store, Query Run the complete test prompt:
“Fetch https://jsonplaceholder.typicode.com/users and store the id, name, email, and city of
every user in a SQLite table calledusers. Show me the final contents of the table.”
This will trigger many rounds through your loop. The model needs to callwget, thenexecute_sqlseveral
times (create table, insert rows, select results), and finally produce a text summary.
After the program finishes, verify the data independently:
sqlite3 database.db "SELECT * FROM users;"
```
```
In your PDF: show the full terminal output of the run. Show the independentsqlite3verification. Count
how many iterations the loop ran.
```
```
Step 5: Polish and Error Handling Make the output readable — show the tool name, arguments, and
a preview of the result at each step.
Test what happens when things go wrong:
```
- A bad URL (e.g.,https://thisdomaindoesnotexist.fake/data)
- Invalid SQL (e.g., inserting into a table that does not exist)
- The user denying the wget command
None of these should crash your program. Wrap tool executions intry/exceptand return error messages
to the model instead.
**In your PDF:** show at least two error cases and how your program handled them without crashing.


```
Extra Challenge: Does the Model Matter?
If you finish early, try this experiment. It requires no code changes — only a one-line edit in your.envfile.
You have been usingqwen3.5-122b-a10b— a large, recent model. Change your.envto use an older,
smaller model:
MODEL=qwen2.5-vl-72b-instruct
Run the exact same test prompt again:
“Fetch https://jsonplaceholder.typicode.com/users and store the id, name, email, and city of
every user in a SQLite table calledusers. Show me the final contents of the table.”
Pay attention to:
```
- Does the model produce valid tool calls at all, or does it try to answer in plain text?
- Does it format theargumentsJSON correctly, or does your program crash onjson.loads()?
- Does it choose the right tools in the right order?
- Does it write correct SQL? Does it handle the INSERT statements properly?
- Does it get stuck in the loop, or does it know when to stop?
- How many iterations does it take compared to the larger model?
Some models are worse at function calling than others. A model that is good at conversation may be bad at
producing structured tool calls. This is not a bug in your code — it is a real difference in model capability,
and it matters when you are choosing which model to deploy in production.
**In your PDF:** if you ran this experiment, show the results side by side. Which model worked better?
Where did the smaller model struggle? What would this mean if you had to choose a model for a real project
— is cheaper always worse?

## Part 3: Deliverable

```
Submission Format
Submit a single PDF report generated from Markdown.
pandoc report.md-o report.pdf--pdf-engine = xelatex
```
```
Write It Yourself
```
```
We want to read your words, not an LLM’s.
Using a language model to help you code is the whole point of this course. Using a language model to write
your report for you is not. We are interested in what you understood, what confused you, what surprised
you, and how you would explain it to someone else.
Write in your own voice. Short sentences are fine. Bullet points are fine. Typos and imperfect grammar are
completely fine — we will not penalise rough writing. What we will notice is a report that reads like it was
generated by a chatbot: generic, fluffy, and saying nothing specific about what actually happened on your
screen.
If a section of your report could have been written by someone who never ran the code, it is not good enough.
Tell us what you saw. Tell us what broke. Tell us what you did not expect.
```
```
What the PDF Must Include
Your PDF must include:
```
0. **Step 0 documentation** — your research notes on SQLite, subprocess, and wget, in your own words


1. **Step 1 documentation** — tool schema, initial code, proof of a single tool call working
2. **Step 2 documentation** — the loop, proof of sequential tool calls, explanation of the stop condition
3. **Step 3 documentation** — the wget tool, user confirmation flow, both approval and denial shown
4. **Step 4 documentation** — the full test run, complete terminal output, independent SQLite verifica-
    tion
5. **Step 5 documentation** — error handling, at least two failure cases shown and handled
6. **Link to your GitHub repository** — the repo must contain all code needed to run the program

**Required Questions to Answer in the Report**

Answer these explicitly:

```
1.How does your program know when to stop calling the LLM?
2.What is the role oftool_call_idin the message protocol?
3.Why is user confirmation important for thewgettool but not forexecute_sql?
4.What happens in the conversation when the user denies a wget command?
5.How many iterations did the loop run for the full test prompt? Were you surprised?
```
## ￿ CRITICAL: API Key Safety

**Read this carefully. This is not optional.**

Your.envfile contains your API key. If that key ends up on GitHub, anyone can use it — and you will be
charged for their usage.

**Rules**

1. **Never put API keys in.pyfiles.** Not as variables, not as comments, not “temporarily.”
2. **Never put API keys in files that are committed to git.** Not inREADME.md, not inconfig.json,
    not anywhere thatgit addwill touch.
3. **Always load credentials from a.envfile** usingpython-dotenv.
4. **Always add.envto.gitignore** before your first commit.
5. **Include a.env.example** file (with placeholder values, not real keys) so others know what variables
    are needed.

**How to Verify**

Before pushing to GitHub, run:

**git** status

If.envappears in the list of files to be committed — **stop**. Add it to.gitignorefirst.

If you accidentally committed a.envfile:

**git** rm --cached.env
echo".env" **>>** .gitignore
**git** add .gitignore
**git** commit -m"Remove .env from tracking"

Then **rotate your API key** — the old one is compromised the moment it touched a public repo, even if
you delete the commit later. Git history is permanent.

**Your.gitignoreMust Contain**

.env
database.db


__pycache__/
.venv/

This is a professional habit. Start now.

## Part 4: Summary

Concept What You Practiced

Tool schemas Defining two real tools with clear JSON schemas
The loop pattern Calling the LLM repeatedly until no tool calls
remain
subprocess Running a system command from Python, with user
control
sqlite3 Creating tables and inserting data from a Python
program
Human in the loop Asking for permission before dangerous operations
Error handling Catching failures and returning them to the model
as information
API key safety Keeping secrets out of code, out of git, out of
GitHub

This week is about learning that an LLM can orchestrate a multi-step workflow — as long as your program
handles the execution, the errors, and the security.


