#!/usr/bin/env bash
set -euo pipefail

cd /home/ubuntu/workspace/week-04

PYTHON_BIN="/home/ubuntu/llm-venv/bin/python"
DB_FILE="/tmp/week04/database.db"
TMP_EVIDENCE_DIR="/tmp/week04-evidence"

mkdir -p /tmp/week04 "$TMP_EVIDENCE_DIR"
rm -f "$DB_FILE"

run_case() {
  local out_name="$1"
  shift
  local tmp_out="${TMP_EVIDENCE_DIR}/${out_name}"
  {
    echo "# command"
    printf "%q " "$@"
    echo
    echo
    "$@"
  } >"$tmp_out" 2>&1
  cp "$tmp_out" "evidence/${out_name}"
  cat "$tmp_out"
}

export DATABASE_PATH="$DB_FILE"

echo "===== STEP 1 ====="
rm -f "$DB_FILE"
run_case "step1_single_tool_call.txt" \
  "$PYTHON_BIN" tool_loop_agent.py \
  --confirm-policy always \
  --prompt-file evidence/prompts/step1_prompt.txt

echo "===== STEP 2 ====="
rm -f "$DB_FILE"
run_case "step2_loop_sequence.txt" \
  "$PYTHON_BIN" tool_loop_agent.py \
  --confirm-policy always \
  --prompt-file evidence/prompts/step2_prompt.txt

echo "===== STEP 3 (approve) ====="
run_case "step3_wget_approve.txt" \
  "$PYTHON_BIN" tool_loop_agent.py \
  --confirm-policy always \
  --prompt-file evidence/prompts/step3_prompt.txt

echo "===== STEP 3 (deny) ====="
run_case "step3_wget_deny.txt" \
  "$PYTHON_BIN" tool_loop_agent.py \
  --confirm-policy never \
  --prompt-file evidence/prompts/step3_prompt.txt

echo "===== STEP 4 ====="
rm -f "$DB_FILE"
run_case "step4_full_test.txt" \
  "$PYTHON_BIN" tool_loop_agent.py \
  --confirm-policy always \
  --prompt-file evidence/prompts/step4_prompt.txt

run_case "step4_sqlite_verify.txt" \
  sqlite3 "$DB_FILE" "SELECT * FROM users;"

echo "===== STEP 5 (bad url) ====="
run_case "step5_bad_url.txt" \
  "$PYTHON_BIN" tool_loop_agent.py \
  --confirm-policy always \
  --prompt-file evidence/prompts/step5_bad_url_prompt.txt

echo "===== STEP 5 (invalid sql) ====="
run_case "step5_invalid_sql.txt" \
  "$PYTHON_BIN" tool_loop_agent.py \
  --confirm-policy always \
  --prompt-file evidence/prompts/step5_invalid_sql_prompt.txt
