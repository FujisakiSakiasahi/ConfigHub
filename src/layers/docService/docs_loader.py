import csv
from dataclasses import dataclass
from pathlib import Path

_BASE_DIR = Path(__file__).parent
_DOCS_DIR = _BASE_DIR / "docs"
_INDEX_PATH = _BASE_DIR / "index.md"


@dataclass
class Document:
    doc_id: str
    title: str
    description: str
    path: Path


def list_documents() -> list[Document]:
    with _INDEX_PATH.open(encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))

    docs = []
    for name, description, filename in rows[1:]:
        if not filename:
            continue
        docs.append(
            Document(
                doc_id=Path(filename).stem,
                title=name,
                description=description,
                path=_DOCS_DIR / filename,
            )
        )
    return docs


def get_document_text(doc_id: str) -> str:
    for doc in list_documents():
        if doc.doc_id == doc_id:
            return doc.path.read_text(encoding="utf-8")
    raise FileNotFoundError(f"No documentation entry for '{doc_id}'")
