# Website Crawl → Knowledge Base Flow

## Architecture
```
POST /api/knowledge/website
    ↓
SSRF validation (RFC1918, loopback, link-local, file:// blocked)
    ↓
knowledge_crawler.py (threading.Thread, no event-loop blocking)
    ↓
urllib → HTML → readability (strip nav/footer/ads)
    ↓
Document row (text_content = concatenated pages)
    ↓
extract_skills_from_document() (chunked, 6K windows, anti-hallucination)
    ↓
Skill rows → induction pre-loaded knowledge
```

## Key Constraints
- Max 50 pages, max depth 3, same domain only
- 500ms rate limit, 60s wall-clock timeout
- robots.txt respected via urllib.robotparser
- Priority pages: /about, /pricing, /faq, /features crawled first
- JS-rendered sites (SPAs) will fail — crawler uses raw HTML only
- cssselect must be installed in the ARA venv

## API Surface
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/knowledge/website` | POST | Submit URL for crawling |
| `/api/knowledge/website/{id}` | DELETE | Remove entry + cascaded skills |
| `/api/knowledge/website/{id}/refresh` | POST | Re-crawl (rejects if crawling) |
| `/api/knowledge/{tenant_id}` | GET | Returns documents + websites with source_type |

## DB Schema
`documents` table gains:
- `source_type` TEXT DEFAULT 'document' — 'document' or 'website'
- `source_url` TEXT — the crawled URL
- `page_count` INTEGER DEFAULT 0
- `crawl_status` TEXT — 'pending', 'crawling', 'done', 'failed'
- `last_crawled_at` TIMESTAMP
- `respect_robots` INTEGER DEFAULT 1

## Frontend
- URL input bar + Crawl button in Knowledge Base page
- Website cards: 🌐 icon, page count, refresh/delete
- Section headers: 🌐 Websites, 📄 Documents
