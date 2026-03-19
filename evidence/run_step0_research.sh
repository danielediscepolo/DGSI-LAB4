#!/usr/bin/env bash
set -euo pipefail

cd /home/ubuntu/workspace/week-04
rm -f /tmp/test_step0.db
tmp_out="/tmp/step0_research.txt"

{
  echo "# SQLite CLI quick test"
  sqlite3 /tmp/test_step0.db "CREATE TABLE demo (id INTEGER PRIMARY KEY, name TEXT);"
  sqlite3 /tmp/test_step0.db "INSERT INTO demo VALUES (1, 'Alice');"
  sqlite3 /tmp/test_step0.db "INSERT INTO demo VALUES (2, 'Bob');"
  echo "-- SELECT * FROM demo;"
  sqlite3 /tmp/test_step0.db "SELECT * FROM demo;"
  echo "-- .tables"
  sqlite3 /tmp/test_step0.db ".tables"
  echo "-- .schema demo"
  sqlite3 /tmp/test_step0.db ".schema demo"
  echo "-- ls -lh /tmp/test_step0.db"
  ls -lh /tmp/test_step0.db

  echo
  echo "# subprocess.run sync test"
  /home/ubuntu/llm-venv/bin/python -c "import subprocess,time; t=time.time(); p=subprocess.run(['bash','-lc','sleep 1; echo done'],capture_output=True,text=True); print(f'returncode={p.returncode}'); print(f'stdout={p.stdout.strip()}'); print(f'elapsed_seconds={time.time()-t:.2f}')"

  echo
  echo "# wget success test"
  wget -q -O - https://jsonplaceholder.typicode.com/users | head -c 260
  echo

  echo
  echo "# wget bad URL test"
  set +e
  wget -q -O - https://thisdomaindoesnotexist.fake/data
  echo "wget_exit_code=$?"
  set -e
} > "$tmp_out" 2>&1

cp "$tmp_out" evidence/step0_research.txt
cat "$tmp_out"
