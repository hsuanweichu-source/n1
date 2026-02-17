#!/usr/bin/env python3
"""Multi-agent novel writing system (MVP runnable prototype).

Usage:
  python novel_system.py chat
  python novel_system.py demo
"""

from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


DATA_DIR = Path("data")
DB_FILE = DATA_DIR / "novel_db.json"


@dataclass
class Project:
    id: str
    title: str
    brief: str
    target_chapter_words: int = 5500


@dataclass
class ChapterPlan:
    chapter_no: int
    objective: str
    section_count: int
    section_word_target: int


class JsonStore:
    def __init__(self, db_file: Path = DB_FILE) -> None:
        self.db_file = db_file
        self.db_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.db_file.exists():
            self._write(
                {
                    "projects": {},
                    "references": {},
                    "outlines": {},
                    "chapter_plans": {},
                    "chapter_drafts": {},
                }
            )

    def _read(self) -> dict[str, Any]:
        return json.loads(self.db_file.read_text(encoding="utf-8"))

    def _write(self, payload: dict[str, Any]) -> None:
        self.db_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def get(self, key: str) -> Any:
        return self._read().get(key)

    def set(self, key: str, value: Any) -> None:
        db = self._read()
        db[key] = value
        self._write(db)


class ResearchAgent:
    def __init__(self, store: JsonStore):
        self.store = store

    def ingest_reference(self, project_id: str, source_name: str, text: str) -> int:
        refs = self.store.get("references")
        refs.setdefault(project_id, [])
        chunks = self._chunk_text(text)
        refs[project_id].append({"source": source_name, "chunks": chunks})
        self.store.set("references", refs)
        return len(chunks)

    def retrieve(self, project_id: str, query: str, top_k: int = 3) -> list[str]:
        refs = self.store.get("references").get(project_id, [])
        scored: list[tuple[int, str]] = []
        keywords = set(re.findall(r"[\w\u4e00-\u9fff]+", query.lower()))
        for ref in refs:
            for chunk in ref["chunks"]:
                tokens = set(re.findall(r"[\w\u4e00-\u9fff]+", chunk.lower()))
                score = len(tokens & keywords)
                if score > 0:
                    scored.append((score, chunk))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored[:top_k]]

    @staticmethod
    def _chunk_text(text: str, max_len: int = 400) -> list[str]:
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
        chunks: list[str] = []
        buffer = ""
        for p in paragraphs:
            if len(buffer) + len(p) <= max_len:
                buffer += ("\n" if buffer else "") + p
            else:
                if buffer:
                    chunks.append(buffer)
                buffer = p
        if buffer:
            chunks.append(buffer)
        return chunks


class OutlinePlannerAgent:
    def generate_candidates(self, brief: str, count: int = 5) -> list[str]:
        archetypes = [
            "英雄旅程型", "雙主角對照型", "懸疑解謎型", "群像成長型", "倒敘真相型", "黑化救贖型"
        ]
        candidates = []
        for i in range(count):
            mode = archetypes[i % len(archetypes)]
            candidates.append(
                f"方案{i+1}（{mode}）\n"
                f"- 核心命題：{brief}\n"
                f"- 起：建立主角困境與目標\n"
                f"- 承：衝突升級，角色價值觀受挑戰\n"
                f"- 轉：關鍵真相揭露或關係崩解\n"
                f"- 合：主角做出代價選擇並收束主題"
            )
        return candidates


class ChapterArchitectAgent:
    def build_plan(self, outline: str, chapter_count: int, target_chapter_words: int) -> list[ChapterPlan]:
        per_section = 850
        section_count = max(4, math.ceil(target_chapter_words / per_section))
        plans: list[ChapterPlan] = []
        for no in range(1, chapter_count + 1):
            plans.append(
                ChapterPlan(
                    chapter_no=no,
                    objective=f"依照大綱推進第 {no} 章，聚焦主要衝突與角色選擇。",
                    section_count=section_count,
                    section_word_target=math.ceil(target_chapter_words / section_count),
                )
            )
        return plans


class WriterAgent:
    def write_chapter(
        self,
        project_title: str,
        chapter_plan: ChapterPlan,
        outline: str,
        reference_chunks: list[str],
    ) -> str:
        sections = []
        for section_no in range(1, chapter_plan.section_count + 1):
            seed = reference_chunks[(section_no - 1) % len(reference_chunks)] if reference_chunks else ""
            paragraph = self._compose_section(
                project_title=project_title,
                chapter_no=chapter_plan.chapter_no,
                section_no=section_no,
                objective=chapter_plan.objective,
                outline=outline,
                reference=seed,
                target_words=chapter_plan.section_word_target,
            )
            sections.append(paragraph)
        draft = "\n\n".join(sections)
        return draft

    def _compose_section(
        self,
        project_title: str,
        chapter_no: int,
        section_no: int,
        objective: str,
        outline: str,
        reference: str,
        target_words: int,
    ) -> str:
        head = (
            f"【{project_title}｜第{chapter_no}章-第{section_no}節】\n"
            f"本節目標：{objective}\n"
            f"情節基礎：{outline.splitlines()[0]}"
        )
        ref_text = f"\n參考片段：{reference[:120]}" if reference else "\n參考片段：無"
        base = (
            "\n夜色壓在街道上，角色沿著目標前進，卻在每一步都被過往的選擇牽制。"
            "衝突不只來自外界，更多來自他/她內心尚未和解的缺口。"
            "當新的線索出現，局勢被迫翻轉，人物必須在信任與背叛之間作出判斷。"
        )
        body = head + ref_text + base
        while self._count_words_zh(body) < target_words:
            body += "他回想起最初的承諾，知道再退一步就會失去真正重要的人。"
        return body

    @staticmethod
    def _count_words_zh(text: str) -> int:
        # Simple proxy for Chinese length control: count CJK chars + latin words.
        cjk = len(re.findall(r"[\u4e00-\u9fff]", text))
        latin = len(re.findall(r"\b\w+\b", text))
        return cjk + latin


class RevisionAgent:
    def review(self, chapter_text: str) -> dict[str, Any]:
        issues = []
        if "參考片段：無" in chapter_text:
            issues.append("建議補充參考資料，提升細節真實性。")
        if chapter_text.count("衝突") < 2:
            issues.append("衝突密度偏低，可增加對抗場景。")
        if len(chapter_text) < 4000:
            issues.append("字數偏少，建議加深場景描寫與心理活動。")
        return {
            "score": max(60, 100 - len(issues) * 10),
            "issues": issues,
            "summary": "整體可讀性良好，建議針對節奏與細節再優化。" if issues else "章節完整，敘事連貫。",
        }


class RouterAgent:
    def classify(self, user_text: str) -> str:
        text = user_text.lower()
        if any(k in text for k in ["參考", "收集", "資料", "爬", "research"]):
            return "research"
        if any(k in text for k in ["大綱", "outline", "方向"]):
            return "outline"
        if any(k in text for k in ["章節", "拆章", "chapter", "分段"]):
            return "plan"
        if any(k in text for k in ["寫", "生成", "draft"]):
            return "write"
        if any(k in text for k in ["修訂", "修改", "review"]):
            return "revise"
        return "unknown"


class NovelSystem:
    def __init__(self) -> None:
        self.store = JsonStore()
        self.router = RouterAgent()
        self.research = ResearchAgent(self.store)
        self.outline = OutlinePlannerAgent()
        self.architect = ChapterArchitectAgent()
        self.writer = WriterAgent()
        self.revision = RevisionAgent()

    def create_project(self, project_id: str, title: str, brief: str, target_words: int = 5500) -> None:
        projects = self.store.get("projects")
        projects[project_id] = asdict(Project(project_id, title, brief, target_words))
        self.store.set("projects", projects)

    def run_demo(self) -> None:
        project_id = "demo"
        self.create_project(project_id, "霧城迴聲", "失憶偵探追查連環失蹤案，逐步揭開自己的過去")
        chunks = self.research.ingest_reference(
            project_id,
            "sample_reference.txt",
            "城市常年大霧，港口區是非法交易中心。\n主角曾是警探，因事故失憶。\n反派擅長操縱輿論與記憶。",
        )
        print(f"[Research] 收錄參考片段 {chunks} 筆")

        candidates = self.outline.generate_candidates("失憶偵探追查連環失蹤案")
        chosen = candidates[0]
        outlines = self.store.get("outlines")
        outlines[project_id] = {"chosen": chosen, "candidates": candidates}
        self.store.set("outlines", outlines)
        print("[Outline] 已產生候選大綱 5 份，預設選方案 1")

        projects = self.store.get("projects")
        target = projects[project_id]["target_chapter_words"]
        plans = self.architect.build_plan(chosen, chapter_count=3, target_chapter_words=target)
        chapter_plans = self.store.get("chapter_plans")
        chapter_plans[project_id] = [asdict(p) for p in plans]
        self.store.set("chapter_plans", chapter_plans)
        print("[Plan] 已拆成 3 章")

        refs = self.research.retrieve(project_id, "主角 失憶 警探")
        chapter_text = self.writer.write_chapter("霧城迴聲", plans[0], chosen, refs)
        chapter_drafts = self.store.get("chapter_drafts")
        chapter_drafts.setdefault(project_id, {})
        chapter_drafts[project_id]["1"] = chapter_text
        self.store.set("chapter_drafts", chapter_drafts)
        print(f"[Write] 第 1 章草稿完成，長度 {len(chapter_text)} 字元")

        report = self.revision.review(chapter_text)
        print(f"[Revision] 分數={report['score']}，建議={report['issues'] or '無'}")

    def chat(self) -> None:
        print("=== 小說多代理系統（輸入 quit 離開）===")
        print("建議先輸入：create 專案ID 專案名 故事簡述")
        current_project = None
        while True:
            user_text = input("你> ").strip()
            if user_text in {"quit", "exit"}:
                break

            if user_text.startswith("create "):
                _, pid, title, brief = user_text.split(" ", 3)
                self.create_project(pid, title, brief)
                current_project = pid
                print(f"系統> 專案 {pid} 建立完成。")
                continue

            if not current_project:
                print("系統> 請先建立專案。")
                continue

            intent = self.router.classify(user_text)
            if intent == "research":
                n = self.research.ingest_reference(current_project, "manual-input", user_text)
                print(f"系統> 已寫入參考資料，共 {n} chunks。")
            elif intent == "outline":
                candidates = self.outline.generate_candidates(user_text)
                outlines = self.store.get("outlines")
                outlines[current_project] = {"chosen": candidates[0], "candidates": candidates}
                self.store.set("outlines", outlines)
                print("系統> 已產生 5 份大綱，預設選擇方案 1。")
            elif intent == "plan":
                projects = self.store.get("projects")
                outlines = self.store.get("outlines")
                if current_project not in outlines:
                    print("系統> 先建立大綱再拆章。")
                    continue
                target = projects[current_project]["target_chapter_words"]
                plans = self.architect.build_plan(outlines[current_project]["chosen"], 3, target)
                chapter_plans = self.store.get("chapter_plans")
                chapter_plans[current_project] = [asdict(p) for p in plans]
                self.store.set("chapter_plans", chapter_plans)
                print("系統> 已拆成 3 章。")
            elif intent == "write":
                chapter_plans = self.store.get("chapter_plans")
                outlines = self.store.get("outlines")
                projects = self.store.get("projects")
                if current_project not in chapter_plans:
                    print("系統> 先拆章再生成。")
                    continue
                plan = ChapterPlan(**chapter_plans[current_project][0])
                refs = self.research.retrieve(current_project, user_text)
                chapter_text = self.writer.write_chapter(projects[current_project]["title"], plan, outlines[current_project]["chosen"], refs)
                drafts = self.store.get("chapter_drafts")
                drafts.setdefault(current_project, {})
                drafts[current_project]["1"] = chapter_text
                self.store.set("chapter_drafts", drafts)
                print("系統> 第 1 章已生成（儲存於 data/novel_db.json）。")
            elif intent == "revise":
                drafts = self.store.get("chapter_drafts")
                text = drafts.get(current_project, {}).get("1")
                if not text:
                    print("系統> 尚未生成章節。")
                    continue
                report = self.revision.review(text)
                print("系統> 修訂報告：", json.dumps(report, ensure_ascii=False))
            else:
                print("系統> 無法判斷任務，請明確說明：收集資料 / 大綱 / 章節 / 寫作 / 修訂")


def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-agent novel writing system")
    parser.add_argument("mode", choices=["demo", "chat"], help="Run demo pipeline or interactive chat")
    args = parser.parse_args()

    system = NovelSystem()
    if args.mode == "demo":
        system.run_demo()
    else:
        system.chat()


if __name__ == "__main__":
    main()
