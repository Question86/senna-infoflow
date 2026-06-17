#!/usr/bin/env python3
"""senna-infoflow monitor.

Reads configured public sources, normalizes findings, scores relevance, writes
JSON findings and a Markdown/JSON briefing for Senna L'Arcan-Ûr.

Design boundaries:
- Only configured public, freigegebene or user-provided sources.
- No bypassing authentication, no private data collection, no secret persistence.
- Individual source failures are isolated and reported; one bad source must not
  break the whole briefing.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urljoin, urlparse
from urllib.robotparser import RobotFileParser

import feedparser
import requests
import yaml
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
BRIEFINGS_DIR = ROOT / "briefings"
STATE_DIR = ROOT / "state"
LOGS_DIR = ROOT / "logs"

DEFAULT_TIMEOUT = 15
DEFAULT_MAX_ITEMS = 20
MAX_SUMMARY_CHARS = 420
HTML_LIKE_RE = re.compile(r"</?[a-zA-Z][^>]*>|<!--")


@dataclass
class SourceError:
    source_id: str
    source_name: str
    source_type: str
    error: str


@dataclass
class Finding:
    title: str
    url: str
    source: str
    source_type: str
    published_at: str | None
    fetched_at: str
    summary: str
    matched_keywords: list[str] = field(default_factory=list)
    relevance_score: int = 0
    relevance_reason: str = ""
    risk_or_opportunity: str = "observation"
    recommended_action: str = ""
    id: str = ""


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def setup_logging() -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOGS_DIR / "monitor.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_path, encoding="utf-8"),
        ],
    )


def load_dotenv(path: Path = ROOT / ".env") -> None:
    """Small .env loader to avoid an extra dependency.

    Existing environment variables win. Lines starting with # are ignored.
    """
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def load_yaml(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data if data is not None else default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        logging.warning("Invalid JSON in %s; using default.", path)
        return default


def normalize_ws(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def strip_html(text: str | None) -> str:
    if not text:
        return ""
    if not HTML_LIKE_RE.search(text):
        return normalize_ws(text)
    return normalize_ws(BeautifulSoup(text, "html.parser").get_text(" "))


def truncate(text: str, limit: int = MAX_SUMMARY_CHARS) -> str:
    text = normalize_ws(text)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def parse_datetime(value: Any) -> str | None:
    """Return ISO 8601 UTC-ish date string from common feed/API inputs."""
    if not value:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc).replace(microsecond=0).isoformat()
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        # GitHub already emits ISO timestamps with Z.
        if re.match(r"^\d{4}-\d{2}-\d{2}T", value):
            return value.replace("Z", "+00:00")
        try:
            parsed = parsedate_to_datetime(value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat()
        except Exception:
            return value
    return None


def stable_hash(*parts: str) -> str:
    joined = "\n".join([p or "" for p in parts])
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:20]


def clean_url(url: str | None) -> str:
    if not url:
        return ""
    return url.strip()


def source_keywords(source: dict[str, Any]) -> list[str]:
    raw = source.get("keywords") or []
    return [str(x) for x in raw if str(x).strip()]


def build_session(user_agent: str) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": user_agent,
            "Accept": "application/rss+xml, application/atom+xml, application/json, text/html, */*;q=0.8",
        }
    )
    return session


def load_seen() -> dict[str, Any]:
    state = read_json(STATE_DIR / "seen.json", {"version": 1, "items": {}})
    if isinstance(state, list):
        # Backward-compatible migration from a plain list of ids.
        return {"version": 1, "items": {item_id: {"first_seen_at": None} for item_id in state}}
    if not isinstance(state, dict):
        return {"version": 1, "items": {}}
    state.setdefault("version", 1)
    state.setdefault("items", {})
    return state


def save_seen(state: dict[str, Any]) -> None:
    write_json(STATE_DIR / "seen.json", state)


def mark_seen(state: dict[str, Any], finding: Finding) -> None:
    if not finding.id:
        finding.id = stable_hash(finding.source, finding.url, finding.title)
    items = state.setdefault("items", {})
    entry = items.get(finding.id, {})
    ts = now_iso()
    entry.setdefault("first_seen_at", ts)
    entry["last_seen_at"] = ts
    entry["title"] = finding.title
    entry["url"] = finding.url
    entry["source"] = finding.source
    items[finding.id] = entry


def is_seen(state: dict[str, Any], finding: Finding) -> bool:
    return bool(finding.id and finding.id in state.get("items", {}))


def request_get(
    session: requests.Session,
    url: str,
    timeout: int,
    headers: dict[str, str] | None = None,
    max_bytes: int | None = None,
) -> requests.Response:
    resp = session.get(url, timeout=timeout, headers=headers or {}, stream=bool(max_bytes))
    resp.raise_for_status()
    if max_bytes:
        chunks: list[bytes] = []
        size = 0
        for chunk in resp.iter_content(chunk_size=8192):
            if not chunk:
                continue
            size += len(chunk)
            if size > max_bytes:
                raise ValueError(f"Response exceeded max_bytes={max_bytes}")
            chunks.append(chunk)
        resp._content = b"".join(chunks)  # requests-compatible cache for resp.text/content
    return resp


def fetch_rss(
    session: requests.Session,
    source: dict[str, Any],
    max_items: int,
    timeout: int,
    fetched_at: str,
) -> list[Finding]:
    url = source.get("url")
    if not url:
        raise ValueError("RSS source requires url")
    resp = request_get(session, str(url), timeout=timeout)
    parsed = feedparser.parse(resp.content)
    if getattr(parsed, "bozo", 0):
        logging.warning("Feed parser warning for %s: %s", source.get("id"), getattr(parsed, "bozo_exception", ""))

    findings: list[Finding] = []
    for entry in parsed.entries[:max_items]:
        title = normalize_ws(getattr(entry, "title", "") or "Untitled RSS item")
        link = clean_url(getattr(entry, "link", "") or url)
        summary = strip_html(getattr(entry, "summary", "") or getattr(entry, "description", "") or title)
        published_at = parse_datetime(
            getattr(entry, "published", None)
            or getattr(entry, "updated", None)
            or getattr(entry, "created", None)
        )
        finding = Finding(
            title=title,
            url=link,
            source=str(source.get("name") or source.get("id")),
            source_type="rss",
            published_at=published_at,
            fetched_at=fetched_at,
            summary=truncate(summary),
        )
        finding.id = stable_hash("rss", finding.url or finding.title, finding.source)
        findings.append(finding)
    return findings


def github_headers(token: str | None) -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def fetch_github_search(
    session: requests.Session,
    source: dict[str, Any],
    max_items: int,
    timeout: int,
    fetched_at: str,
    token: str | None,
) -> list[Finding]:
    mode = str(source.get("mode") or "issues").lower().strip()
    query = str(source.get("query") or "").strip()
    if not query:
        raise ValueError("github_search source requires query")

    if mode == "code" and not token:
        logging.info("Skipping GitHub code search for %s because GITHUB_TOKEN is not set.", source.get("id"))
        return []

    endpoint_map = {
        "issues": "https://api.github.com/search/issues",
        "repositories": "https://api.github.com/search/repositories",
        "repos": "https://api.github.com/search/repositories",
        "code": "https://api.github.com/search/code",
    }
    endpoint = endpoint_map.get(mode)
    if not endpoint:
        raise ValueError(f"Unsupported github_search mode: {mode}")

    params = f"?q={quote_plus(query)}&sort=updated&order=desc&per_page={max_items}"
    resp = request_get(session, endpoint + params, timeout=timeout, headers=github_headers(token))
    remaining = resp.headers.get("X-RateLimit-Remaining")
    if remaining == "0":
        reset = resp.headers.get("X-RateLimit-Reset")
        logging.warning("GitHub rate limit exhausted. Reset: %s", reset)

    data = resp.json()
    items = data.get("items", [])
    findings: list[Finding] = []

    for item in items[:max_items]:
        if mode in {"repositories", "repos"}:
            title = item.get("full_name") or item.get("name") or "GitHub repository"
            url = item.get("html_url") or ""
            summary = item.get("description") or ""
            published_at = parse_datetime(item.get("updated_at") or item.get("created_at"))
        elif mode == "code":
            title = item.get("name") or item.get("path") or "GitHub code result"
            url = item.get("html_url") or ""
            repo_name = (item.get("repository") or {}).get("full_name", "")
            summary = f"Code result in {repo_name}: {item.get('path', '')}"
            published_at = None
        else:
            title = item.get("title") or "GitHub issue/result"
            url = item.get("html_url") or ""
            body = item.get("body") or ""
            repo_url = item.get("repository_url") or ""
            summary = body if body else f"GitHub search result. Repository API URL: {repo_url}"
            published_at = parse_datetime(item.get("updated_at") or item.get("created_at"))

        finding = Finding(
            title=normalize_ws(title),
            url=clean_url(url),
            source=str(source.get("name") or source.get("id")),
            source_type="github_search",
            published_at=published_at,
            fetched_at=fetched_at,
            summary=truncate(strip_html(summary)),
        )
        finding.id = stable_hash("github_search", finding.url or finding.title, finding.source)
        findings.append(finding)

    return findings


def fetch_reddit_json(
    session: requests.Session,
    source: dict[str, Any],
    max_items: int,
    timeout: int,
    fetched_at: str,
) -> list[Finding]:
    subreddit = str(source.get("subreddit") or "").strip().strip("/")
    if not subreddit:
        raise ValueError("reddit_json source requires subreddit")

    query = str(source.get("query") or "").strip()
    sort = str(source.get("sort") or "new")
    time_filter = str(source.get("time") or "week")

    if query:
        url = (
            f"https://www.reddit.com/r/{quote_plus(subreddit)}/search.json"
            f"?q={quote_plus(query)}&restrict_sr=1&sort={quote_plus(sort)}&t={quote_plus(time_filter)}&limit={max_items}"
        )
    else:
        url = f"https://www.reddit.com/r/{quote_plus(subreddit)}/new.json?limit={max_items}"

    resp = request_get(session, url, timeout=timeout)
    data = resp.json()
    children = (data.get("data") or {}).get("children") or []

    findings: list[Finding] = []
    for child in children[:max_items]:
        item = child.get("data") or {}
        title = item.get("title") or "Reddit post"
        permalink = item.get("permalink") or ""
        post_url = urljoin("https://www.reddit.com", permalink)
        summary = item.get("selftext") or item.get("url") or ""
        published_at = parse_datetime(item.get("created_utc"))

        finding = Finding(
            title=normalize_ws(title),
            url=clean_url(post_url),
            source=str(source.get("name") or f"r/{subreddit}"),
            source_type="reddit_json",
            published_at=published_at,
            fetched_at=fetched_at,
            summary=truncate(strip_html(summary)),
        )
        finding.id = stable_hash("reddit_json", finding.url or finding.title, finding.source)
        findings.append(finding)
    return findings


def fetch_hackernews(
    session: requests.Session,
    source: dict[str, Any],
    max_items: int,
    timeout: int,
    fetched_at: str,
) -> list[Finding]:
    query = str(source.get("query") or "").strip()
    if not query:
        raise ValueError("hackernews source requires query")

    url = (
        "https://hn.algolia.com/api/v1/search_by_date"
        f"?query={quote_plus(query)}&tags=story&hitsPerPage={max_items}"
    )
    resp = request_get(session, url, timeout=timeout)
    data = resp.json()
    hits = data.get("hits", [])

    findings: list[Finding] = []
    for hit in hits[:max_items]:
        title = hit.get("title") or hit.get("story_title") or "Hacker News item"
        hn_url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
        summary = hit.get("story_text") or hit.get("comment_text") or title
        published_at = parse_datetime(hit.get("created_at"))

        finding = Finding(
            title=normalize_ws(title),
            url=clean_url(hn_url),
            source=str(source.get("name") or source.get("id")),
            source_type="hackernews",
            published_at=published_at,
            fetched_at=fetched_at,
            summary=truncate(strip_html(summary)),
        )
        finding.id = stable_hash("hackernews", finding.url or finding.title, finding.source)
        findings.append(finding)
    return findings


_ROBOTS_CACHE: dict[str, RobotFileParser | None] = {}


def robots_allowed(session: requests.Session, url: str, user_agent: str, timeout: int) -> bool:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return False
    base = f"{parsed.scheme}://{parsed.netloc}"
    if base in _ROBOTS_CACHE:
        parser = _ROBOTS_CACHE[base]
        return True if parser is None else parser.can_fetch(user_agent, url)

    robots_url = urljoin(base, "/robots.txt")
    parser = RobotFileParser()
    parser.set_url(robots_url)
    try:
        resp = request_get(session, robots_url, timeout=timeout)
        parser.parse(resp.text.splitlines())
        _ROBOTS_CACHE[base] = parser
        return parser.can_fetch(user_agent, url)
    except Exception as exc:
        # If robots.txt is absent/unavailable, do not treat that as a global ban.
        logging.info("Could not read robots.txt for %s: %s", base, exc)
        _ROBOTS_CACHE[base] = None
        return True


def fetch_webpage_check(
    session: requests.Session,
    source: dict[str, Any],
    timeout: int,
    fetched_at: str,
    user_agent: str,
    max_bytes: int,
    respect_robots: bool,
) -> list[Finding]:
    url = str(source.get("url") or "").strip()
    if not url:
        raise ValueError("webpage_check source requires url")

    if respect_robots and not robots_allowed(session, url, user_agent, timeout):
        logging.info("Skipping %s because robots.txt disallows it.", url)
        return []

    resp = request_get(session, url, timeout=timeout, max_bytes=max_bytes)
    soup = BeautifulSoup(resp.text, "html.parser")
    title = normalize_ws(soup.title.get_text(" ") if soup.title else url)

    meta_description = ""
    meta = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
    if meta and meta.get("content"):
        meta_description = normalize_ws(str(meta.get("content")))

    text = normalize_ws(soup.get_text(" "))
    summary = truncate(meta_description or text)
    last_modified = resp.headers.get("Last-Modified")
    published_at = parse_datetime(last_modified)

    # Include a short content hash in the ID so meaningful page changes can resurface.
    content_fingerprint = stable_hash(title, summary, last_modified or "")

    finding = Finding(
        title=title,
        url=clean_url(url),
        source=str(source.get("name") or source.get("id")),
        source_type="webpage_check",
        published_at=published_at,
        fetched_at=fetched_at,
        summary=summary,
    )
    finding.id = stable_hash("webpage_check", finding.url, content_fingerprint)
    return [finding]


def fetch_manual_notes(source: dict[str, Any], fetched_at: str) -> list[Finding]:
    rel_path = str(source.get("path") or "inbox/manual_notes.md").strip()
    path = ROOT / rel_path
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)

    notes: list[str] = []
    for block in re.split(r"\n(?=\s*[-*]\s+\[[ xX]\])", text):
        cleaned = block.strip()
        if re.match(r"^\s*[-*]\s+\[[ xX]\]", cleaned):
            notes.append(cleaned)

    findings: list[Finding] = []
    for index, note in enumerate(notes[:50], start=1):
        summary = truncate(strip_html(note), 700)
        if not summary:
            continue
        title = f"Manual note #{index}"
        finding = Finding(
            title=title,
            url=rel_path,
            source=str(source.get("name") or source.get("id")),
            source_type="manual_note",
            published_at=None,
            fetched_at=fetched_at,
            summary=summary,
        )
        finding.id = stable_hash("manual_note", rel_path, summary)
        findings.append(finding)
    return findings


def keyword_specs(keywords_config: dict[str, Any], source: dict[str, Any]) -> list[dict[str, Any]]:
    specs = list(keywords_config.get("keywords") or [])
    # Source-specific keywords get a small weight; they help narrow context without
    # permanently modifying the global vocabulary.
    for kw in source_keywords(source):
        specs.append({"term": kw, "aliases": [kw], "weight": 2, "categories": ["source_specific"]})
    return specs


def contains_term(text: str, term: str) -> bool:
    term = term.strip()
    if not term:
        return False
    # Short tokens like AI/KI need word boundaries to avoid accidental matches.
    if len(term) <= 3 and term.isalnum():
        return bool(re.search(rf"\b{re.escape(term.lower())}\b", text))
    return term.lower() in text


def score_finding(finding: Finding, source: dict[str, Any], keywords_config: dict[str, Any], rules: dict[str, Any]) -> Finding:
    scoring = rules.get("scoring") or {}
    title_multiplier = float(scoring.get("title_multiplier", 1.4))
    url_multiplier = float(scoring.get("url_multiplier", 1.2))
    max_score = int(scoring.get("max_score", 100))

    title_text = finding.title.lower()
    summary_text = finding.summary.lower()
    url_text = finding.url.lower()
    combined_text = f"{title_text} {summary_text} {url_text} {finding.source.lower()}"

    matched: list[str] = []
    reasons: list[str] = []
    score = 0.0

    for spec in keyword_specs(keywords_config, source):
        term = str(spec.get("term") or "").strip()
        aliases = [str(a) for a in (spec.get("aliases") or [term])]
        weight = float(spec.get("weight") or 1)

        alias_matched = [alias for alias in aliases if contains_term(combined_text, alias)]
        if not alias_matched:
            continue

        matched.append(term)
        local_score = weight
        if any(contains_term(title_text, alias) for alias in aliases):
            local_score *= title_multiplier
        if any(contains_term(url_text, alias) for alias in aliases):
            local_score *= url_multiplier
        score += local_score
        reasons.append(f"{term} (+{local_score:.1f})")

    recent_bonus = scoring.get("recent_bonus") or {}
    if recent_bonus.get("enabled", True) and finding.published_at:
        try:
            published = datetime.fromisoformat(str(finding.published_at).replace("Z", "+00:00"))
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
            age_hours = (datetime.now(timezone.utc) - published.astimezone(timezone.utc)).total_seconds() / 3600
            if age_hours >= 0 and age_hours <= float(recent_bonus.get("within_hours", 72)):
                bonus = float(recent_bonus.get("points", 2))
                score += bonus
                reasons.append(f"recent (+{bonus:.1f})")
        except Exception:
            pass

    classification = rules.get("classification") or {}
    risk_terms = [str(x) for x in classification.get("risk_terms", [])]
    opportunity_terms = [str(x) for x in classification.get("opportunity_terms", [])]
    risk_hits = [x for x in risk_terms if contains_term(combined_text, x)]
    opportunity_hits = [x for x in opportunity_terms if contains_term(combined_text, x)]

    if risk_hits and opportunity_hits:
        finding.risk_or_opportunity = "mixed"
    elif risk_hits:
        finding.risk_or_opportunity = "risk"
    elif opportunity_hits:
        finding.risk_or_opportunity = "opportunity"
    else:
        finding.risk_or_opportunity = "observation"

    actions = rules.get("actions") or {}
    identity_terms = {"AXI0M", "User Yps"}
    if identity_terms.intersection(set(matched)):
        action = actions.get("identity_match")
    elif finding.risk_or_opportunity == "risk":
        action = actions.get("default_risk")
    elif finding.risk_or_opportunity == "opportunity":
        action = actions.get("default_opportunity")
    else:
        action = actions.get("default_observation")

    high_threshold = int(scoring.get("high_threshold", 18))
    if score >= high_threshold:
        action = f"{actions.get('high_priority', '').strip()} {action or ''}".strip()

    finding.matched_keywords = sorted(set(matched), key=str.lower)
    finding.relevance_score = min(max_score, int(round(score)))
    finding.relevance_reason = "; ".join(reasons) if reasons else "No configured keyword match."
    finding.recommended_action = action or "Beobachten und bei Wiederholung erneut bewerten."
    return finding


def fetch_source(
    session: requests.Session,
    source: dict[str, Any],
    env: dict[str, Any],
    rules: dict[str, Any],
    fetched_at: str,
) -> list[Finding]:
    source_type = str(source.get("type") or "").strip()
    max_items = int(source.get("max_items") or env["max_items"])
    timeout = int((rules.get("http") or {}).get("timeout_seconds", DEFAULT_TIMEOUT))
    user_agent = env["user_agent"]
    token = env.get("github_token")

    if source_type == "rss":
        return fetch_rss(session, source, max_items, timeout, fetched_at)
    if source_type == "github_search":
        return fetch_github_search(session, source, max_items, timeout, fetched_at, token)
    if source_type == "reddit_json":
        return fetch_reddit_json(session, source, max_items, timeout, fetched_at)
    if source_type == "hackernews":
        return fetch_hackernews(session, source, max_items, timeout, fetched_at)
    if source_type == "webpage_check":
        http_rules = rules.get("http") or {}
        return fetch_webpage_check(
            session=session,
            source=source,
            timeout=timeout,
            fetched_at=fetched_at,
            user_agent=user_agent,
            max_bytes=int(http_rules.get("max_bytes_per_webpage", 500000)),
            respect_robots=bool(http_rules.get("respect_robots_txt_for_webpage_check", True)),
        )
    if source_type == "manual_note":
        return fetch_manual_notes(source, fetched_at)

    raise ValueError(f"Unsupported source type: {source_type}")


def priority_sections(findings: list[Finding], rules: dict[str, Any]) -> tuple[list[Finding], list[Finding], list[Finding]]:
    scoring = rules.get("scoring") or {}
    high_threshold = int(scoring.get("high_threshold", 18))
    medium_threshold = int(scoring.get("medium_threshold", 8))
    observe_threshold = int(scoring.get("observe_threshold", 1))

    high = [f for f in findings if f.relevance_score >= high_threshold]
    medium = [f for f in findings if medium_threshold <= f.relevance_score < high_threshold]
    observe = [f for f in findings if observe_threshold <= f.relevance_score < medium_threshold]

    sort_key = lambda f: (f.relevance_score, f.published_at or "", f.title)
    return (
        sorted(high, key=sort_key, reverse=True),
        sorted(medium, key=sort_key, reverse=True),
        sorted(observe, key=sort_key, reverse=True),
    )


def markdown_link(url: str) -> str:
    if not url:
        return ""
    if url.startswith("http://") or url.startswith("https://"):
        return f" — [Quelle]({url})"
    return f" — `{url}`"


def render_finding_md(finding: Finding) -> str:
    keywords = ", ".join(finding.matched_keywords) if finding.matched_keywords else "keine"
    return (
        f"- **{finding.title}** — Score {finding.relevance_score}, "
        f"{finding.risk_or_opportunity}{markdown_link(finding.url)}\n"
        f"  - Quelle: {finding.source} / `{finding.source_type}`\n"
        f"  - Zeit: published `{finding.published_at or 'unbekannt'}`, fetched `{finding.fetched_at}`\n"
        f"  - Treffer: {keywords}\n"
        f"  - Warum relevant: {finding.relevance_reason}\n"
        f"  - Kurz: {finding.summary or 'Keine Zusammenfassung verfügbar.'}\n"
        f"  - Handlung: {finding.recommended_action}"
    )


def short_situation(high: list[Finding], medium: list[Finding], observe: list[Finding], errors: list[SourceError]) -> str:
    total = len(high) + len(medium) + len(observe)
    if total == 0:
        base = "Keine neuen relevanten Treffer aus den konfigurierten öffentlichen Quellen."
    else:
        top = high[0] if high else medium[0] if medium else observe[0]
        base = (
            f"{total} neue relevante Treffer. "
            f"Stärkstes Signal: „{top.title}“ aus {top.source} "
            f"(Score {top.relevance_score}, {top.risk_or_opportunity})."
        )
    if errors:
        base += f" {len(errors)} Quelle(n) hatten Abruffehler; Details stehen in latest.json."
    return base


def render_briefing_md(findings: list[Finding], errors: list[SourceError], rules: dict[str, Any]) -> str:
    high, medium, observe = priority_sections(findings, rules)
    briefing_rules = rules.get("briefing") or {}
    max_items = int(briefing_rules.get("max_items_per_section", 20))
    reminder_min_score = int(briefing_rules.get("reminder_candidate_min_score", 18))

    recommendations: list[str] = []
    for f in high + medium:
        if f.recommended_action and f.recommended_action not in recommendations:
            recommendations.append(f.recommended_action)

    reminder_candidates = [
        f for f in high + medium
        if f.relevance_score >= reminder_min_score
        and ({"AXI0M", "User Yps", "Produktidee", "Content-Chance"} & set(f.matched_keywords))
    ]

    lines: list[str] = [
        "# Senna Briefing",
        "",
        f"_Generiert: {now_iso()}_",
        "",
        "## Kurzlage",
        "",
        short_situation(high, medium, observe, errors),
        "",
        "## Priorität Hoch",
        "",
    ]

    lines.extend([render_finding_md(f) for f in high[:max_items]] or ["Keine neuen Hochprioritäts-Treffer."])
    lines.extend(["", "## Priorität Mittel", ""])
    lines.extend([render_finding_md(f) for f in medium[:max_items]] or ["Keine neuen mittleren Treffer."])
    lines.extend(["", "## Nur beobachten", ""])
    lines.extend([render_finding_md(f) for f in observe[:max_items]] or ["Keine neuen Beobachtungssignale."])
    lines.extend(["", "## Empfehlungen", ""])

    if recommendations:
        lines.extend([f"- {item}" for item in recommendations[:10]])
    else:
        lines.append("- Keine direkte Handlung. Konfigurierte Quellen weiter prüfen.")

    lines.extend(["", "## Erinnerungskandidaten", ""])
    if reminder_candidates:
        for f in reminder_candidates[:10]:
            lines.append(f"- **{f.title}** — {f.relevance_reason}{markdown_link(f.url)}")
    else:
        lines.append("- Keine neuen langfristigen Erinnerungskandidaten.")

    if errors and briefing_rules.get("include_source_errors", True):
        lines.extend(["", "## Quellenfehler", ""])
        for err in errors:
            lines.append(f"- `{err.source_id}` ({err.source_type}): {err.error}")

    lines.append("")
    return "\n".join(lines)


def merge_todays_findings(new_findings: list[Finding]) -> list[dict[str, Any]]:
    date_dir = DATA_DIR / today_str()
    path = date_dir / "findings.json"
    existing = read_json(path, [])
    if not isinstance(existing, list):
        existing = []

    by_id: dict[str, dict[str, Any]] = {}
    for item in existing:
        if isinstance(item, dict):
            item_id = str(item.get("id") or stable_hash(item.get("url", ""), item.get("title", "")))
            by_id[item_id] = item

    for finding in new_findings:
        by_id[finding.id] = asdict(finding)

    merged = sorted(
        by_id.values(),
        key=lambda x: (int(x.get("relevance_score") or 0), str(x.get("published_at") or ""), str(x.get("title") or "")),
        reverse=True,
    )
    write_json(path, merged)
    return merged


def write_outputs(new_findings: list[Finding], errors: list[SourceError], rules: dict[str, Any]) -> None:
    BRIEFINGS_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    merged_today = merge_todays_findings(new_findings)

    # latest is intentionally based on new findings from this run, not every
    # historical finding. Senna reads the current delta and can inspect data/.
    latest_md = render_briefing_md(new_findings, errors, rules)
    (BRIEFINGS_DIR / "latest.md").write_text(latest_md, encoding="utf-8")

    high, medium, observe = priority_sections(new_findings, rules)
    latest_json = {
        "generated_at": now_iso(),
        "date": today_str(),
        "scope": "configured_public_sources_only",
        "counts": {
            "new_relevant_findings": len(new_findings),
            "today_file_total": len(merged_today),
            "high": len(high),
            "medium": len(medium),
            "observe": len(observe),
            "source_errors": len(errors),
        },
        "sections": {
            "high": [asdict(f) for f in high],
            "medium": [asdict(f) for f in medium],
            "observe": [asdict(f) for f in observe],
        },
        "findings": [asdict(f) for f in sorted(new_findings, key=lambda f: f.relevance_score, reverse=True)],
        "source_errors": [asdict(e) for e in errors],
    }
    write_json(BRIEFINGS_DIR / "latest.json", latest_json)


def main() -> int:
    setup_logging()
    load_dotenv()

    sources_config = load_yaml(CONFIG_DIR / "sources.yaml", {})
    keywords_config = load_yaml(CONFIG_DIR / "keywords.yaml", {"keywords": []})
    rules = load_yaml(CONFIG_DIR / "rules.yaml", {})

    env = {
        "github_token": os.getenv("GITHUB_TOKEN", "").strip() or None,
        "user_agent": os.getenv("USER_AGENT", "senna-infoflow/1.0").strip() or "senna-infoflow/1.0",
        "max_items": int(os.getenv("MAX_ITEMS_PER_SOURCE", DEFAULT_MAX_ITEMS)),
    }

    sources = sources_config.get("sources") or []
    if not sources:
        logging.warning("No sources configured.")
        write_outputs([], [], rules)
        return 0

    session = build_session(env["user_agent"])
    state = load_seen()
    fetched_at = now_iso()
    polite_delay = float((rules.get("http") or {}).get("polite_delay_seconds", 1.0))

    new_relevant: list[Finding] = []
    errors: list[SourceError] = []

    for source in sources:
        if not source or source.get("enabled", sources_config.get("defaults", {}).get("enabled", True)) is False:
            continue

        source_id = str(source.get("id") or source.get("name") or "unknown_source")
        source_name = str(source.get("name") or source_id)
        source_type = str(source.get("type") or "unknown")

        try:
            logging.info("Fetching source %s (%s)", source_id, source_type)
            findings = fetch_source(session, source, env, rules, fetched_at)
        except Exception as exc:
            logging.exception("Source failed: %s", source_id)
            errors.append(SourceError(source_id=source_id, source_name=source_name, source_type=source_type, error=str(exc)))
            time.sleep(polite_delay)
            continue

        for finding in findings:
            # Ensure each item has an id even if a fetcher forgot to set one.
            if not finding.id:
                finding.id = stable_hash(finding.source_type, finding.url or finding.title, finding.source)

            already_seen = is_seen(state, finding)
            scored = score_finding(finding, source, keywords_config, rules)

            # Mark seen after scoring. This prevents repeated noise from old items.
            mark_seen(state, scored)

            if already_seen:
                continue
            if scored.relevance_score >= int((rules.get("scoring") or {}).get("observe_threshold", 1)):
                new_relevant.append(scored)

        time.sleep(polite_delay)

    # Dedupe across sources by id and URL/title fallback.
    deduped: dict[str, Finding] = {}
    for item in new_relevant:
        key = item.id or stable_hash(item.url, item.title)
        old = deduped.get(key)
        if old is None or item.relevance_score > old.relevance_score:
            deduped[key] = item

    final_findings = sorted(deduped.values(), key=lambda f: (f.relevance_score, f.published_at or ""), reverse=True)

    save_seen(state)
    write_outputs(final_findings, errors, rules)

    logging.info("Done. New relevant findings: %s; errors: %s", len(final_findings), len(errors))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
