#!/usr/bin/env python3
"""Multi-agent novel writing MVP (CLI).

This program implements a runnable version of the PRD:
- Research agent: ingest references into sqlite + chunks
- Outline planner: generate multiple outline options
- Chapter architect: split outline into chapters/sections with character budget
- Writer agent: generate chapter draft section-by-section with budget control
- Revision editor: provide revision suggestions and an edited draft
- Router/orchestrator: exposed via CLI subcommands
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

DB_PATH = Path("data/novel_system.db")


@dataclass
class OutlineOption:
    option_id: int
    title: str
    premise: str
    conflict: str
    turning_point: str
    ending_tone: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "option_id": self.option_id,
            "title": self.title,
            "premise": self.premise,
            "conflict": self.conflict,
            "turning_point": self.turning_point,
            "ending_tone": self.ending_tone,
        }


class Database:
    def __init__(self, db_path: Path = DB_PATH) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                brief TEXT NOT NULL,
                selected_outline INTEGER,
                chapter_plan_json TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                author TEXT,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id)
            );

            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER NOT NULL,
                project_id INTEGER NOT NULL,
                chunk_text TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(source_id) REFERENCES sources(id),
                FOREIGN KEY(project_id) REFERENCES projects(id)
            );

            CREATE TABLE IF NOT EXISTS outlines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                option_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id)
            );

            CREATE TABLE IF NOT EXISTS chapters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                chapter_no INTEGER NOT NULL,
                draft TEXT,
                revised_draft TEXT,
                review_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(project_id, chapter_no),
                FOREIGN KEY(project_id) REFERENCES projects(id)
            );
            """
        )
        self.conn.commit()

    def now(self) -> str:
        return dt.datetime.now().isoformat(timespec="seconds")


class ResearchAgent:
    def __init__(self, db: Database) -> None:
        self.db = db

    def ingest_source(self, project_id: int, title: str, content: str, author: str | None = None) -> int:
        cur = self.db.conn.execute(
            "INSERT INTO sources(project_id,title,author,content,created_at) VALUES(?,?,?,?,?)",
            (project_id, title, author, content, self.db.now()),
        )
        source_id = int(cur.lastrowid)
        for chunk in self._chunk_text(content):
            self.db.conn.execute(
                "INSERT INTO chunks(source_id,project_id,chunk_text,created_at) VALUES(?,?,?,?)",
                (source_id, project_id, chunk, self.db.now()),
            )
        self.db.conn.commit()
        return source_id

    def _chunk_text(self, text: str, max_chars: int = 350) -> Iterable[str]:
        paragraphs = [p.strip() for p in re.split(r"\n+", text) if p.strip()]
        if not paragraphs:
            paragraphs = [text.strip()]
        buf = ""
        for p in paragraphs:
            if len(buf) + len(p) + 1 <= max_chars:
                buf = f"{buf}\n{p}".strip()
            else:
                if buf:
                    yield buf
                buf = p
        if buf:
            yield buf

    def retrieve(self, project_id: int, query: str, top_k: int = 5) -> list[str]:
        # simple keyword overlap retrieval
        tokens = {t for t in re.split(r"\W+", query) if t}
        rows = self.db.conn.execute(
            "SELECT chunk_text FROM chunks WHERE project_id=?", (project_id,)
        ).fetchall()
        scored: list[tuple[int, str]] = []
        for r in rows:
            chunk = r["chunk_text"]
            score = sum(1 for t in tokens if t and t in chunk)
            scored.append((score, chunk))
        scored.sort(key=lambda x: x[0], reverse=True)
        selected = [c for s, c in scored[:top_k] if s > 0]
        if selected:
            return selected
        return [r["chunk_text"] for r in rows[:top_k]]


class OutlinePlanner:
    def generate_options(self, brief: str, n: int = 6) -> list[OutlineOption]:
        arcs = [
            ("復仇與救贖", "主角背負舊案", "舊敵再現", "放下執念", "溫暖收束"),
            ("成長與代價", "天賦少年踏入新世界", "理想與現實衝突", "失去摯友", "苦澀但成熟"),
            ("陰謀與真相", "平靜小鎮暗藏祕密", "權力集團追殺", "揭露核心謊言", "開放式結尾"),
            ("愛與責任", "兩位主角共同冒險", "價值觀分歧", "危機中互相理解", "希望感結尾"),
            ("文明存亡", "世界資源枯竭", "各陣營博弈", "主角選擇犧牲", "史詩感落幕"),
            ("懸疑追查", "離奇案件連環發生", "線索被刻意誤導", "反派其實是熟人", "反轉收尾"),
        ]
        options: list[OutlineOption] = []
        for i in range(1, n + 1):
            title, premise, conflict, turning, ending = arcs[(i - 1) % len(arcs)]
            options.append(
                OutlineOption(
                    option_id=i,
                    title=f"方案{i}：{title}",
                    premise=f"基於你的構想「{brief[:36]}...」，設定為：{premise}。",
                    conflict=conflict,
                    turning_point=turning,
                    ending_tone=ending,
                )
            )
        return options


class ChapterArchitect:
    def build_plan(
        self,
        outline: OutlineOption,
        chapters: int = 3,
        chapter_target_chars: int = 5500,
        sections_per_chapter: int = 8,
    ) -> list[dict[str, Any]]:
        section_target = max(300, chapter_target_chars // sections_per_chapter)
        plan: list[dict[str, Any]] = []
        for c in range(1, chapters + 1):
            sections = []
            for s in range(1, sections_per_chapter + 1):
                sections.append(
                    {
                        "section_no": s,
                        "goal": f"第{c}章第{s}節：推進{outline.conflict}，並埋入後續伏筆。",
                        "target_chars": section_target,
                    }
                )
            plan.append(
                {
                    "chapter_no": c,
                    "chapter_goal": f"圍繞 {outline.title}，完成{outline.turning_point}前的關鍵推進。",
                    "target_chars": chapter_target_chars,
                    "sections": sections,
                }
            )
        return plan


class WriterAgent:
    def write_chapter(self, chapter_plan: dict[str, Any], retrieved_chunks: list[str], brief: str) -> str:
        parts: list[str] = []
        context_line = "；".join(c[:60].replace("\n", " ") for c in retrieved_chunks[:3])
        for sec in chapter_plan["sections"]:
            sec_header = f"\n### 第{chapter_plan['chapter_no']}章-第{sec['section_no']}節\n"
            body = self._generate_section(sec["goal"], sec["target_chars"], brief, context_line)
            parts.append(sec_header + body)
        text = "\n".join(parts)
        return self._enforce_target(text, chapter_plan["target_chars"]) 

    def _generate_section(self, goal: str, target_chars: int, brief: str, context_line: str) -> str:
        seeds = [
            f"場景開場緊扣需求：{brief[:40]}。",
            f"本節目標是{goal}。",
            f"參考片段摘要：{context_line or '目前無外部片段，採原創推進'}。",
            "角色的選擇帶出新的風險，並讓人物關係產生張力。",
            "敘事節奏在對話與行動之間切換，避免只講結果不講過程。",
            "尾段留下小型懸念，確保下一節有清楚接續動機。",
        ]
        out = []
        i = 0
        while len("".join(out)) < target_chars:
            out.append(seeds[i % len(seeds)])
            out.append("\n")
            i += 1
        return "".join(out)

    def _enforce_target(self, text: str, target_chars: int) -> str:
        if len(text) > target_chars + 400:
            return text[: target_chars + 400]
        if len(text) < target_chars:
            filler = "\n" + "情節補強：主角重新審視線索，並以新的行動回應前文衝突。"
            while len(text) < target_chars:
                text += filler
        return text


class RevisionEditor:
    def review(self, draft: str) -> dict[str, Any]:
        issues = []
        if "參考片段摘要：目前無外部片段" in draft:
            issues.append("缺少參考資料引用，可先補充素材後重寫。")
        if draft.count("懸念") < 2:
            issues.append("章節懸念偏少，建議在章末增加反轉或未解事件。")
        if len(draft) < 4500:
            issues.append("字數偏低，建議增加場景描寫與角色內心活動。")
        revised = draft.replace("需求", "故事需求").replace("風險", "風險與代價")
        return {
            "issue_count": len(issues),
            "issues": issues,
            "summary": "修訂完成，已優化措辭一致性與敘事語氣。",
            "revised_draft": revised,
        }


class NovelSystem:
    def __init__(self, db: Database) -> None:
        self.db = db
        self.research = ResearchAgent(db)
        self.outline_planner = OutlinePlanner()
        self.architect = ChapterArchitect()
        self.writer = WriterAgent()
        self.editor = RevisionEditor()

    def create_project(self, name: str, brief: str) -> int:
        cur = self.db.conn.execute(
            "INSERT INTO projects(name,brief,created_at) VALUES(?,?,?)",
            (name, brief, self.db.now()),
        )
        self.db.conn.commit()
        return int(cur.lastrowid)

    def get_project(self, name: str) -> sqlite3.Row:
        row = self.db.conn.execute("SELECT * FROM projects WHERE name=?", (name,)).fetchone()
        if not row:
            raise ValueError(f"找不到專案: {name}")
        return row

    def save_outlines(self, project_id: int, options: list[OutlineOption]) -> None:
        self.db.conn.execute("DELETE FROM outlines WHERE project_id=?", (project_id,))
        for opt in options:
            self.db.conn.execute(
                "INSERT INTO outlines(project_id,option_json,created_at) VALUES(?,?,?)",
                (project_id, json.dumps(opt.to_dict(), ensure_ascii=False), self.db.now()),
            )
        self.db.conn.commit()

    def list_outlines(self, project_id: int) -> list[OutlineOption]:
        rows = self.db.conn.execute(
            "SELECT option_json FROM outlines WHERE project_id=? ORDER BY id", (project_id,)
        ).fetchall()
        result = []
        for r in rows:
            data = json.loads(r["option_json"])
            result.append(OutlineOption(**data))
        return result

    def select_outline_and_plan(
        self, project_id: int, option_id: int, chapters: int, target_chars: int, sections: int
    ) -> list[dict[str, Any]]:
        options = self.list_outlines(project_id)
        selected = next((o for o in options if o.option_id == option_id), None)
        if not selected:
            raise ValueError(f"outline option {option_id} 不存在")
        plan = self.architect.build_plan(selected, chapters, target_chars, sections)
        self.db.conn.execute(
            "UPDATE projects SET selected_outline=?, chapter_plan_json=? WHERE id=?",
            (option_id, json.dumps(plan, ensure_ascii=False), project_id),
        )
        self.db.conn.commit()
        return plan

    def write_chapter(self, project_id: int, chapter_no: int) -> str:
        row = self.db.conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if not row or not row["chapter_plan_json"]:
            raise ValueError("尚未建立章節計畫")
        plan = json.loads(row["chapter_plan_json"])
        chapter_plan = next((c for c in plan if c["chapter_no"] == chapter_no), None)
        if not chapter_plan:
            raise ValueError(f"找不到章節 {chapter_no}")
        contexts = self.research.retrieve(project_id, row["brief"], top_k=5)
        draft = self.writer.write_chapter(chapter_plan, contexts, row["brief"])
        now = self.db.now()
        self.db.conn.execute(
            """
            INSERT INTO chapters(project_id,chapter_no,draft,created_at,updated_at)
            VALUES(?,?,?,?,?)
            ON CONFLICT(project_id,chapter_no)
            DO UPDATE SET draft=excluded.draft, updated_at=excluded.updated_at
            """,
            (project_id, chapter_no, draft, now, now),
        )
        self.db.conn.commit()
        return draft

    def revise_chapter(self, project_id: int, chapter_no: int) -> dict[str, Any]:
        row = self.db.conn.execute(
            "SELECT * FROM chapters WHERE project_id=? AND chapter_no=?", (project_id, chapter_no)
        ).fetchone()
        if not row or not row["draft"]:
            raise ValueError("尚未有章節草稿，請先 write-chapter")
        review = self.editor.review(row["draft"])
        self.db.conn.execute(
            "UPDATE chapters SET revised_draft=?, review_json=?, updated_at=? WHERE id=?",
            (review["revised_draft"], json.dumps(review, ensure_ascii=False), self.db.now(), row["id"]),
        )
        self.db.conn.commit()
        return review


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="可運行的多代理小說系統 MVP")
    sp = p.add_subparsers(dest="command", required=True)

    init_p = sp.add_parser("init-project")
    init_p.add_argument("--name", required=True)
    init_p.add_argument("--brief", required=True)

    source_p = sp.add_parser("add-source")
    source_p.add_argument("--project", required=True)
    source_p.add_argument("--title", required=True)
    source_p.add_argument("--file", required=True)
    source_p.add_argument("--author")

    outline_p = sp.add_parser("gen-outline")
    outline_p.add_argument("--project", required=True)
    outline_p.add_argument("--count", type=int, default=6)

    plan_p = sp.add_parser("plan-chapters")
    plan_p.add_argument("--project", required=True)
    plan_p.add_argument("--option", type=int, required=True)
    plan_p.add_argument("--chapters", type=int, default=3)
    plan_p.add_argument("--target-chars", type=int, default=5500)
    plan_p.add_argument("--sections", type=int, default=8)

    write_p = sp.add_parser("write-chapter")
    write_p.add_argument("--project", required=True)
    write_p.add_argument("--chapter", type=int, required=True)

    rev_p = sp.add_parser("revise-chapter")
    rev_p.add_argument("--project", required=True)
    rev_p.add_argument("--chapter", type=int, required=True)

    status_p = sp.add_parser("status")
    status_p.add_argument("--project", required=True)

    demo_p = sp.add_parser("demo-run")
    demo_p.add_argument("--project", default="demo")

    return p.parse_args()


def main() -> None:
    args = parse_args()
    system = NovelSystem(Database())

    if args.command == "init-project":
        pid = system.create_project(args.name, args.brief)
        print(f"已建立專案 #{pid}: {args.name}")
        return

    if args.command == "add-source":
        p = system.get_project(args.project)
        content = Path(args.file).read_text(encoding="utf-8")
        sid = system.research.ingest_source(p["id"], args.title, content, args.author)
        print(f"已匯入資料 source_id={sid}")
        return

    if args.command == "gen-outline":
        p = system.get_project(args.project)
        options = system.outline_planner.generate_options(p["brief"], n=args.count)
        system.save_outlines(p["id"], options)
        for opt in options:
            print(json.dumps(opt.to_dict(), ensure_ascii=False, indent=2))
        return

    if args.command == "plan-chapters":
        p = system.get_project(args.project)
        plan = system.select_outline_and_plan(
            p["id"], args.option, args.chapters, args.target_chars, args.sections
        )
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return

    if args.command == "write-chapter":
        p = system.get_project(args.project)
        draft = system.write_chapter(p["id"], args.chapter)
        out = Path(f"output/{args.project}_chapter_{args.chapter}_draft.txt")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(draft, encoding="utf-8")
        print(f"草稿已輸出: {out}")
        return

    if args.command == "revise-chapter":
        p = system.get_project(args.project)
        review = system.revise_chapter(p["id"], args.chapter)
        out = Path(f"output/{args.project}_chapter_{args.chapter}_revised.txt")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(review["revised_draft"], encoding="utf-8")
        print(json.dumps(review, ensure_ascii=False, indent=2))
        print(f"修訂稿已輸出: {out}")
        return

    if args.command == "status":
        p = system.get_project(args.project)
        chapter_rows = system.db.conn.execute(
            "SELECT chapter_no, LENGTH(draft) AS draft_len, LENGTH(revised_draft) AS revised_len, updated_at FROM chapters WHERE project_id=? ORDER BY chapter_no",
            (p["id"],),
        ).fetchall()
        print(f"專案: {p['name']}")
        print(f"brief: {p['brief']}")
        print(f"selected_outline: {p['selected_outline']}")
        print("chapters:")
        for row in chapter_rows:
            print(dict(row))
        return

    if args.command == "demo-run":
        name = args.project
        brief = "末日後的台北，女主角帶著失憶線索尋找家人，並捲入城市能源陰謀。"
        try:
            system.get_project(name)
        except ValueError:
            system.create_project(name, brief)
        p = system.get_project(name)
        demo_source = (
            "在破碎的都市中，生存不只取決於資源，還取決於你願意信任誰。\n"
            "每一次選擇都會改變陣營關係，並讓真相更接近或更遙遠。"
        )
        system.research.ingest_source(p["id"], "demo_ref", demo_source, "system")
        options = system.outline_planner.generate_options(p["brief"], 6)
        system.save_outlines(p["id"], options)
        system.select_outline_and_plan(p["id"], option_id=3, chapters=3, target_chars=1200, sections=4)
        draft = system.write_chapter(p["id"], 1)
        review = system.revise_chapter(p["id"], 1)
        out = Path("output/demo_chapter_1_revised.txt")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(review["revised_draft"], encoding="utf-8")
        print(f"Demo 完成，草稿字元數={len(draft)}，修訂問題數={review['issue_count']}，輸出={out}")
        return


if __name__ == "__main__":
    main()
