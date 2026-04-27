from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import Flask, flash, g, redirect, render_template, request, url_for


BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "english_game.db"

app = Flask(__name__)
app.config["SECRET_KEY"] = "kids-english-game-secret"


def ensure_database() -> None:
    if not DATABASE.exists():
        init_db()
        return

    db = sqlite3.connect(DATABASE)
    migrate_db(db)
    db.commit()
    db.close()


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        g.db = conn
    return g.db


@app.teardown_appcontext
def close_db(_: Any) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    db = sqlite3.connect(DATABASE)
    with open(BASE_DIR / "schema.sql", "r", encoding="utf-8") as schema_file:
        db.executescript(schema_file.read())
    migrate_db(db)
    db.commit()

    level_count = db.execute("SELECT COUNT(*) FROM levels").fetchone()[0]
    if level_count == 0:
        seed_levels(db)
    db.close()


def migrate_db(db: sqlite3.Connection) -> None:
    columns = {
        row[1] for row in db.execute("PRAGMA table_info(levels)").fetchall()
    }
    if "has_video" not in columns:
        db.execute("ALTER TABLE levels ADD COLUMN has_video INTEGER NOT NULL DEFAULT 1")


def seed_levels(db: sqlite3.Connection) -> None:
    demo_levels = [
        {
            "title": "Level 1 - Greeting",
            "english_text": "Hello, my name is Tom.",
            "translation": "你好，我叫汤姆。",
            "options": ["你好，我叫汤姆。", "今天天气很好。", "我喜欢踢足球。"],
            "video_url": "https://www.youtube.com/embed/dUXk8Nc5qQ8",
            "has_video": 1,
        },
        {
            "title": "Level 2 - Fruit",
            "english_text": "I like apples.",
            "translation": "我喜欢苹果。",
            "options": ["我喜欢香蕉。", "我喜欢苹果。", "我喜欢牛奶。"],
            "video_url": "https://www.youtube.com/embed/fLhZ0VptmW8",
            "has_video": 1,
        },
        {
            "title": "Level 3 - School",
            "english_text": "This is my school bag.",
            "translation": "这是我的书包。",
            "options": ["这是我的书包。", "那是我的铅笔。", "我有一只小猫。", "这是我的教室。"],
            "video_url": "https://www.youtube.com/embed/1qG3M7xQhHo",
            "has_video": 1,
        },
    ]

    for level in demo_levels:
        db.execute(
            """
            INSERT INTO levels (title, english_text, translation, options_json, video_url)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                level["title"],
                level["english_text"],
                level["translation"],
                json.dumps(level["options"], ensure_ascii=False),
                level["video_url"],
            ),
        )
    db.commit()


def normalize_text(value: str) -> str:
    return " ".join(value.strip().lower().split())


def fetch_levels() -> list[dict[str, Any]]:
    rows = get_db().execute(
        """
        SELECT
            l.*,
            COUNT(r.id) AS attempts,
            SUM(CASE WHEN r.is_completed = 1 THEN 1 ELSE 0 END) AS completions,
            MAX(r.updated_at) AS last_played
        FROM levels l
        LEFT JOIN progress_records r ON r.level_id = l.id
        GROUP BY l.id
        ORDER BY l.id
        """
    ).fetchall()
    return [dict(row) for row in rows]


def fetch_level(level_id: int) -> dict[str, Any] | None:
    row = get_db().execute("SELECT * FROM levels WHERE id = ?", (level_id,)).fetchone()
    if row is None:
        return None
    level = dict(row)
    level["options"] = json.loads(level["options_json"])
    level["has_video"] = bool(level.get("has_video", 1))
    return level


def fetch_progress(level_id: int) -> list[dict[str, Any]]:
    rows = get_db().execute(
        """
        SELECT *
        FROM progress_records
        WHERE level_id = ?
        ORDER BY updated_at DESC, id DESC
        """,
        (level_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def save_progress(level_id: int, stage_one_ok: bool, stage_two_ok: bool, completed: bool) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    get_db().execute(
        """
        INSERT INTO progress_records (
            level_id, stage_one_success, stage_two_success, is_completed, updated_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (level_id, int(stage_one_ok), int(stage_two_ok), int(completed), now),
    )
    get_db().commit()


@app.before_request
def before_request() -> None:
    ensure_database()


@app.route("/")
def home() -> str:
    return render_template("index.html", levels=fetch_levels())


@app.route("/level/<int:level_id>", methods=["GET", "POST"])
def level_detail(level_id: int) -> str:
    level = fetch_level(level_id)
    if level is None:
        flash("未找到这个关卡。", "error")
        return redirect(url_for("home"))

    state = {
        "stage_one_passed": False,
        "stage_two_passed": False,
        "user_answer": "",
        "selected_option": "",
    }

    if request.method == "POST":
        action = request.form.get("action")

        if action == "check_sentence":
            user_answer = request.form.get("user_answer", "")
            state["user_answer"] = user_answer
            if normalize_text(user_answer) == normalize_text(level["english_text"]):
                state["stage_one_passed"] = True
                flash("第一部分回答正确，继续下一题吧。", "success")
            else:
                save_progress(level_id, False, False, False)
                flash("输入内容和目标英语不匹配，请再试一次。", "error")

        elif action == "check_option":
            state["stage_one_passed"] = request.form.get("stage_one_passed") == "true"
            state["user_answer"] = request.form.get("user_answer", "")
            selected_option = request.form.get("selected_option", "")
            state["selected_option"] = selected_option

            if not state["stage_one_passed"]:
                flash("请先完成第一部分。", "error")
            elif selected_option == level["translation"]:
                state["stage_two_passed"] = True
                if level["has_video"]:
                    flash("第二部分答对了，可以观看动画片啦。", "success")
                else:
                    flash("第二部分答对了，本关没有动画片，可以直接完成关卡。", "success")
            else:
                save_progress(level_id, True, False, False)
                flash("翻译选择错误，请再试试。", "error")

        elif action == "finish_level":
            state["stage_one_passed"] = request.form.get("stage_one_passed") == "true"
            state["stage_two_passed"] = request.form.get("stage_two_passed") == "true"
            state["user_answer"] = request.form.get("user_answer", "")
            state["selected_option"] = request.form.get("selected_option", "")

            if state["stage_one_passed"] and state["stage_two_passed"]:
                save_progress(level_id, True, True, True)
                flash("恭喜完成本关卡，记录已保存。", "success")
                return redirect(url_for("progress_list"))
            flash("请完成前两部分后再结束关卡。", "error")

    return render_template("level_detail.html", level=level, state=state)


@app.route("/progress")
def progress_list() -> str:
    levels = fetch_levels()
    return render_template("progress.html", levels=levels)


@app.route("/progress/<int:level_id>")
def progress_detail(level_id: int) -> str:
    level = fetch_level(level_id)
    if level is None:
        flash("未找到这个关卡。", "error")
        return redirect(url_for("progress_list"))

    records = fetch_progress(level_id)
    return render_template("progress_detail.html", level=level, records=records)


@app.route("/settings")
def settings() -> str:
    levels = fetch_levels()
    return render_template("settings.html", levels=levels)


@app.route("/settings/new", methods=["GET", "POST"])
def create_level() -> str:
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        english_text = request.form.get("english_text", "").strip()
        translation = request.form.get("translation", "").strip()
        options_raw = request.form.get("options", "").strip()
        has_video = request.form.get("has_video") == "on"
        video_url = request.form.get("video_url", "").strip()

        options = [item.strip() for item in options_raw.splitlines() if item.strip()]
        if not title or not english_text or not translation or len(options) < 3:
            flash("请完整填写内容，选项至少 3 条。", "error")
            return render_template("level_form.html", level=None, form=request.form)

        if has_video and not video_url:
            flash("勾选了动画片时，必须填写视频链接。", "error")
            return render_template("level_form.html", level=None, form=request.form)

        if translation not in options:
            flash("选项中必须包含正确翻译。", "error")
            return render_template("level_form.html", level=None, form=request.form)

        get_db().execute(
            """
            INSERT INTO levels (title, english_text, translation, options_json, video_url, has_video)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                title,
                english_text,
                translation,
                json.dumps(options, ensure_ascii=False),
                video_url,
                int(has_video),
            ),
        )
        get_db().commit()
        flash("新关卡已创建。", "success")
        return redirect(url_for("settings"))

    return render_template("level_form.html", level=None, form={})


@app.route("/settings/<int:level_id>/edit", methods=["GET", "POST"])
def edit_level(level_id: int) -> str:
    level = fetch_level(level_id)
    if level is None:
        flash("未找到这个关卡。", "error")
        return redirect(url_for("settings"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        english_text = request.form.get("english_text", "").strip()
        translation = request.form.get("translation", "").strip()
        options_raw = request.form.get("options", "").strip()
        has_video = request.form.get("has_video") == "on"
        video_url = request.form.get("video_url", "").strip()

        options = [item.strip() for item in options_raw.splitlines() if item.strip()]
        if not title or not english_text or not translation or len(options) < 3:
            flash("请完整填写内容，选项至少 3 条。", "error")
            return render_template("level_form.html", level=level, form=request.form)

        if has_video and not video_url:
            flash("勾选了动画片时，必须填写视频链接。", "error")
            return render_template("level_form.html", level=level, form=request.form)

        if translation not in options:
            flash("选项中必须包含正确翻译。", "error")
            return render_template("level_form.html", level=level, form=request.form)

        get_db().execute(
            """
            UPDATE levels
            SET title = ?, english_text = ?, translation = ?, options_json = ?, video_url = ?, has_video = ?
            WHERE id = ?
            """,
            (
                title,
                english_text,
                translation,
                json.dumps(options, ensure_ascii=False),
                video_url,
                int(has_video),
                level_id,
            ),
        )
        get_db().commit()
        flash("关卡已更新。", "success")
        return redirect(url_for("settings"))

    form = {
        "title": level["title"],
        "english_text": level["english_text"],
        "translation": level["translation"],
        "options": "\n".join(level["options"]),
        "video_url": level["video_url"],
        "has_video": level["has_video"],
    }
    return render_template("level_form.html", level=level, form=form)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
