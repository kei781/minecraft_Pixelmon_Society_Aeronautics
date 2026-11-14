from __future__ import annotations
import hashlib
import json
import re
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from .config import Config
from .models import Decision


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.db = sqlite3.connect(path, timeout=15)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS messages (
          id TEXT PRIMARY KEY, guild TEXT NOT NULL, channel TEXT NOT NULL, author TEXT NOT NULL,
          question TEXT NOT NULL, created REAL NOT NULL, day TEXT NOT NULL, status TEXT NOT NULL,
          decision TEXT, parts TEXT, sent_parts INTEGER NOT NULL DEFAULT 0, ticket INTEGER);
        CREATE TABLE IF NOT EXISTS tickets (
          id INTEGER PRIMARY KEY, fingerprint TEXT NOT NULL, title TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'suspected', snapshot TEXT NOT NULL,
          details TEXT NOT NULL, created REAL NOT NULL, updated REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS reports (
          ticket INTEGER NOT NULL, message TEXT NOT NULL UNIQUE, url TEXT NOT NULL,
          details TEXT NOT NULL, FOREIGN KEY(ticket) REFERENCES tickets(id));
        CREATE TABLE IF NOT EXISTS updates (
          id INTEGER PRIMARY KEY, ticket INTEGER NOT NULL, status TEXT NOT NULL,
          summary TEXT NOT NULL, evidence TEXT NOT NULL, created REAL NOT NULL,
          notified INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS reply_links (
          message TEXT PRIMARY KEY, ticket INTEGER NOT NULL, author TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS messages_author_time ON messages(author, created);
        CREATE INDEX IF NOT EXISTS tickets_fingerprint ON tickets(fingerprint);
        """)
        path.chmod(0o600)

    def bind(self, cfg: Config):
        with self.db:
            self.db.execute("CREATE TABLE IF NOT EXISTS scope (id INTEGER PRIMARY KEY CHECK(id=1), guild TEXT NOT NULL, channel TEXT NOT NULL)")
            self.db.execute("INSERT OR IGNORE INTO scope VALUES(1,?,?)", (str(cfg.guild_id),str(cfg.channel_id)))
            row = self.db.execute("SELECT guild,channel FROM scope WHERE id=1").fetchone()
            if (row['guild'],row['channel']) != (str(cfg.guild_id),str(cfg.channel_id)):
                raise ValueError("Database belongs to another guild/channel; choose a new database")

    def reserve(self, cfg: Config, message: str, author: str, question: str, now=None):
        now = time.time() if now is None else now
        day = datetime.fromtimestamp(now, ZoneInfo("Asia/Seoul")).date().isoformat()
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            self._recover_processing(now-390)
            self.db.execute("DELETE FROM messages WHERE ticket IS NULL AND status IN ('sent','error') AND created<?", (now-7*86400,))
            if self.db.execute("SELECT 1 FROM messages WHERE id=?", (message,)).fetchone():
                return "duplicate"
            recent = self.db.execute("SELECT MAX(created) FROM messages WHERE author=?", (author,)).fetchone()[0]
            if recent is not None and now-recent < cfg.user_cooldown_seconds:
                return "cooldown"
            if self.db.execute("SELECT COUNT(*) FROM messages WHERE day=?", (day,)).fetchone()[0] >= cfg.daily_request_limit:
                return "daily_limit"
            if self.db.execute("SELECT COUNT(*) FROM messages WHERE status='processing'").fetchone()[0] >= cfg.max_parallel_requests:
                return "busy"
            self.db.execute("INSERT INTO messages(id,guild,channel,author,question,created,day,status) VALUES(?,?,?,?,?,?,?,'processing')",
                            (message,str(cfg.guild_id),str(cfg.channel_id),author,question,now,day))
        return "accepted"

    def history(self, author: str, before: float):
        rows = self.db.execute("SELECT question,decision FROM messages WHERE author=? AND created<? AND created>? AND status IN ('ready','sent') ORDER BY created DESC LIMIT 4",
                               (author,before,before-6*3600)).fetchall()
        return [{"question": r["question"], "answer": json.loads(r["decision"])["answer"]}
                for r in reversed(rows) if r["decision"]]

    def _recover_processing(self, before: float):
        notice = '문의 처리 중 봇이 재시작되거나 응답 시간이 초과됐습니다. 답변과 티켓 접수가 완료되지 않았으니 이 메시지에 답장으로 다시 문의해 주세요.'
        self.db.execute("UPDATE messages SET status='ready',parts=?,sent_parts=0 WHERE status='processing' AND created<?",
                        (json.dumps([notice],ensure_ascii=False),before))

    def recover_processing(self):
        # A service instance owns all in-flight work; setup runs once before receiving messages.
        with self.db:
            self._recover_processing(float('inf'))

    def ticket_for_reply(self, reference: str, author: str):
        row = self.db.execute("""SELECT t.id FROM tickets t JOIN (
          SELECT ticket,author FROM messages WHERE id=?
          UNION ALL SELECT ticket,author FROM reply_links WHERE message=?
        ) r ON r.ticket=t.id WHERE r.author=?
        AND t.status IN ('suspected','investigating','needs_information') LIMIT 1""",
                              (reference,reference,author)).fetchone()
        return row[0] if row else None

    def ticket_context(self, ticket: int, author: str):
        rows = self.db.execute("SELECT question,decision FROM messages WHERE ticket=? AND author=? ORDER BY created DESC LIMIT 4",
                               (ticket,author)).fetchall()
        history = [{"question":r['question'],"answer":json.loads(r['decision'])['answer']}
                   for r in reversed(rows) if r['decision']]
        update = self.db.execute("SELECT summary FROM updates WHERE ticket=? ORDER BY id DESC LIMIT 1",(ticket,)).fetchone()
        if update:
            history.append({"question":f"PSA-{ticket:04d} 운영자 확인 요청", "answer":update['summary']})
        return history

    def link_reply(self, message: str, ticket: int, author: str):
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO reply_links VALUES(?,?,?)",(message,ticket,author))

    def finish(self, message: str, decision: Decision, snapshot: str, source_labels: list[str], related_ticket=None):
        now = time.time()
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            row = self.db.execute("SELECT * FROM messages WHERE id=?", (message,)).fetchone()
            if row is None or row["status"] != "processing":
                raise ValueError("message is not being processed")
            ticket_id = related_ticket
            if ticket_id is not None:
                if not self.db.execute("SELECT 1 FROM tickets t JOIN messages m ON m.ticket=t.id WHERE t.id=? AND m.author=? AND t.status IN ('suspected','investigating','needs_information')",(ticket_id,row['author'])).fetchone():
                    raise ValueError('follow-up ticket is unavailable for this author')
                self.db.execute("UPDATE tickets SET updated=?,status=CASE WHEN status='needs_information' THEN 'suspected' ELSE status END WHERE id=?",(now,ticket_id))
            elif decision.category == "suspected_bug":
                title = decision.title.strip() or row["question"][:100]
                fingerprint = hashlib.sha256((snapshot+re.sub(r"\s+", "", title.lower())).encode()).hexdigest()
                existing = self.db.execute("SELECT id FROM tickets WHERE fingerprint=? AND status IN ('suspected','investigating','needs_information') ORDER BY id LIMIT 1", (fingerprint,)).fetchone()
                details = decision.model_dump_json()
                if existing:
                    ticket_id = existing[0]
                    self.db.execute("UPDATE tickets SET updated=? WHERE id=?", (now,ticket_id))
                else:
                    ticket_id = self.db.execute("INSERT INTO tickets(fingerprint,title,snapshot,details,created,updated) VALUES(?,?,?,?,?,?)",
                                               (fingerprint,title,snapshot,details,now,now)).lastrowid
            if ticket_id is not None:
                url = f"https://discord.com/channels/{row['guild']}/{row['channel']}/{message}"
                self.db.execute("INSERT INTO reports VALUES(?,?,?,?)", (ticket_id,message,url,decision.model_dump_json()))
            text = decision.answer
            if source_labels:
                text += "\n\n근거: " + ", ".join(source_labels[:4])
            if ticket_id is not None:
                label = '추가 정보 기록' if related_ticket is not None else '버그 의심 접수'
                text += f"\n\n🔎 {label} **PSA-{ticket_id:04d}**\n한국 시간 새벽 4시 작업 대상입니다. 해결 시점은 조사 결과에 따라 달라집니다. 추가 정보는 이 답변에 답장해 주세요."
            # Discord counts UTF-16 units; keep chunks below 2000 even with emoji.
            parts, current, units = [], [], 0
            for char in text:
                size = len(char.encode('utf-16-le'))//2
                if units + size > 1800:
                    parts.append(''.join(current)); current, units = [], 0
                current.append(char); units += size
            if current:
                parts.append(''.join(current))
            self.db.execute("UPDATE messages SET status='ready',decision=?,parts=?,ticket=? WHERE id=?",
                            (decision.model_dump_json(),json.dumps(parts,ensure_ascii=False),ticket_id,message))
        return ticket_id

    def fail(self, message: str):
        with self.db:
            self.db.execute("UPDATE messages SET status='error' WHERE id=? AND status='processing'", (message,))

    def pending(self):
        return self.db.execute("SELECT * FROM messages WHERE status='ready' ORDER BY created LIMIT 20").fetchall()

    def sent_part(self, message: str):
        with self.db:
            row = self.db.execute("SELECT parts,sent_parts FROM messages WHERE id=?", (message,)).fetchone()
            count = row['sent_parts']+1
            status = 'sent' if count >= len(json.loads(row['parts'])) else 'ready'
            self.db.execute("UPDATE messages SET sent_parts=?,status=? WHERE id=?", (count,status,message))

    def tickets(self, include_closed=False):
        clause = "" if include_closed else "WHERE status NOT IN ('resolved','not_a_bug')"
        result = []
        for row in self.db.execute(f"SELECT * FROM tickets {clause} ORDER BY created"):
            ticket = dict(row); ticket['details'] = json.loads(ticket['details'])
            ticket['reports'] = [dict(r) for r in self.db.execute("SELECT * FROM reports WHERE ticket=?", (row['id'],))]
            ticket['updates'] = [dict(r) for r in self.db.execute("SELECT * FROM updates WHERE ticket=? ORDER BY id", (row['id'],))]
            result.append(ticket)
        return result

    def update_ticket(self, ticket: int, status: str, summary: str, evidence: str):
        if status not in ('investigating','needs_information','resolved','not_a_bug'):
            raise ValueError("invalid ticket status")
        if not summary.strip() or not evidence.strip():
            raise ValueError("every status update requires a summary and evidence")
        with self.db:
            if not self.db.execute("SELECT 1 FROM tickets WHERE id=?", (ticket,)).fetchone():
                raise ValueError("unknown ticket")
            self.db.execute("UPDATE tickets SET status=?,updated=? WHERE id=?", (status,time.time(),ticket))
            self.db.execute("INSERT INTO updates(ticket,status,summary,evidence,created) VALUES(?,?,?,?,?)",
                            (ticket,status,summary,evidence,time.time()))

    def notifications(self):
        return self.db.execute("""SELECT u.*,m.id AS report_message,m.author AS report_author
          FROM updates u JOIN messages m ON m.id=(SELECT m2.id FROM messages m2
          WHERE m2.ticket=u.ticket ORDER BY m2.created LIMIT 1)
          WHERE u.notified=0 ORDER BY u.id LIMIT 10""").fetchall()

    def notified(self, update: int):
        with self.db:
            self.db.execute("UPDATE updates SET notified=1 WHERE id=?", (update,))
