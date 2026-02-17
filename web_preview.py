#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from novel_system import Database, NovelSystem


def run_demo(system: NovelSystem, project: str) -> str:
    brief = "末日後的台北，女主角帶著失憶線索尋找家人，並捲入城市能源陰謀。"
    try:
        system.get_project(project)
    except ValueError:
        system.create_project(project, brief)

    p = system.get_project(project)
    demo_source = (
        "在破碎的都市中，生存不只取決於資源，還取決於你願意信任誰。\n"
        "每一次選擇都會改變陣營關係，並讓真相更接近或更遙遠。"
    )
    system.research.ingest_source(p["id"], "demo_ref", demo_source, "web")
    options = system.outline_planner.generate_options(p["brief"], 6)
    system.save_outlines(p["id"], options)
    system.select_outline_and_plan(p["id"], option_id=3, chapters=3, target_chars=1200, sections=4)
    draft = system.write_chapter(p["id"], 1)
    review = system.revise_chapter(p["id"], 1)
    out = Path(f"output/{project}_chapter_1_revised.txt")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(review["revised_draft"], encoding="utf-8")
    return f"Demo 完成：project={project}, draft_chars={len(draft)}, issues={review['issue_count']}, output={out}"


def fetch_status(system: NovelSystem, project: str) -> str:
    p = system.get_project(project)
    rows = system.db.conn.execute(
        "SELECT chapter_no, LENGTH(draft) AS draft_len, LENGTH(revised_draft) AS revised_len, updated_at FROM chapters WHERE project_id=? ORDER BY chapter_no",
        (p["id"],),
    ).fetchall()
    return json.dumps(
        {
            "project": p["name"],
            "brief": p["brief"],
            "selected_outline": p["selected_outline"],
            "chapters": [dict(r) for r in rows],
        },
        ensure_ascii=False,
        indent=2,
    )


def make_handler(system: NovelSystem):
    class Handler(BaseHTTPRequestHandler):
        last_error = ""

        def _read_post(self) -> dict[str, str]:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            parsed = parse_qs(body)
            return {k: v[0] for k, v in parsed.items()}

        def _render(self, message: str = "", status_text: str = "") -> None:
            output_files = sorted(Path("output").glob("*_chapter_1_revised.txt"))
            output_html = "".join(
                f"<li><code>{html.escape(str(p))}</code></li>" for p in output_files[-10:]
            ) or "<li>目前沒有輸出檔案，請先按「執行 Demo」。</li>"

            error_block = (
                f"<div class='card err'><h2>最近錯誤</h2><pre>{html.escape(self.last_error)}</pre></div>"
                if self.last_error
                else ""
            )

            page = f"""<!doctype html>
<html lang='zh-Hant'>
<head>
  <meta charset='utf-8'>
  <meta name='viewport' content='width=device-width,initial-scale=1'>
  <title>Novel System 本機預覽</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 920px; margin: 2rem auto; padding: 0 1rem; color: #0f172a; }}
    .card {{ border: 1px solid #ddd; border-radius: 10px; padding: 1rem; margin-bottom: 1rem; background: #fff; }}
    .err {{ border-color: #ef4444; background: #fef2f2; }}
    button {{ background: #2563eb; color: #fff; border: none; border-radius: 8px; padding: .6rem 1rem; cursor: pointer; }}
    input {{ padding: .5rem; width: 280px; }}
    pre {{ background: #f8fafc; padding: 1rem; border-radius: 8px; overflow-x: auto; white-space: pre-wrap; }}
    .ok {{ color: #166534; }}
    .hint {{ color: #334155; font-size: 14px; }}
  </style>
</head>
<body>
  <h1>Multi-Agent Novel Writer（本機網頁版預覽）</h1>
  <p class='hint'>如果看到空白頁，請確認你是開啟 <code>http://127.0.0.1:8000</code>，且 web_preview.py 正在執行中。</p>
  <div class='card'>
    <h2>一鍵 Demo</h2>
    <form method='post' action='/demo'>
      <label>專案名稱：</label>
      <input name='project' value='demo_web' />
      <button type='submit'>執行 Demo</button>
    </form>
    <p class='ok'>{html.escape(message)}</p>
  </div>

  <div class='card'>
    <h2>查詢專案狀態</h2>
    <form method='post' action='/status'>
      <label>專案名稱：</label>
      <input name='project' value='demo_web' />
      <button type='submit'>查詢</button>
    </form>
    <pre>{html.escape(status_text)}</pre>
  </div>

  <div class='card'>
    <h2>近期修訂稿檔案</h2>
    <ul>{output_html}</ul>
  </div>
  {error_block}
</body>
</html>"""

            data = page.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == "/health":
                data = b"ok"
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            if path != "/":
                self.send_error(404)
                return
            self._render(status_text="可先按『執行 Demo』，再按『查詢』查看章節狀態。")

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            try:
                form = self._read_post()
                project = (form.get("project") or "demo_web").strip() or "demo_web"
                if path == "/demo":
                    msg = run_demo(system, project)
                    self.last_error = ""
                    self._render(message=msg)
                    return
                if path == "/status":
                    status_text = fetch_status(system, project)
                    self.last_error = ""
                    self._render(status_text=status_text)
                    return
                self.send_error(404)
            except Exception:  # noqa: BLE001
                self.last_error = traceback.format_exc()
                self._render(message="執行失敗，請查看下方『最近錯誤』")

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description="Novel System 本機網頁預覽")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    system = NovelSystem(Database())
    server = ThreadingHTTPServer((args.host, args.port), make_handler(system))
    print(f"Web preview running: http://{args.host}:{args.port}")
    print("Health check: /health")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
