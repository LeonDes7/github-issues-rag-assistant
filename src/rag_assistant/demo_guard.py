"""Local persistent quota shared by Streamlit sessions on one app instance."""
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

SESSION_LIMIT = 5
DAILY_LIMIT = 50

def reserve_question(state, database, day=None):
    """Count attempts before network activity, including failed requests."""
    if state.get("demo_questions", 0) >= SESSION_LIMIT:
        return "You have reached this session's five-question limit. Thanks for trying the demo!"
    day = day or datetime.now(timezone.utc).date().isoformat()
    database = Path(database)
    database.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(database, timeout=5)) as connection, connection:
        connection.execute("CREATE TABLE IF NOT EXISTS daily (day TEXT PRIMARY KEY, count INTEGER NOT NULL)")
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("INSERT OR IGNORE INTO daily VALUES (?, 0)", (day,))
        count = connection.execute("SELECT count FROM daily WHERE day=?", (day,)).fetchone()[0]
        if count >= DAILY_LIMIT:
            return "Today's demo question limit has been reached. Please come back tomorrow (UTC)."
        connection.execute("UPDATE daily SET count=count+1 WHERE day=?", (day,))
    state["demo_questions"] = state.get("demo_questions", 0) + 1
    return None
