#!/usr/bin/env python3
"""
geo_rank_check — проверка присутствия бренда в ответах LLM.

Поддерживает два режима:
  --mode georank  — через API GEOrank (https://lk.georank.ru)
  --mode direct    — напрямую через Perplexity / OpenAI / Яндекс API

Usage:
    # GEOrank (рекомендуемый)
    python3 geo_check.py --mode georank --api-key KEY --brand "Бренд" \
        --queries-file queries.csv --output results.json

    # Прямые API
    python3 geo_check.py --mode direct --brand "Бренд" \
        --url "https://example.com" \
        --queries-file queries.csv --output results.json \
        --providers perplexity openai \
        --perplexity-key KEY --openai-key KEY

    python3 geo_check.py --help   # полная справка
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.request
import urllib.parse
import urllib.error
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Optional


# ─── Модель данных ────────────────────────────────────────────────────────────

@dataclass
class QueryResult:
    query: str
    intent: str = "unknown"
    provider: str = ""
    model: str = ""
    found: bool = False
    position: Optional[int] = None
    context: str = ""
    citation_url: str = ""
    sentiment: str = "neutral"  # positive / neutral / negative / not_found
    error: str = ""


@dataclass
class GeoCheckResult:
    brand: str
    url: str
    checked_at: str
    total_queries: int
    llm_visibility_score: int
    mode: str
    providers: list[str]
    results: list[QueryResult] = field(default_factory=list)
    summary: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "brand": self.brand,
            "url": self.url,
            "checked_at": self.checked_at,
            "total_queries": self.total_queries,
            "llm_visibility_score": self.llm_visibility_score,
            "mode": self.mode,
            "providers": self.providers,
            "results": [asdict(r) for r in self.results],
            "summary": self.summary,
        }


# ─── CSV-парсер запросов ───────────────────────────────────────────────────────

def load_queries(path: str) -> list[dict]:
    """Загружает запросы из CSV. Ожидает колонки: query[, intent][, model]."""
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            q = (row.get("query") or row.get("q") or "").strip()
            if not q:
                continue
            rows.append({
                "query": q,
                "intent": (row.get("intent") or "any").strip().lower(),
                "model": (row.get("model") or "any").strip().lower(),
            })
    return rows


# ─── GEOrank API ──────────────────────────────────────────────────────────────

def check_georank(
    api_key: str,
    brand: str,
    queries: list[dict],
    *,
    delay: float = 1.0,
) -> list[QueryResult]:
    """
    Проверяет присутствие бренда через GEOrank API.

    Документация API: https://lk.georank.ru/docs/manual.pdf
    BASE_URL задан исходя из текущей структуры личного кабинета.
    """
    base_url = "https://api.georank.ru/v1"
    results: list[QueryResult] = []

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "geo-rank-check/1.0 (SEO workshop)",
    }

    for item in queries:
        qr = QueryResult(query=item["query"], intent=item["intent"])

        payload = json.dumps({
            "query": item["query"],
            "brand": brand,
            "include_context": True,
            "include_citations": True,
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{base_url}/check",
            data=payload,
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            qr.provider = "georank"
            qr.model = data.get("model", "unknown")

            found_items = data.get("found_items", [])
            if found_items:
                qr.found = True
                qr.position = found_items[0].get("position")
                qr.context = found_items[0].get("context", "")[:500]
                qr.citation_url = found_items[0].get("url", "")
                qr.sentiment = found_items[0].get("sentiment", "neutral")
            else:
                qr.found = False
                qr.sentiment = "not_found"

        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if exc.code == 401:
                qr.error = f"georank: 401 Unauthorized — проверьте API-ключ"
            elif exc.code == 429:
                qr.error = f"georank: 429 Rate limit exceeded — увеличьте delay"
                time.sleep(delay * 2)
            else:
                qr.error = f"georank: HTTP {exc.code} — {body[:200]}"

        except urllib.error.URLError as exc:
            qr.error = f"georank: network error — {exc.reason}"

        except json.JSONDecodeError:
            qr.error = "georank: не удалось распарсить ответ"

        except Exception as exc:
            qr.error = f"georank: {type(exc).__name__}: {exc}"

        results.append(qr)
        time.sleep(delay)

    return results


# ─── Perplexity API ───────────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    """Убирает лишние пробелы и приводит к нижнему регистру."""
    return re.sub(r"\s+", " ", text).strip().lower()


def _brand_in_response(text: str, brand: str, url: str) -> tuple[bool, str, str, int]:
    """
    Проверяет, упоминается ли бренд/URL в тексте ответа.

    Возвращает (found, context, citation_url, position).
    Position = порядковый номер вхождения (1-based).
    """
    text_lower = _normalize(text)
    brand_lower = _normalize(brand)
    url_lower = url.lower()

    # Стратегия поиска: точное вхождение бренда важнее URL
    brand_pattern = re.escape(brand_lower)
    url_pattern = re.escape(url_lower)

    found = False
    position = 0
    context = ""
    citation_url = ""

    # 1. Ищем URL-ссылки
    url_matches = list(re.finditer(url_pattern, text_lower))
    if url_matches:
        found = True
        position = url_matches[0].start()  # используем позицию в тексте как суррогат
        start = max(0, url_matches[0].start() - 100)
        end = min(len(text), url_matches[0].end() + 200)
        context = text[start:end]
        citation_url = url

    # 2. Ищем название бренда (если URL не нашёлся или нашёлся доп. вхождение)
    brand_matches = list(re.finditer(brand_pattern, text_lower))
    if brand_matches and not found:
        found = True
        m = brand_matches[0]
        start = max(0, m.start() - 150)
        end = min(len(text), m.end() + 200)
        context = text[start:end]
        position = m.start()

    return found, context, citation_url, position


def check_perplexity(
    api_key: str,
    brand: str,
    url: str,
    queries: list[dict],
    *,
    model: str = "sonar",
    delay: float = 2.0,
    timeout: int = 45,
) -> list[QueryResult]:
    """
    Проверяет присутствие через Perplexity Sonar API.
    https://docs.perplexity.ai/docs/api-reference
    """
    results: list[QueryResult] = []

    for item in queries:
        qr = QueryResult(query=item["query"], intent=item["intent"])
        qr.provider = "perplexity"
        qr.model = model

        payload = json.dumps({
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": (
                        f"Ответь на вопрос: {item['query']}\n\n"
                        f"Упомяни бренд '{brand}' ({url}) только если он релевантен. "
                        "В ответе дай список рекомендуемых решений с кратким описанием каждого."
                    )
                }
            ],
            "max_tokens": 512,
            "temperature": 0.2,
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://api.perplexity.ai/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "geo-rank-check/1.0",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            answer = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )

            found, context, citation_url, position = _brand_in_response(
                answer, brand, url
            )
            qr.found = found
            qr.context = context
            qr.citation_url = citation_url
            qr.position = position

            if not found:
                qr.sentiment = "not_found"
            else:
                qr.sentiment = "neutral"

        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if exc.code == 429:
                qr.error = f"perplexity: 429 Rate limit — нужен delay"
                time.sleep(delay * 3)
            else:
                qr.error = f"perplexity: HTTP {exc.code} — {body[:200]}"
        except Exception as exc:
            qr.error = f"perplexity: {type(exc).__name__}: {exc}"

        results.append(qr)
        time.sleep(delay)

    return results


# ─── OpenAI API ───────────────────────────────────────────────────────────────

def check_openai(
    api_key: str,
    brand: str,
    url: str,
    queries: list[dict],
    *,
    model: str = "gpt-4o-mini",
    delay: float = 2.0,
    timeout: int = 45,
) -> list[QueryResult]:
    """Проверяет присутствие через OpenAI Chat Completions API."""
    results: list[QueryResult] = []

    for item in queries:
        qr = QueryResult(query=item["query"], intent=item["intent"])
        qr.provider = "openai"
        qr.model = model

        payload = json.dumps({
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": (
                        f"Пользователь спрашивает: {item['query']}\n\n"
                        f"Дай развёрнутый ответ, упоминая бренд '{brand}' "
                        f"({url}) только если он действительно релевантен. "
                        "Перечисли 3–5 решений с кратким описанием."
                    )
                }
            ],
            "max_tokens": 512,
            "temperature": 0.3,
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "geo-rank-check/1.0",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            answer = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )

            found, context, citation_url, position = _brand_in_response(
                answer, brand, url
            )
            qr.found = found
            qr.context = context
            qr.citation_url = citation_url
            qr.position = position
            qr.sentiment = "not_found" if not found else "neutral"

        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if exc.code == 429:
                qr.error = f"openai: 429 Rate limit — нужен delay"
                time.sleep(delay * 3)
            else:
                qr.error = f"openai: HTTP {exc.code} — {body[:200]}"
        except Exception as exc:
            qr.error = f"openai: {type(exc).__name__}: {exc}"

        results.append(qr)
        time.sleep(delay)

    return results


# ─── Яндекс API (GigaChat) ────────────────────────────────────────────────────

def check_yandexgpt(
    api_key: str,
    brand: str,
    url: str,
    queries: list[dict],
    *,
    model: str = "gpt://b1gpp0i0ek9dl5i9qg9g/yandexgpt-lite",
    delay: float = 2.0,
    timeout: int = 45,
) -> list[QueryResult]:
    """Проверяет присутствие через Яндекс API (GigaChat / ЯндексGPT)."""
    results: list[QueryResult] = []

    for item in queries:
        qr = QueryResult(query=item["query"], intent=item["intent"])
        qr.provider = "yandex"
        qr.model = model

        payload = json.dumps({
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": (
                        f"Пользователь спрашивает: {item['query']}\n\n"
                        f"Дай развёрнутый ответ. Упомяни бренд '{brand}' "
                        f"({url}), только если он релевантен. "
                        "Перечисли 3–5 решений с описанием."
                    )
                }
            ],
            "max_tokens": 512,
            "temperature": 0.3,
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://llm.api.cloud.yandex.net/llm/v1/chat",
            data=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "geo-rank-check/1.0",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            answer = (
                data.get("result", {})
                .get("message", {})
                .get("content", "")
            )

            found, context, citation_url, position = _brand_in_response(
                answer, brand, url
            )
            qr.found = found
            qr.context = context
            qr.citation_url = citation_url
            qr.position = position
            qr.sentiment = "not_found" if not found else "neutral"

        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            qr.error = f"yandex: HTTP {exc.code} — {body[:200]}"
        except Exception as exc:
            qr.error = f"yandex: {type(exc).__name__}: {exc}"

        results.append(qr)
        time.sleep(delay)

    return results


# ─── Сводка по интентам ──────────────────────────────────────────────────────

def summarize(results: list[QueryResult]) -> dict:
    intents = ["branded", "comparing", "informing", "commercial", "unknown"]
    summary = {}
    for intent in intents:
        subset = [r for r in results if r.intent == intent]
        if not subset:
            continue
        found_count = sum(1 for r in subset if r.found)
        total = len(subset)
        summary[intent] = {
            "total": total,
            "found": found_count,
            "visibility": round(found_count / total * 100) if total else 0,
        }
    summary["not_found_queries"] = [
        r.query for r in results if not r.found and not r.error
    ]
    return summary


def visibility_score(results: list[QueryResult]) -> int:
    total = len(results)
    if total == 0:
        return 0
    found = sum(1 for r in results if r.found)
    return round(found / total * 100)


# ─── CLI ──────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="GEO Rank Check: проверка присутствия бренда в ответах LLM.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    p.add_argument("--mode", choices=["georank", "direct"], default="direct",
                   help="Режим: georank (через API GEOrank) или direct (напрямую)")

    p.add_argument("--brand", required=True, help="Название бренда для поиска")
    p.add_argument("--url", help="URL бренда (для режима direct)")
    p.add_argument("--queries-file", required=True,
                   help="CSV с колонками: query[, intent][, model]")

    p.add_argument("--output", "-o", default="geo-results.json",
                   help="Выходной JSON-файл (по умолчанию geo-results.json)")

    # GEOrank
    p.add_argument("--api-key", help="GEOrank API-ключ (или GEORANK_API_KEY)")
    p.add_argument("--delay", type=float, default=1.0,
                   help="Пауза между запросами, сек (по умолчанию 1.0)")

    # Прямые API
    p.add_argument("--providers", nargs="+",
                   choices=["perplexity", "openai", "yandex"],
                   default=["perplexity"],
                   help="Провайдеры для режима direct")
    p.add_argument("--perplexity-key", help="Perplexity API-ключ (или PERPLEXITY_API_KEY)")
    p.add_argument("--openai-key", help="OpenAI API-ключ (или OPENAI_API_KEY)")
    p.add_argument("--yandex-key", help="Яндекс API IAM-токен (или YANDEX_API_KEY)")
    p.add_argument("--perplexity-model", default="sonar",
                   help="Модель Perplexity (по умолчанию sonar)")
    p.add_argument("--openai-model", default="gpt-4o-mini",
                   help="Модель OpenAI (по умолчанию gpt-4o-mini)")
    p.add_argument("--timeout", type=int, default=45,
                   help="Таймаут одного запроса, сек (по умолчанию 45)")
    p.add_argument("--dry-run", action="store_true",
                   help="Показать запросы без отправки (для отладки)")

    return p


def main() -> None:
    args = _build_parser().parse_args()

    # ── Загрузка запросов ──────────────────────────────────────────────────
    if not os.path.exists(args.queries_file):
        print(f"ERROR: файл не найден: {args.queries_file}", file=sys.stderr)
        sys.exit(1)

    queries = load_queries(args.queries_file)
    if not queries:
        print("ERROR: в файле нет валидных запросов", file=sys.stderr)
        sys.exit(1)

    # ── API-ключи ─────────────────────────────────────────────────────────
    if args.mode == "georank":
        api_key = args.api_key or os.environ.get("GEORANK_API_KEY", "")
        if not api_key:
            print("ERROR: нужен --api-key или GEORANK_API_KEY", file=sys.stderr)
            sys.exit(1)
    else:
        api_key = None

    perplexity_key = args.perplexity_key or os.environ.get("PERPLEXITY_API_KEY", "")
    openai_key = args.openai_key or os.environ.get("OPENAI_API_KEY", "")
    yandex_key = args.yandex_key or os.environ.get("YANDEX_API_KEY", "")

    # ── Dry run ───────────────────────────────────────────────────────────
    if args.dry_run:
        print(f"[DRY RUN] Режим: {args.mode}")
        print(f"Бренд: {args.brand}")
        print(f"URL: {args.url}")
        print(f"Запросов: {len(queries)}")
        for q in queries:
            print(f"  - [{q['intent']}] {q['query']}")
        sys.exit(0)

    # ── Выполнение ────────────────────────────────────────────────────────
    all_results: list[QueryResult] = []

    if args.mode == "georank":
        print(f"→ GEOrank API, {len(queries)} запросов")
        all_results = check_georank(api_key, args.brand, queries, delay=args.delay)

    else:  # direct
        for provider in args.providers:
            key_map = {
                "perplexity": perplexity_key,
                "openai": openai_key,
                "yandex": yandex_key,
            }
            key = key_map[provider]
            if not key:
                print(f"⚠ Пропуск {provider}: ключ не найден", file=sys.stderr)
                continue

            print(f"→ {provider}, {len(queries)} запросов")

            if provider == "perplexity":
                batch = check_perplexity(
                    key, args.brand, args.url or "",
                    queries, model=args.perplexity_model,
                    delay=args.delay, timeout=args.timeout,
                )
            elif provider == "openai":
                batch = check_openai(
                    key, args.brand, args.url or "",
                    queries, model=args.openai_model,
                    delay=args.delay, timeout=args.timeout,
                )
            elif provider == "yandex":
                batch = check_yandexgpt(
                    key, args.brand, args.url or "",
                    queries, delay=args.delay, timeout=args.timeout,
                )
            else:
                continue

            all_results.extend(batch)

    # ── Результат ─────────────────────────────────────────────────────────
    if not all_results:
        print("ERROR: не удалось получить результаты ни от одного провайдера",
              file=sys.stderr)
        sys.exit(1)

    score = visibility_score(all_results)
    summary = summarize(all_results)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    result_obj = GeoCheckResult(
        brand=args.brand,
        url=args.url or "",
        checked_at=now,
        total_queries=len(queries),
        llm_visibility_score=score,
        mode=args.mode,
        providers=args.providers if args.mode == "direct" else ["georank"],
        results=all_results,
        summary=summary,
    )

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result_obj.to_dict(), f, ensure_ascii=False, indent=2)

    # ── Консольная сводка ─────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"LLM Visibility Score: {score}/100")
    print(f"Провайдеры: {', '.join(result_obj.providers)}")
    print(f"Проверено запросов: {len(all_results)}")

    for intent, stat in summary.items():
        if isinstance(stat, dict):
            print(f"  {intent:<15} {stat['found']}/{stat['total']} "
                  f"({stat['visibility']}%)")

    if summary.get("not_found_queries"):
        print(f"\nНе найдены ({len(summary['not_found_queries'])}):")
        for q in summary["not_found_queries"][:5]:
            print(f"  — {q}")
        if len(summary["not_found_queries"]) > 5:
            print(f"  ... и ещё {len(summary['not_found_queries']) - 5}")

    errors = [r for r in all_results if r.error]
    if errors:
        print(f"\nОшибок: {len(errors)}")
        for e in errors[:3]:
            print(f"  [{e.query[:50]}] {e.error}")

    print(f"\nРезультат сохранён: {args.output}")


if __name__ == "__main__":
    main()
