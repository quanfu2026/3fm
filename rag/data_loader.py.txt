from pathlib import Path

def load_documents(path):
    docs = []
    path = Path(path)

    if not path.exists():
        return []

    for file in path.rglob("*"):
        if file.suffix in [".txt", ".md"]:
            docs.append(file.read_text(encoding="utf-8"))

    return docs