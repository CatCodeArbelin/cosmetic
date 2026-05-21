from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class KnowledgeChunk:
    section: str
    content: str


class KnowledgeService:
    def __init__(self, kb_path: str = 'app/knowledge_base.md') -> None:
        self.kb_path = Path(kb_path)

    def read(self) -> str:
        if not self.kb_path.exists():
            return ''
        return self.kb_path.read_text(encoding='utf-8')

    def _sections(self) -> list[KnowledgeChunk]:
        raw = self.read()
        if not raw:
            return []

        chunks: list[KnowledgeChunk] = []
        current_title = 'Общее'
        current_lines: list[str] = []

        for line in raw.splitlines():
            if line.startswith('## '):
                if current_lines:
                    chunks.append(KnowledgeChunk(section=current_title, content='\n'.join(current_lines).strip()))
                current_title = line.replace('## ', '', 1).strip()
                current_lines = []
            else:
                current_lines.append(line)

        if current_lines:
            chunks.append(KnowledgeChunk(section=current_title, content='\n'.join(current_lines).strip()))

        return [chunk for chunk in chunks if chunk.content]

    def relevant_context(self, user_text: str, limit: int = 2) -> str:
        query_words = {word.strip('.,!?()[]{}:;"\'').lower() for word in user_text.split() if len(word) > 2}
        if not query_words:
            return self.read()

        scored: list[tuple[int, KnowledgeChunk]] = []
        for chunk in self._sections():
            haystack = f'{chunk.section} {chunk.content}'.lower()
            score = sum(1 for word in query_words if word in haystack)
            if score > 0:
                scored.append((score, chunk))

        if not scored:
            return self.read()

        top_chunks = [item[1] for item in sorted(scored, key=lambda x: x[0], reverse=True)[:limit]]
        return '\n\n'.join(f'## {chunk.section}\n{chunk.content}' for chunk in top_chunks)
