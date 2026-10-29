"""Load only the reviewed bundled synthetic knowledge corpus."""

import json
from pathlib import Path

from opsbridge.application.knowledge import CorpusManifest, KnowledgeService
from opsbridge.infrastructure.config import get_settings
from opsbridge.infrastructure.db import Database


def main() -> int:
    corpus_path = Path(__file__).resolve().parents[3] / "data" / "knowledge" / "corpus.json"
    if corpus_path.stat().st_size > 1_000_000:
        raise RuntimeError("Bundled corpus exceeds the reviewed size limit")
    manifest = CorpusManifest.model_validate(json.loads(corpus_path.read_text(encoding="utf-8")))
    database = Database(get_settings().database_url)
    try:
        inserted, unchanged = KnowledgeService(database).ingest(manifest)
    finally:
        database.dispose()
    print(f"Knowledge corpus ready: {inserted} updated, {unchanged} unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
