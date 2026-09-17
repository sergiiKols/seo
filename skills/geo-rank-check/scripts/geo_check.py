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
import hashlib
import json
import os
import random
import re
import socket
import sys
import time
import urllib.request
import urllib.parse
import urllib.error
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Optional


# ─── Протокол исполнения (masterskie/shablony/STANDART-SKILLA.md) ─────────────

EXIT_OK, EXIT_ERROR, EXIT_NEEDS_INPUT, EXIT_NEEDS_SANCTION = 0, 1, 10, 20

# Закрыто по умолчанию: провайдер платный, пока бесплатность не подтверждена
# первоисточником. Проверка 16.09.2026: ни у одного не подтверждена
# (Perplexity Sonar по вторичным источникам — $5–14 за 1000 запросов + токены).
FREE_PROVIDERS: set[str] = set()

KEY_ENV = {
    "georank": "GEORANK_API_KEY",
    "perplexity": "PERPLEXITY_API_KEY",
    "openai": "OPENAI_API_KEY",
    "yandex": "YANDEX_API_KEY",
}
KEY_WHERE = {
    "georank": "https://lk.georank.ru/",
    "perplexity": "https://www.perplexity.ai/settings/api",
    "openai": "https://platform.openai.com/api-keys",
    "yandex": "https://console.yandex.cloud/",
}


def emit(kind: str, code: int, **fields) -> None:
    """Последний блок вывода — маркер для агента, затем выход с кодом."""
    print(f"\n{kind}")
    for k, v in fields.items():
        print(f"{k}={v}")
    sys.stdout.flush()
    sys.exit(code)


# ─── Ретраи (razbory/ekspl-03): экспоненциальная задержка + полный джиттер ────

RETRY_LIMIT = 2            # повторов сверх первой попытки; задаётся --retries
RETRY_BASE, RETRY_CAP = 1.0, 30.0
RETRYABLE_HTTP = {429, 500, 502, 503, 504}
RETRIES_USED = 0           # сколько повторов сделано — каждый платный


def _request_json(req: urllib.request.Request, timeout: float) -> dict:
    """POST с ретраями только временных сбоев: 429, 5xx, сеть, таймаут.

    401/400/403 не повторяются — ключ или запрос от повтора не исправятся.
    429 с Retry-After ждёт столько, сколько сказал сервер (не больше потолка).
    """
    global RETRIES_USED
    for attempt in range(RETRY_LIMIT + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code not in RETRYABLE_HTTP or attempt == RETRY_LIMIT:
                raise
            after = (exc.headers or {}).get("Retry-After")
            wait = (min(float(after), RETRY_CAP) if after and after.replace(".", "", 1).isdigit()
                    else random.uniform(0, min(RETRY_CAP, RETRY_BASE * 2 ** attempt)))
        except (urllib.error.URLError, socket.timeout, TimeoutError):
            if attempt == RETRY_LIMIT:
                raise
            wait = random.uniform(0, min(RETRY_CAP, RETRY_BASE * 2 ** attempt))
        RETRIES_USED += 1
        time.sleep(wait)
    raise RuntimeError("недостижимо")


class _Parser(argparse.ArgumentParser):
    """argparse выходит с кодом 2, а он в стандарте занят стоп-находками."""

    def error(self, message: str) -> None:
        print(f"ERROR: {message}", file=sys.stderr)
        emit("SKILL_ERROR", EXIT_ERROR, STAGE="аргументы", ERROR=message)


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
    run: int = 1  # номер прогона (при --runs N один запрос проверяется N раз)
    # Разбор присутствия (разбор seo-04): раньше это было одно поле found.
    mention: bool = False       # бренд назван в тексте ответа
    citation: bool = False      # наш адрес в источниках ответа, имени может не быть
    ambiguous: bool = False     # имя нашлось, но подтверждения, что это мы, нет
    anchor: str = ""            # чем подтверждено, что назвали именно нас
    citation_rank: Optional[int] = None  # место нашего адреса в списке источников


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
    apr: dict = field(default_factory=dict)
    scores: dict = field(default_factory=dict)
    anchors: list[str] = field(default_factory=list)
    otpechatok: str = ""
    trend: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "brand": self.brand,
            "url": self.url,
            "checked_at": self.checked_at,
            "total_queries": self.total_queries,
            "llm_visibility_score": self.llm_visibility_score,
            "scores": self.scores,
            "anchors": self.anchors,
            "otpechatok": self.otpechatok,
            "trend": self.trend,
            "mode": self.mode,
            "providers": self.providers,
            "results": [asdict(r) for r in self.results],
            "summary": self.summary,
            "apr": self.apr,
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
            data = _request_json(req, timeout=30)

            qr.provider = "georank"
            qr.model = data.get("model", "unknown")

            found_items = data.get("found_items", [])
            if found_items:
                # GEOrank отдаёт готовый вердикт и не делит упоминание и
                # цитирование: его находка считается упоминанием, проверка
                # на однофамильцев остаётся за сервисом (мы её не видим).
                qr.found = True
                qr.mention = True
                qr.anchor = "вердикт georank"
                qr.position = found_items[0].get("position")
                qr.context = found_items[0].get("context", "")[:500]
                qr.citation_url = found_items[0].get("url", "")
                qr.citation = bool(qr.citation_url)
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


# ─── Присутствие в ответе: три разных события ────────────────────────────────
# Разбор seo-04 (ролик про «три имени», 17.09.2026). Раньше упоминание бренда и
# наличие нашего адреса давали один и тот же признак found, и балл видимости
# складывал «нас назвали» с «нас молча использовали как источник». Это разные
# результаты: во втором случае клиент получил наш ответ и не узнал, чей он.
# Третье событие — совпало имя, а не объект: у бренда-словарного слова или
# фамилии подстрочный поиск даёт ложное попадание.

ANCHOR_WINDOW = 300   # символов вокруг имени, где ищется подтверждающее слово


@dataclass
class Presence:
    mention: bool = False
    citation: bool = False
    ambiguous: bool = False
    anchor: str = ""
    context: str = ""
    citation_url: str = ""
    citation_rank: Optional[int] = None
    position: Optional[int] = None

    @property
    def found(self) -> bool:
        """Присутствие: подтверждённое упоминание или цитирование.
        Спорное имя без подтверждения присутствием не считается."""
        return (self.mention and not self.ambiguous) or self.citation


def _domain_of(url: str) -> str:
    """Хост без схемы и www: сравнивать надо домен, а не точную строку URL."""
    raw = url.strip()
    if not raw:
        return ""
    host = urllib.parse.urlsplit(raw if "//" in raw else "//" + raw).netloc.lower()
    host = host.split("@")[-1].split(":")[0]
    return host[4:] if host.startswith("www.") else host


PADEZH_TAIL = 3  # допуск на русское окончание: «Новосибирск» → «Новосибирске»


def _word_re(needle: str, tail: int = PADEZH_TAIL) -> Optional[re.Pattern]:
    """Имя с границей слова слева и падежным окончанием справа.

    \\b сам по себе не годится: бренд может начинаться и кончаться не буквой
    («1С», «ideav.ru»), поэтому граница задана отрицательным взглядом на \\w.
    Хвост до трёх букв нужен русскому языку — «студия Идеава» и «в
    Новосибирске» это то же слово. При tail=0 сравнение точное: так ищется
    домен, у которого окончаний не бывает.
    """
    esc = re.escape(needle.strip())
    if not esc:
        return None
    hvost = rf"\w{{0,{tail}}}" if tail else ""
    return re.compile(rf"(?<!\w){esc}{hvost}(?!\w)", re.IGNORECASE)


def anchors_for(url: str, extra) -> list[str]:
    """Слова, подтверждающие, что назвали именно нас: домен, его имя и то,
    что задано через --anchors (город, продукт, фамилия основателя)."""
    out = [s.strip() for s in (extra or []) if s and s.strip()]
    dom = _domain_of(url)
    if dom:
        out.append(dom)
        head = dom.split(".")[0]
        if len(head) > 2:
            out.append(head)
    return list(dict.fromkeys(out))


def _brand_in_response(
    text: str,
    brand: str,
    url: str,
    anchors: Optional[list[str]] = None,
    citations: Optional[list[str]] = None,
) -> Presence:
    """Разбирает ответ на упоминание, цитирование и спорное совпадение имени."""
    p = Presence()
    text = text or ""
    dom = _domain_of(url)
    anchors = anchors if anchors is not None else anchors_for(url, [])

    # 1. Цитирование: наш домен в списке источников провайдера или в тексте.
    if dom:
        for i, src in enumerate(citations or [], start=1):
            if _domain_of(src) == dom or dom in (src or "").lower():
                p.citation = True
                p.citation_url = src
                p.citation_rank = i
                break
        if not p.citation:
            dom_rx = _word_re(dom, tail=0)
            hit = dom_rx.search(text) if dom_rx else None
            if hit:
                p.citation = True
                p.citation_url = url
                p.position = hit.start()
                p.context = text[max(0, hit.start() - 100):hit.end() + 200]

    # 2. Упоминание: имя бренда в тексте, по границам слова.
    rx = _word_re(brand)
    m = rx.search(text) if rx else None
    if m:
        p.mention = True
        p.position = m.start()
        p.context = text[max(0, m.start() - 150):m.end() + 200]

        # 3. Подтверждение объекта: наш адрес где-то в ответе или якорь рядом
        #    с именем. Иначе это может быть другой объект с тем же названием.
        window = text[max(0, m.start() - ANCHOR_WINDOW):m.end() + ANCHOR_WINDOW]
        for a in anchors:
            arx = _word_re(a)
            if arx and arx.search(window):
                p.anchor = a
                break
        if not p.anchor and p.citation:
            p.anchor = "источник"
        p.ambiguous = not p.anchor

    return p


def _apply(qr: QueryResult, p: Presence) -> None:
    """Переносит разбор присутствия в результат запроса."""
    qr.found = p.found
    qr.mention = p.mention
    qr.citation = p.citation
    qr.ambiguous = p.ambiguous
    qr.anchor = p.anchor
    qr.context = p.context
    qr.citation_url = p.citation_url
    qr.citation_rank = p.citation_rank
    qr.position = p.position
    qr.sentiment = "neutral" if p.found else "not_found"


def _citations_of(data: dict) -> list[str]:
    """Список источников ответа — там, где провайдер его отдаёт.

    У Perplexity это citations (плоский список URL) или search_results
    (объекты с url). У обычного chat-completions источников нет вовсе —
    тогда цитирование видно только по адресу в тексте ответа.
    """
    out: list[str] = []
    for src in data.get("citations") or []:
        if isinstance(src, str):
            out.append(src)
        elif isinstance(src, dict) and src.get("url"):
            out.append(src["url"])
    for src in data.get("search_results") or []:
        if isinstance(src, dict) and src.get("url"):
            out.append(src["url"])
    return list(dict.fromkeys(out))


def check_perplexity(
    api_key: str,
    brand: str,
    url: str,
    queries: list[dict],
    *,
    model: str = "sonar",
    delay: float = 2.0,
    timeout: int = 45,
    anchors: Optional[list[str]] = None,
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
            data = _request_json(req, timeout=timeout)

            answer = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )

            _apply(qr, _brand_in_response(
                answer, brand, url, anchors, _citations_of(data)))

        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if exc.code == 429:
                qr.error = f"perplexity: 429 Rate limit — нужен delay"
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
    base_url: str = "https://api.openai.com/v1",
    anchors: Optional[list[str]] = None,
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
            f"{base_url.rstrip('/')}/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "geo-rank-check/1.0",
            },
            method="POST",
        )

        try:
            data = _request_json(req, timeout=timeout)

            answer = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )

            _apply(qr, _brand_in_response(
                answer, brand, url, anchors, _citations_of(data)))

        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if exc.code == 429:
                qr.error = f"openai: 429 Rate limit — нужен delay"
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
    anchors: Optional[list[str]] = None,
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
            data = _request_json(req, timeout=timeout)

            answer = (
                data.get("result", {})
                .get("message", {})
                .get("content", "")
            )

            _apply(qr, _brand_in_response(
                answer, brand, url, anchors, _citations_of(data)))

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
        checked = sum(1 for r in subset if not r.error)
        summary[intent] = {
            "total": total,
            "found": found_count,
            "errors": total - checked,
            "visibility": round(found_count / checked * 100) if checked else 0,
        }
    # Спорное совпадение имени — не «нас нет»: мы не знаем, о нас ли речь.
    # Поэтому в «не найдены» такие запросы не идут, у них свой список.
    summary["not_found_queries"] = [
        r.query for r in results if not r.found and not r.ambiguous and not r.error
    ]
    # Цитирование без упоминания: наш ответ использован, имя не названо.
    summary["silent_citations"] = [
        {"query": r.query, "provider": r.provider, "rank": r.citation_rank}
        for r in results if r.citation and not r.mention and not r.error
    ]
    # Совпало имя, а не объект: подтверждения нет, в балл не берётся.
    summary["ambiguous_queries"] = [
        {"query": r.query, "provider": r.provider, "context": r.context[:200]}
        for r in results if r.ambiguous and not r.error
    ]
    return summary


def visibility_score(results: list[QueryResult]) -> int:
    # Запрос с ошибкой не ответ «бренда нет»: в знаменатель не входит.
    checked = [r for r in results if not r.error]
    if not checked:
        return 0
    found = sum(1 for r in checked if r.found)
    return round(found / len(checked) * 100)


def scores(results: list[QueryResult]) -> dict:
    """Три числа вместо одного (разбор seo-04).

    presence — присутствие: назвали или процитировали;
    mention  — назвали по имени, подтверждённо;
    citation — взяли как источник, независимо от того, назвали ли.

    Знаменатель у всех трёх один: запросы без ошибки. Разные знаменатели
    здесь дали бы несравнимые проценты.
    """
    checked = [r for r in results if not r.error]
    n = len(checked)
    if not n:
        return {"presence": 0, "mention": 0, "citation": 0,
                "silent_citations": 0, "ambiguous": 0, "denominator": 0}
    pct = lambda k: round(k / n * 100)
    return {
        "presence": pct(sum(1 for r in checked if r.found)),
        "mention": pct(sum(1 for r in checked if r.mention and not r.ambiguous)),
        "citation": pct(sum(1 for r in checked if r.citation)),
        "silent_citations": sum(1 for r in checked if r.citation and not r.mention),
        "ambiguous": sum(1 for r in checked if r.ambiguous),
        "denominator": n,
    }


# ─── Ряд замеров: видимость меняется сама ────────────────────────────────────
# Разбор seo-04: у автора ролика было 4 упоминания в сентябре и 0 через год,
# при том что он ничего не менял. Одиночный замер этого не показывает, поэтому
# прогоны складываются в файл и сравниваются с предыдущим.
#
# Сравнивать можно только одинаковое: отпечаток считается по набору запросов
# и списку провайдеров. Разошёлся отпечаток — сравнение не выводится, иначе
# падение балла объяснялось бы «нас стали хуже называть», а на деле сменили
# набор запросов.

def zamer_otpechatok(queries: list[dict], providers: list[str]) -> str:
    payload = json.dumps(
        {"queries": sorted(q["query"].strip().lower() for q in queries),
         "providers": sorted(providers)},
        ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def istoriya_prochitat(path: str, brand: str) -> list[dict]:
    """Прошлые замеры этого бренда, в порядке записи. Битые строки пропускаются."""
    if not path or not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("brand") == brand:
                out.append(rec)
    return out


def trend(prev: Optional[dict], cur: dict, otpechatok: str) -> dict:
    """Изменение против прошлого замера — или причина, почему сравнения нет."""
    if not prev:
        return {"comparable": False,
                "why": "первый замер этого бренда в файле истории"}
    if prev.get("otpechatok") != otpechatok:
        return {"comparable": False, "prev_at": prev.get("checked_at"),
                "why": "набор запросов или список провайдеров изменился — "
                       "числа несравнимы"}
    return {
        "comparable": True,
        "prev_at": prev.get("checked_at"),
        "presence": cur["presence"] - prev.get("presence", 0),
        "mention": cur["mention"] - prev.get("mention", 0),
        "citation": cur["citation"] - prev.get("citation", 0),
    }


def istoriya_dopisat(path: str, rec: dict) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


# ─── APR: Answer Presence Rate (habr 1046259, разбор apr-2026-09) ────────────
# Один прогон LLM — не сигнал: у цитирования заметная случайность, поэтому
# каждый запрос проверяется несколько раз, стабильность источника считается
# как доля прогонов, в которых бренд попал в ответ. Порог 20% — из статьи:
# источники с APR ниже отсекались как шум.

APR_THRESHOLD = 0.2  # источник считается «стабильным» при APR >= 20%


def apr_report(results: list[QueryResult]) -> dict:
    """Считает APR по (запрос × провайдер) из результатов повторных прогонов."""
    by_key: dict[tuple[str, str], list[QueryResult]] = {}
    for r in results:
        if not r.error:
            by_key.setdefault((r.query, r.provider), []).append(r)

    per_query = []
    for (query, provider), runs in by_key.items():
        runs_count = len(runs)
        found_count = sum(1 for r in runs if r.found)
        per_query.append({
            "query": query,
            "provider": provider,
            "runs": runs_count,
            "found_runs": found_count,
            "apr": round(found_count / runs_count * 100),
        })

    if not per_query:
        return {"runs_per_query": 1, "stable_queries": [], "per_query": []}

    stable = [q for q in per_query if q["apr"] >= APR_THRESHOLD * 100]
    overall = round(sum(q["apr"] for q in per_query) / len(per_query))
    return {
        "runs_per_query": max(q["runs"] for q in per_query),
        "mean_apr": overall,
        "stable_queries": len(stable),
        "per_query": per_query,
    }


# ─── CLI ──────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = _Parser(
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
    p.add_argument("--base-url", default="https://api.openai.com/v1",
                   help="База OpenAI-совместимого API для провайдера openai; "
                        "любой локальный/прокси сервер с /chat/completions")
    p.add_argument("--timeout", type=int, default=45,
                   help="Таймаут одного запроса, сек (по умолчанию 45)")
    p.add_argument("--dry-run", action="store_true",
                   help="Показать запросы без отправки (для отладки)")
    p.add_argument("--retries", type=int, default=2,
                   help="Повторов временных сбоев (429, 5xx, сеть) на запрос; "
                        "0 — без повторов. Каждый повтор платный (по умолчанию 2)")
    p.add_argument("--anchors", nargs="+", default=[],
                   help="Слова, подтверждающие, что назвали именно нас: город, "
                        "продукт, фамилия основателя. Домен из --url добавляется "
                        "сам. Имя без подтверждения рядом идёт в «спорные», "
                        "а не в балл")
    p.add_argument("--history", metavar="FILE.jsonl",
                   help="Файл ряда замеров: прогон дописывается строкой, "
                        "и выводится изменение против прошлого замера с тем же "
                        "набором запросов и провайдеров")
    p.add_argument("--runs", type=int, default=1,
                   help="Прогонов на каждый запрос для APR (по умолчанию 1). "
                        "5–10 прогонов дают стабильность цитирования; "
                        "каждый прогон платный")
    p.add_argument("--sanction-spend", action="store_true",
                   help="Санкция человека на платные запросы ЭТОГО запуска. "
                        "Агент не добавляет флаг без явного согласия.")

    return p


def main() -> None:
    global RETRY_LIMIT
    args = _build_parser().parse_args()
    if args.retries < 0:
        emit("SKILL_ERROR", EXIT_ERROR, STAGE="аргументы", ERROR="--retries не может быть отрицательным")
    RETRY_LIMIT = args.retries

    # ── Загрузка запросов ──────────────────────────────────────────────────
    if not os.path.exists(args.queries_file):
        print(f"ERROR: файл не найден: {args.queries_file}", file=sys.stderr)
        emit("SKILL_ERROR", EXIT_ERROR, STAGE="входной файл",
             ERROR=f"файл не найден: {args.queries_file}")

    queries = load_queries(args.queries_file)
    if not queries:
        print("ERROR: в файле нет валидных запросов", file=sys.stderr)
        emit("SKILL_NEEDS_INPUT", EXIT_NEEDS_INPUT, MISSING="queries-file",
             WHERE=f"{args.queries_file}: нужна колонка query хотя бы с одной строкой")

    provider_names = (["georank"] if args.mode == "georank"
                      else list(dict.fromkeys(args.providers)))
    anchors = anchors_for(args.url or "", args.anchors)
    otpechatok = zamer_otpechatok(queries, provider_names)

    # ── Dry run: сеть и ключи не нужны ───────────────────────────────────
    if args.dry_run:
        print(f"[DRY RUN] Режим: {args.mode}")
        print(f"Бренд: {args.brand}")
        print(f"URL: {args.url}")
        print(f"Запросов: {len(queries)}")
        print(f"Отпечаток набора: {otpechatok}")
        if anchors:
            print(f"Подтверждающие слова: {', '.join(anchors)}")
        else:
            print("Подтверждающих слов нет: совпадение имени не проверяется, "
                  "все упоминания уйдут в спорные — задайте --anchors или --url")
        if args.history:
            prev = istoriya_prochitat(args.history, args.brand)
            print(f"История: {len(prev)} замеров этого бренда в {args.history}"
                  if prev else f"История: {args.history} — записей по бренду нет")
        for q in queries:
            print(f"  - [{q['intent']}] {q['query']}")
        emit("SKILL_RESULT", EXIT_OK,
             SUMMARY=f"пробный прогон: {len(queries)} запросов, сеть не использовалась")

    # ── API-ключи: все недостающие — одним запросом ──────────────────────
    requested = provider_names
    cli_keys = {"georank": args.api_key, "perplexity": args.perplexity_key,
                "openai": args.openai_key, "yandex": args.yandex_key}
    if any(cli_keys[p] for p in requested):
        print("⚠ Ключ передан аргументом — он остаётся в истории команд. "
              "Передавайте через переменную окружения.", file=sys.stderr)
    keys = {p: cli_keys[p] or os.environ.get(KEY_ENV[p], "") for p in requested}
    missing = [p for p in requested if not keys[p]]
    if missing:
        emit("SKILL_NEEDS_INPUT", EXIT_NEEDS_INPUT,
             MISSING=",".join(KEY_ENV[p] for p in missing),
             WHERE=" ".join(KEY_WHERE[p] for p in missing))

    # ── Санкция: платные запросы только с явного согласия человека ───────
    paid = [p for p in requested if p not in FREE_PROVIDERS]
    if paid and not args.sanction_spend:
        runs = max(1, args.runs)
        emit("SKILL_NEEDS_SANCTION", EXIT_NEEDS_SANCTION,
             TRIGGER="деньги",
             WHAT=f"платных запросов: {len(queries) * len(paid) * runs} "
                  f"({', '.join(paid)}; прогон/запрос: {runs}) "
                  f"с повторами сбоев — до "
                  f"{len(queries) * len(paid) * runs * (RETRY_LIMIT + 1)}",
             COST="не оценена: тарифы не подтверждены первоисточником (16.09.2026)",
             FLAG="--sanction-spend")
    api_key = keys.get("georank")

    # ── Выполнение ────────────────────────────────────────────────────────
    all_results: list[QueryResult] = []
    runs = max(1, args.runs)

    for run_no in range(1, runs + 1):
        if runs > 1:
            print(f"\n— Прогон {run_no}/{runs} —")

        if args.mode == "georank":
            if run_no == 1:
                print(f"→ GEOrank API, {len(queries)} запросов")
            all_results.extend(
                check_georank(api_key, args.brand, queries, delay=args.delay))
            # маркируем прогоны у georank-результатов
            for r in all_results[-len(queries):]:
                r.run = run_no

        else:  # direct
            for provider in requested:
                key = keys[provider]

                print(f"→ {provider}, {len(queries)} запросов")

                if provider == "perplexity":
                    batch = check_perplexity(
                        key, args.brand, args.url or "",
                        queries, model=args.perplexity_model,
                        delay=args.delay, timeout=args.timeout,
                        anchors=anchors,
                    )
                elif provider == "openai":
                    batch = check_openai(
                        key, args.brand, args.url or "",
                        queries, model=args.openai_model,
                        delay=args.delay, timeout=args.timeout,
                        base_url=args.base_url, anchors=anchors,
                    )
                elif provider == "yandex":
                    batch = check_yandexgpt(
                        key, args.brand, args.url or "",
                        queries, delay=args.delay, timeout=args.timeout,
                        anchors=anchors,
                    )
                else:
                    continue

                for r in batch:
                    r.run = run_no
                all_results.extend(batch)

    # ── Результат ─────────────────────────────────────────────────────────
    if not all_results:
        print("ERROR: не удалось получить результаты ни от одного провайдера",
              file=sys.stderr)
        emit("SKILL_ERROR", EXIT_ERROR, STAGE="запросы к провайдерам",
             ERROR="ни одного результата")

    score = visibility_score(all_results)
    summary = summarize(all_results)
    apr = apr_report(all_results)
    ball = scores(all_results)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    izmenenie: dict = {}
    if args.history:
        proshlye = istoriya_prochitat(args.history, args.brand)
        izmenenie = trend(proshlye[-1] if proshlye else None, ball, otpechatok)

    result_obj = GeoCheckResult(
        brand=args.brand,
        url=args.url or "",
        checked_at=now,
        total_queries=len(queries),
        llm_visibility_score=score,
        scores=ball,
        anchors=anchors,
        otpechatok=otpechatok,
        trend=izmenenie,
        mode=args.mode,
        providers=args.providers if args.mode == "direct" else ["georank"],
        results=all_results,
        summary=summary,
        apr=apr,
    )

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result_obj.to_dict(), f, ensure_ascii=False, indent=2)

    # ── Консольная сводка ─────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"LLM Visibility Score: {score}/100")
    print(f"Провайдеры: {', '.join(result_obj.providers)}")
    print(f"Проверено запросов: {len(all_results)}")

    # Три числа: присутствие, названы по имени, взяты как источник.
    print(f"\nПрисутствие: {ball['presence']}%  ·  назвали по имени: "
          f"{ball['mention']}%  ·  взяли как источник: {ball['citation']}%"
          f"   (знаменатель {ball['denominator']})")
    if ball["silent_citations"]:
        print(f"  ⚠ использованы как источник без имени: "
              f"{ball['silent_citations']} — ответ наш, узнаваемости ноль")
    if ball["ambiguous"]:
        print(f"  ⚠ спорных совпадений имени: {ball['ambiguous']} — "
              f"в балл не вошли, проверить вручную")
    if not anchors:
        print("  ⚠ подтверждающих слов не задано (--anchors/--url): "
              "совпадение имени не проверялось")

    if izmenenie:
        if izmenenie.get("comparable"):
            znak = lambda v: f"{v:+d}"
            print(f"\nПротив замера {izmenenie['prev_at']}: присутствие "
                  f"{znak(izmenenie['presence'])} п.п., имя "
                  f"{znak(izmenenie['mention'])} п.п., источник "
                  f"{znak(izmenenie['citation'])} п.п.")
        else:
            print(f"\nСравнения с прошлым замером нет: {izmenenie['why']}")

    for intent, stat in summary.items():
        if isinstance(stat, dict):
            print(f"  {intent:<15} {stat['found']}/{stat['total']} "
                  f"({stat['visibility']}%)")

    if runs > 1:
        print(f"\nAPR (стабильность цитирования, порог {int(APR_THRESHOLD*100)}%):")
        print(f"  прогон/запрос: {apr.get('runs_per_query', runs)}, "
              f"средний APR: {apr.get('mean_apr', 0)}%, "
              f"стабильных запросов: {apr.get('stable_queries', 0)}/{len(apr.get('per_query', []))}")
        for q in apr.get("per_query", []):
            flag = "●" if q["apr"] >= APR_THRESHOLD * 100 else "○"
            print(f"  {flag} [{q['provider']}] {q['query'][:45]:<45} "
                  f"APR {q['apr']}% ({q['found_runs']}/{q['runs']})")

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

    result_file = os.path.abspath(args.output)
    if len(errors) == len(all_results):
        # Все запросы упали: «видимость 0» здесь была бы ложным выводом.
        # В историю такой прогон не пишется по той же причине.
        emit("SKILL_ERROR", EXIT_ERROR, STAGE="запросы к провайдерам",
             ERROR=errors[0].error[:200], RESULT_FILE=result_file, RETRIES=RETRIES_USED)

    if args.history:
        istoriya_dopisat(args.history, {
            "checked_at": now, "brand": args.brand, "url": args.url or "",
            "otpechatok": otpechatok, "mode": args.mode,
            "providers": result_obj.providers, "queries": len(queries),
            "runs": runs, "errors": len(errors),
            "presence": ball["presence"], "mention": ball["mention"],
            "citation": ball["citation"],
            "silent_citations": ball["silent_citations"],
            "ambiguous": ball["ambiguous"],
            "mean_apr": apr.get("mean_apr"),
            "result_file": result_file,
        })
        print(f"Замер дописан в ряд: {os.path.abspath(args.history)}")

    emit("SKILL_RESULT", EXIT_OK, RESULT_FILE=result_file,
         SUMMARY=f"присутствие {ball['presence']}%, по имени {ball['mention']}%, "
                 f"источником {ball['citation']}% по "
                 f"{len(all_results) - len(errors)} запросам без ошибок",
         MENTION=ball["mention"], CITATION=ball["citation"],
         SILENT=ball["silent_citations"], AMBIGUOUS=ball["ambiguous"],
         ERRORS=len(errors), RETRIES=RETRIES_USED)


if __name__ == "__main__":
    main()
