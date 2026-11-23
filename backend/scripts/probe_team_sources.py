"""Read-only official source diagnostics; no DB, AI calls or credentials required."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.content_collector import Formula1ContentCollector, TEAM_EDITORIAL_SOURCES
collector = Formula1ContentCollector(None, None, "PaddockBrief source availability check")
def probe(source):
    try:
        collector.team_article_urls(source)
    except Exception:
        pass
with ThreadPoolExecutor(max_workers=4) as pool:
    list(pool.map(probe, TEAM_EDITORIAL_SOURCES))
print(json.dumps(sorted(collector.team_source_status, key=lambda row: row['code']), ensure_ascii=False))
