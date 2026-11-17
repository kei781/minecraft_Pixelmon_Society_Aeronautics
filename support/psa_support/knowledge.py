from __future__ import annotations
import hashlib
import json
import re
from collections import Counter
from pathlib import Path


def tokens(text: str) -> list[str]:
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text).lower()
    words = re.findall(r"[a-z0-9_]{2,}|[가-힣]{2,}", text)
    # Keep exact item IDs AND components so template-generated stone_${type} recipes match.
    return words + [part for word in words if '_' in word for part in word.split('_') if len(part)>1]


class Knowledge:
    def __init__(self, path: Path):
        data = json.loads(path.read_text())
        self.manifest = data["manifest"]
        self.documents = {d["id"]: d for d in data["documents"]}
        if not self.documents:
            raise ValueError("knowledge snapshot is empty")
        self.counters = {key: Counter(tokens(d["path"] + " " + d["text"]))
                         for key, d in self.documents.items()}
        self.frequency = Counter(word for counts in self.counters.values() for word in counts)

    def search(self, queries: list[str], limit=16):
        rankings = []
        for query in queries[:7]:
            terms = set(tokens(query))
            scores = {}
            for key, counts in self.counters.items():
                score = sum(min(counts[t], 4) / (self.frequency[t] ** 0.5)
                            for t in terms if counts[t])
                path = self.documents[key]['path']
                if '/recipes/' in path or '/shops/' in path:
                    score *= 2.5
                if '/dialog/dialogs/' in path:
                    score *= 0.12
                if '/loot_tables/' in path:
                    score *= 0.35
                if score:
                    scores[key] = score
            rankings.append(sorted(scores, key=lambda k: (-scores[k], k)))
        # Round-robin different questions: an NPC-location premise must not bury the tool recipe.
        selected = []
        for rank in range(limit):
            for ranking in rankings:
                if rank<len(ranking) and ranking[rank] not in selected:
                    selected.append(ranking[rank])
                    if len(selected)>=limit:
                        return [self.documents[k] for k in selected]
        return [self.documents[k] for k in selected]


def document_chunks(path: str, text: str):
    # Preserve source locations, including long JSON lines, within a bounded input budget.
    lines = text.splitlines()
    current, start, length = [], 1, 0
    for number, line in enumerate(lines, 1):
        for offset in range(0, max(len(line), 1), 2800):
            part = line[offset:offset + 2800]
            if current and length + len(part) > 3500:
                body = "\n".join(current)
                yield {"id": hashlib.sha256((path + str(start) + body).encode()).hexdigest()[:16],
                       "path": path, "line": start, "text": body}
                current, start, length = [], number, 0
            if not current:
                start = number
            current.append(part)
            length += len(part) + 1
    if current:
        body = "\n".join(current)
        yield {"id": hashlib.sha256((path + str(start) + body).encode()).hexdigest()[:16],
               "path": path, "line": start, "text": body}
