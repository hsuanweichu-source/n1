# n1

可運行的「多代理小說生成」MVP 原型。

## 快速開始

```bash
python novel_system.py demo
```

會依序執行：
1. 建立專案
2. 匯入參考資料（Research Agent）
3. 產生多版大綱（Outline Planner）
4. 拆成章節計畫（Chapter Architect）
5. 生成章節草稿（Writer Agent）
6. 輸出修訂建議（Revision Agent）

資料會寫入 `data/novel_db.json`。

## 互動模式

```bash
python novel_system.py chat
```

互動範例：
- `create demo 霧城迴聲 失憶偵探追查失蹤案`
- `請先收集資料：港口黑幫、大霧城市`
- `請產生大綱`
- `請拆章節`
- `請開始寫第一章`
- `請修訂第一章`
