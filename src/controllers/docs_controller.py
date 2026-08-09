from src.layers.docService import docs_loader


class DocsController:
    """Bridge between the documentation view and service layers."""

    def get_articles(self) -> list:
        return [
            {"id": doc.doc_id, "title": doc.title, "description": doc.description}
            for doc in docs_loader.list_documents()
        ]

    def get_article_content(self, doc_id: str) -> str:
        return docs_loader.get_document_text(doc_id)
