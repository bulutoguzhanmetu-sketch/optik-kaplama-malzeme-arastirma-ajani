"""coating_agent konfigürasyonu. Tüm değerler ortam değişkenlerinden okunur, repoya gizli anahtar yazılmaz."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

SOURCE_PDF_DIR = Path(os.environ.get("COATING_AGENT_SOURCE_DIR", BASE_DIR / "source_pdfs"))
DATA_DIR = Path(os.environ.get("COATING_AGENT_DATA_DIR", BASE_DIR / "data"))
OUTPUT_DIR = Path(os.environ.get("COATING_AGENT_OUTPUT_DIR", BASE_DIR / "output"))

CHROMA_DB_DIR = DATA_DIR / "chroma_db"
MANIFEST_PATH = DATA_DIR / "ingested_manifest.json"
COLLECTION_NAME = "optik_kaplama_kanit_tabani"

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")

# Chunk ayarları (yaklaşık token sayısı; kelime bazlı kabaca tahmin edilir, ~1 token ≈ 0.75 kelime)
CHUNK_TOKEN_SIZE = int(os.environ.get("COATING_AGENT_CHUNK_TOKENS", "650"))
CHUNK_TOKEN_OVERLAP = int(os.environ.get("COATING_AGENT_CHUNK_OVERLAP", "120"))

RETRIEVAL_TOP_K = int(os.environ.get("COATING_AGENT_TOP_K", "12"))

for _d in (SOURCE_PDF_DIR, DATA_DIR, OUTPUT_DIR):
    _d.mkdir(parents=True, exist_ok=True)
