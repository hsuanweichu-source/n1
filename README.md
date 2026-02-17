# n1 - Multi-Agent Novel Writer (Code MVP)

這個 repository 提供**可直接執行的程式碼**，用 CLI 方式跑多代理小說寫作流程。

## 你最關心的：怎麼知道程式怎麼用？
直接看這三種入口：

1. **指令說明**
```bash
python3 novel_system.py --help
```

2. **一鍵預覽（測試版本）**
```bash
bash scripts/preview.sh
```
會自動建立一個測試專案，跑完「建專案 → 匯入資料 → 產生大綱 → 拆章 → 寫作 → 修訂 → 狀態檢查」，並產生輸出檔案。

3. **自動化 smoke test**
```bash
bash tests/test_smoke.sh
```
會檢查整體流程能否成功跑完。

---


## 本機網頁版預覽

```bash
bash scripts/run_web_preview.sh 127.0.0.1 8000
```

啟動後打開：`http://127.0.0.1:8000`

- 點「執行 Demo」可一鍵產生測試章節
- 點「查詢」可看該專案章節狀態
- 頁面下方會列出近期輸出檔案


若你遇到「空白頁」，請依序檢查：
1. 你打開的是 `http://127.0.0.1:8000`（不是本機檔案路徑）。
2. 服務有啟動（終端要持續顯示 running）。
3. 檢查健康檢查：`http://127.0.0.1:8000/health` 應顯示 `ok`。
4. 若執行流程失敗，頁面會直接顯示「最近錯誤」堆疊訊息。

## 功能
- 專案建立
- 參考資料匯入與切塊（Research）
- 多版大綱產生（Outline）
- 章節拆分與字數目標（Chapter Planning）
- 章節草稿生成（Writer）
- 修訂建議與修訂稿輸出（Revision）

## 快速開始

```bash
python3 novel_system.py --help
python3 novel_system.py demo-run
python3 novel_system.py status --project demo
```

執行 `demo-run` 後會輸出：
- `output/demo_chapter_1_revised.txt`

## 手動流程

```bash
# 1) 建立專案
python3 novel_system.py init-project --name mynovel --brief "你的故事大綱"

# 2) 匯入參考資料（txt）
python3 novel_system.py add-source --project mynovel --title ref1 --file ./reference.txt --author "某作者"

# 3) 生成多版大綱
python3 novel_system.py gen-outline --project mynovel --count 6

# 4) 選擇大綱並拆章
python3 novel_system.py plan-chapters --project mynovel --option 2 --chapters 3 --target-chars 5500 --sections 8

# 5) 生成章節草稿
python3 novel_system.py write-chapter --project mynovel --chapter 1

# 6) 修訂章節
python3 novel_system.py revise-chapter --project mynovel --chapter 1

# 7) 查看專案狀態
python3 novel_system.py status --project mynovel
```

## 輸出位置
- 草稿：`output/<project>_chapter_<n>_draft.txt`
- 修訂稿：`output/<project>_chapter_<n>_revised.txt`
- 資料庫：`data/novel_system.db`
