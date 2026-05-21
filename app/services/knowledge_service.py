from pathlib import Path


class KnowledgeService:
    def __init__(self, kb_path: str = 'app/knowledge_base.md') -> None:
        self.kb_path = Path(kb_path)

    def read(self) -> str:
        if not self.kb_path.exists():
            return ''
        return self.kb_path.read_text(encoding='utf-8')
