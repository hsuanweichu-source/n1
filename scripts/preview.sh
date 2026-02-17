#!/usr/bin/env bash
set -euo pipefail

PROJECT_NAME="preview_$(date +%s)"
BRIEF="近未來台北，一位聲音工程師發現錄音裡藏著失蹤案件線索。"
REF_FILE="/tmp/${PROJECT_NAME}_ref.txt"

echo "[1/7] 建立測試參考資料..."
cat > "$REF_FILE" <<'TXT'
城市裡的每一段噪音都可能是訊號，關鍵在你如何聆聽。
主角在追查中逐步揭露龐大利益集團，並面對與同伴的信任裂痕。
TXT

echo "[2/7] 初始化專案: $PROJECT_NAME"
python3 novel_system.py init-project --name "$PROJECT_NAME" --brief "$BRIEF"

echo "[3/7] 匯入參考資料"
python3 novel_system.py add-source --project "$PROJECT_NAME" --title "preview_ref" --file "$REF_FILE" --author "system"

echo "[4/7] 產生大綱"
python3 novel_system.py gen-outline --project "$PROJECT_NAME" --count 6 > /tmp/${PROJECT_NAME}_outlines.jsonl

echo "[5/7] 拆章規劃"
python3 novel_system.py plan-chapters --project "$PROJECT_NAME" --option 2 --chapters 2 --target-chars 1500 --sections 4 > /tmp/${PROJECT_NAME}_plan.json

echo "[6/7] 生成與修訂第一章"
python3 novel_system.py write-chapter --project "$PROJECT_NAME" --chapter 1
python3 novel_system.py revise-chapter --project "$PROJECT_NAME" --chapter 1

echo "[7/7] 顯示狀態"
python3 novel_system.py status --project "$PROJECT_NAME"

echo "完成。可查看 output/${PROJECT_NAME}_chapter_1_draft.txt 與 output/${PROJECT_NAME}_chapter_1_revised.txt"
