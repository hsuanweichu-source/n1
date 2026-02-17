#!/usr/bin/env bash
set -euo pipefail

PROJECT="test_$(date +%s)"
BRIEF="測試用故事：迷霧港口與失落地圖"
REF="/tmp/${PROJECT}.txt"

cat > "$REF" <<'TXT'
主角在港口追查失落地圖，與舊友重逢後發現背後陰謀。
TXT

python3 novel_system.py init-project --name "$PROJECT" --brief "$BRIEF" >/dev/null
python3 novel_system.py add-source --project "$PROJECT" --title t --file "$REF" >/dev/null
python3 novel_system.py gen-outline --project "$PROJECT" --count 6 >/dev/null
python3 novel_system.py plan-chapters --project "$PROJECT" --option 1 --chapters 2 --target-chars 1200 --sections 4 >/dev/null
python3 novel_system.py write-chapter --project "$PROJECT" --chapter 1 >/dev/null
python3 novel_system.py revise-chapter --project "$PROJECT" --chapter 1 >/dev/null

DRAFT="output/${PROJECT}_chapter_1_draft.txt"
REV="output/${PROJECT}_chapter_1_revised.txt"

[[ -f "$DRAFT" ]]
[[ -f "$REV" ]]

python3 novel_system.py status --project "$PROJECT" | rg "chapter_no|selected_outline|專案" >/dev/null

echo "smoke test passed: $PROJECT"
