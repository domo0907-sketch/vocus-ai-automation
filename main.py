"""Monitor the owner's public Vocus room and create editorial Markdown drafts.

No automatic posting, scraping bypass, or login automation is performed.
"""
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from openai import OpenAI

ROOT = Path(__file__).resolve().parent
CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
STATE_PATH = ROOT / "state.json"
OUT = ROOT / "output"
HEADERS = {"User-Agent": "VocusOwnArticlesMonitor/1.0 (+personal content backup; low frequency)", "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.7"}
ARTICLE_RE = re.compile(r"^/article/([a-zA-Z0-9]+)(?:/)?$")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def fetch(session, url):
    response = session.get(url, headers=HEADERS, timeout=25)
    response.raise_for_status()
    if "html" not in response.headers.get("Content-Type", "").lower():
        raise ValueError(f"Not HTML: {url}")
    return BeautifulSoup(response.text, "html.parser")


def find_articles(soup):
    """Discover only true article URLs; excludes navigation/social links."""
    seen, results = set(), []
    for a in soup.select('a[href]'):
        href = urljoin("https://vocus.cc", a.get("href", ""))
        parsed = urlparse(href)
        if parsed.hostname not in ("vocus.cc", "www.vocus.cc"):
            continue
        match = ARTICLE_RE.fullmatch(parsed.path)
        if not match:
            continue
        canonical = f"https://vocus.cc/article/{match.group(1)}"
        if canonical not in seen:
            seen.add(canonical)
            results.append(canonical)
    return results


def article_text(soup):
    # Remove surrounding layout, share panels, headings TOC widgets.
    for tag in soup.select("script,style,nav,footer,header,aside,button,form"):
        tag.decompose()
    headline = soup.find("h1")
    title = headline.get_text(" ", strip=True) if headline else ""
    if not title:
        meta = soup.find("meta", attrs={"property": "og:title"})
        title = meta.get("content", "") if meta else ""
    if not title:
        raise ValueError("Missing article heading")
    # Site markup may change: validate length and spot-check output before relying on it.
    candidates = []
    for selector in ['article', '[class*="article-content"]', '[class*="Article_content"]', 'main']:
        for node in soup.select(selector):
            paragraphs = [n.get_text(" ", strip=True) for n in node.select("h2,h3,p,li,blockquote")]
            text = "\n\n".join(p for p in paragraphs if len(p) > 8)
            if text:
                candidates.append(text)
    if not candidates:
        raise ValueError("Could not identify article body; inspect page structure")
    body = max(candidates, key=len)
    if len(body) < CONFIG["min_source_characters"]:
        raise ValueError(f"Body too short ({len(body)} characters)")
    return title, body[:35000]


def rewrite(client, title, body, url):
    prompt = f"""以下為本人已發表於方格子的原創文章，請重新整理為『另一篇有獨立價值、供作者人工審核』的繁體中文草稿。
不得虛構購買經驗、實測結果、售價、規格、專家意見或新的事實。保留可追溯的來源資訊。若資訊可能過時，列出待查證項目；避免只換字的重複內容。
輸出 Markdown：新標題（H1）、一段摘要、3-5個SEO關鍵字、H2小節、待查證清單、原文來源連結。不要聲稱已經上架。
原文標題：{title}\n原文網址：{url}\n原文內容：\n{body}"""
    result = client.responses.create(model=CONFIG["rewrite_model"], input=prompt, max_output_tokens=2500)
    output = (result.output_text or "").strip()
    if len(output) < 200:
        raise ValueError("AI result unexpectedly short")
    return output


def main():
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("Set OPENAI_API_KEY in GitHub Actions secrets or environment")
    OUT.mkdir(exist_ok=True)
    state = json.loads(STATE_PATH.read_text(encoding="utf-8")) if STATE_PATH.exists() else {"processed": {}}
    processed = state.setdefault("processed", {})
    session = requests.Session()
    index = fetch(session, CONFIG["author_url"])
    urls = find_articles(index)
    if not urls:
        raise RuntimeError("No article links were found; page format may have changed or access blocked")
    logging.info("Found %d article links on room page", len(urls))
    client = OpenAI()
    count = 0
    for url in urls:
        if count >= CONFIG["max_new_articles_per_run"]:
            break
        if url in processed:
            continue
        try:
            page = fetch(session, url)
            title, body = article_text(page)
            draft = rewrite(client, title, body, url)
            article_id = url.rsplit("/", 1)[-1]
            destination = OUT / f"{article_id}.md"
            destination.write_text(f"<!-- 原始標題：{title} -->\n<!-- 原始網址：{url} -->\n\n{draft}\n", encoding="utf-8")
            processed[url] = {"source_title": title, "draft_file": destination.name, "processed_at_utc": datetime.now(timezone.utc).isoformat(), "status": "pending_human_review"}
            STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            logging.info("Created draft: %s", destination)
            count += 1
            time.sleep(2)
        except Exception as exc:
            logging.error("Skipped %s: %s", url, exc)
    logging.info("Finished: %d new drafts", count)
    if count == 0 and not processed:
        raise RuntimeError("No drafts generated; inspect access / page selectors / OpenAI setup")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logging.exception("Job failed")
        sys.exit(1)
