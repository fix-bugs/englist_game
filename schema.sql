CREATE TABLE IF NOT EXISTS levels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    english_text TEXT NOT NULL,
    translation TEXT NOT NULL,
    options_json TEXT NOT NULL,
    video_url TEXT NOT NULL,
    has_video INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS progress_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    level_id INTEGER NOT NULL,
    stage_one_success INTEGER NOT NULL DEFAULT 0,
    stage_two_success INTEGER NOT NULL DEFAULT 0,
    is_completed INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(level_id) REFERENCES levels(id)
);
