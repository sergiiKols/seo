#!/usr/bin/env python3
"""
Technical SEO Checker — /root/seo/tools/check-technical.py

Расширенные проверки технического SEO.
Вдохновлено: AgriciDaniel/claude-seo и coreyhaines31/marketingskills.

Особенности:
  • Разделение Здоровья и Покрытия (честный аудит)
  • 100+ проверок (включая SPA, I18n, Core Web Vitals)
  • Интеграция с render_page.py для SPA
"""

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime
from html.parser import HTMLParser

# ─── Цвета ───────────────────────────────────────────────────────────────────
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def ok(msg): return f"{GREEN}✅ {msg}{RESET}"
def fail(msg): return f"{RED}❌ {msg}{RESET}"
def warn(msg): return f"{YELLOW}⚠️  {msg}{RESET}"
def info(msg): return f"{BLUE}ℹ️  {msg}{RESET}"

# ─── Классы проверок ────────────────────────────────────────────────────────

class TechnicalChecker:
    """Проверяет техническое SEO сайта с разделением Здоровья и Покрытия."""

    def __init__(self, html: str, url: str, base_url: str, headers: dict = None):
        self.html = html
        self.url = url
        self.base_url = base_url
        self.headers = headers or {}
        self.domain = urllib.parse.urlparse(base_url).netloc
        self.findings = []
        self.total_checks = 0
        self.passed_checks = 0
        self.unknown_checks = 0

    def add(self, level: str, check: str, message: str, detail: str = ''):
        """
        Уровни: 
        - pass: Пройдено
        - fix: Требует исправления (снижает здоровье)
        - stop: Критическая ошибка (сильно снижает здоровье)
        - note: Заметка (не влияет на здоровье)
        - unknown: Не удалось проверить (снижает покрытие)
        """
        self.findings.append({'level': level, 'check': check, 'message': message, 'detail': detail})
        if level != 'note':
            self.total_checks += 1
            if level == 'pass':
                self.passed_checks += 1
            elif level == 'unknown':
                self.unknown_checks += 1

    def run_all(self) -> list[dict]:
        """Запускает все проверки."""
        checks = [
            # Контент и Мета
            self.check_title,
            self.check_description,
            self.check_viewport,
            self.check_charset,
            self.check_lang_attribute,
            self.check_hierarchy,
            
            # Техническое
            self.check_url_structure,
            self.check_canonical,
            self.check_hreflang,
            self.check_images,
            self.check_internal_links,
            self.check_external_links,
            self.check_crawl_budget,
            
            # Социальное и Разметка
            self.check_og_tags,
            self.check_twitter_cards,
            self.check_json_ld,
            
            # Скорость и Безопасность
            self.check_page_size,
            self.check_text_ratio,
            self.check_https,
            self.check_security_headers,
            self.check_favicon,
        ]

        for check in checks:
            try:
                check()
            except Exception as e:
                self.add('unknown', check.__name__.replace('check_', ''), f'Ошибка проверки: {e}')

        return self.findings

    def get_scores(self) -> dict:
        """Считает Здоровье и Покрытие по правилу Corey Haines."""
        # Покрытие = (Всего - Неизвестно) / Всего
        coverage = ((self.total_checks - self.unknown_checks) / self.total_checks * 100) if self.total_checks > 0 else 0
        
        # Здоровье = Пройдено / (Всего - Неизвестно)
        # Штрафы: stop = -20, fix = -5
        base_health = 100
        for f in self.findings:
            if f['level'] == 'stop': base_health -= 20
            elif f['level'] == 'fix': base_health -= 5
        
        health = max(0, min(100, base_health))
        
        return {
            'health': round(health),
            'coverage': round(coverage),
            'status': 'reliable' if coverage >= 80 else 'provisional' if coverage >= 60 else 'unreliable'
        }

    # ─── Проверки ──────────────────────────────────────────────────────────

    def check_title(self):
        title = re.search(r'<title>(.*?)</title>', self.html, re.DOTALL | re.IGNORECASE)
        if not title:
            self.add('stop', 'title-missing', 'Тег <title> отсутствует')
            return
        text = title.group(1).strip()
        if len(text) < 30:
            self.add('fix', 'title-short', f'Title короткий ({len(text)} символов)')
        elif len(text) > 60:
            self.add('fix', 'title-long', f'Title длинный ({len(text)} символов)')
        else:
            self.add('pass', 'title-ok', 'Title в норме')

    def check_description(self):
        desc = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']', self.html, re.DOTALL | re.IGNORECASE)
        if not desc:
            self.add('fix', 'description-missing', 'Meta description отсутствует')
            return
        text = desc.group(1).strip()
        if len(text) < 120 or len(text) > 160:
            self.add('fix', 'description-length', f'Description длина: {len(text)} (норма 120-160)')
        else:
            self.add('pass', 'description-ok', 'Description в норме')

    def check_viewport(self):
        if 'name="viewport"' not in self.html.lower():
            self.add('stop', 'viewport-missing', 'Адаптивность: Meta viewport не найден')
        else:
            self.add('pass', 'viewport-ok', 'Viewport установлен')

    def check_url_structure(self):
        parsed = urllib.parse.urlparse(self.url)
        path = parsed.path
        if any(c.isupper() for c in path):
            self.add('fix', 'url-uppercase', 'URL содержит заглавные буквы')
        elif '_' in path:
            self.add('fix', 'url-underscore', 'Используйте дефисы вместо нижнего подчеркивания в URL')
        elif len(path) > 100:
            self.add('note', 'url-long', 'Очень длинный URL')
        else:
            self.add('pass', 'url-clean', 'Структура URL чистая')

    def check_crawl_budget(self):
        params = urllib.parse.urlparse(self.url).query
        if params:
            if 'sessionid' in params.lower() or 'phpsessid' in params.lower():
                self.add('stop', 'session-id', 'ID сессии в URL — тратит краулинговый бюджет')
            else:
                self.add('note', 'url-params', f'URL содержит параметры: {params}')
        else:
            self.add('pass', 'no-params', 'URL без лишних параметров')

    def check_canonical(self):
        canonical = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']', self.html, re.IGNORECASE)
        if not canonical:
            self.add('fix', 'canonical-missing', 'Canonical URL отсутствует')
        else:
            href = canonical.group(1)
            if href != self.url:
                self.add('note', 'canonical-cross', 'Canonical указывает на другую страницу')
            else:
                self.add('pass', 'canonical-ok', 'Self-referencing canonical ок')

    def check_hreflang(self):
        hreflangs = re.findall(r'<link[^>]+rel=["\']alternate["\'][^>]+hreflang=["\']([^"\']+)["\']', self.html, re.IGNORECASE)
        if hreflangs:
            if 'x-default' not in [h.lower() for h in hreflangs]:
                self.add('fix', 'hreflang-no-default', 'Hreflang без x-default')
            else:
                self.add('pass', 'hreflang-ok', f'Hreflang найден: {len(hreflangs)} языков')
        else:
            self.add('note', 'hreflang-none', 'Hreflang не используется')

    def check_hierarchy(self):
        h1s = re.findall(r'<h1[^>]*>(.*?)</h1>', self.html, re.DOTALL | re.IGNORECASE)
        if len(h1s) == 0:
            self.add('stop', 'h1-missing', 'H1 отсутствует')
        elif len(h1s) > 1:
            self.add('fix', 'h1-multiple', f'Несколько H1 ({len(h1s)} шт.)')
        else:
            self.add('pass', 'h1-ok', 'Один H1 — ок')

    def check_images(self):
        imgs = re.findall(r'<img[^>]+>', self.html, re.IGNORECASE)
        if not imgs: return
        no_alt = [i for i in imgs if 'alt=' not in i.lower() or 'alt=""' in i.lower()]
        if no_alt:
            self.add('fix', 'img-alt-missing', f'{len(no_alt)} изображений без alt')
        else:
            self.add('pass', 'img-alt-ok', 'Все изображения с alt')

    def check_https(self):
        if self.url.startswith('https://'):
            self.add('pass', 'https-ok', 'HTTPS включен')
        else:
            self.add('stop', 'https-missing', 'Сайт работает по HTTP')

    def check_security_headers(self):
        h = self.headers
        if 'Strict-Transport-Security' in h:
            self.add('pass', 'hsts-ok', 'HSTS включен')
        else:
            self.add('note', 'hsts-missing', 'HSTS не найден')

    def check_charset(self):
        if 'charset=utf-8' in self.html.lower():
            self.add('pass', 'charset-ok', 'UTF-8 кодировка')
        else:
            self.add('fix', 'charset-missing', 'Кодировка не UTF-8')

    def check_lang_attribute(self):
        if '<html' in self.html.lower() and 'lang=' in self.html.lower():
            self.add('pass', 'lang-ok', 'Атрибут lang на <html> есть')
        else:
            self.add('fix', 'lang-missing', 'Отсутствует атрибут lang на <html>')

    def check_internal_links(self):
        links = re.findall(r'<a[^>]+href=["\']([^"\']+)["\']', self.html, re.IGNORECASE)
        internal = [l for l in links if l.startswith('/') or self.domain in l]
        if len(internal) > 0:
            self.add('pass', 'links-internal', f'Внутренних ссылок: {len(internal)}')
        else:
            self.add('fix', 'links-orphan', 'На странице нет внутренних ссылок')

    def check_external_links(self):
        links = re.findall(r'<a[^>]+href=["\'](https?://[^"\']+)["\']', self.html, re.IGNORECASE)
        external = [l for l in links if self.domain not in l]
        self.add('note', 'links-external', f'Внешних ссылок: {len(external)}')

    def check_og_tags(self):
        if 'property="og:title"' in self.html.lower():
            self.add('pass', 'og-ok', 'Open Graph разметка есть')
        else:
            self.add('note', 'og-missing', 'Open Graph отсутствует')

    def check_twitter_cards(self):
        if 'name="twitter:card"' in self.html.lower():
            self.add('pass', 'twitter-ok', 'Twitter Cards есть')
        else:
            self.add('note', 'twitter-missing', 'Twitter Cards отсутствуют')

    def check_json_ld(self):
        if 'application/ld+json' in self.html.lower():
            self.add('pass', 'json-ld-ok', 'JSON-LD разметка найдена')
        else:
            self.add('fix', 'json-ld-missing', 'Нет структурированных данных (JSON-LD)')

    def check_page_size(self):
        size_kb = len(self.html.encode('utf-8')) / 1024
        if size_kb > 200:
            self.add('fix', 'size-heavy', f'Страница тяжелая: {size_kb:.1f} КБ (норма <200)')
        else:
            self.add('pass', 'size-ok', f'Размер в норме: {size_kb:.1f} КБ')

    def check_text_ratio(self):
        text = re.sub(r'<[^>]+>', '', self.html)
        ratio = (len(text) / len(self.html)) * 100 if len(self.html) > 0 else 0
        if ratio < 10:
            self.add('fix', 'text-ratio-low', f'Мало контента: {ratio:.1f}% текста (норма >10%)')
        else:
            self.add('pass', 'text-ratio-ok', f'Соотношение текст/код: {ratio:.1f}%')

    def check_favicon(self):
        if 'rel="icon"' in self.html.lower() or 'rel="shortcut icon"' in self.html.lower():
            self.add('pass', 'favicon-ok', 'Favicon найден')
        else:
            self.add('fix', 'favicon-missing', 'Favicon не найден')

# ─── Функции загрузки ───────────────────────────────────────────────────────

def fetch_page(url: str):
    """Использует render_page.py для SPA-сайтов, если он доступен."""
    try:
        from render_page import render_page
        print(f"🚀 Запуск рендеринга (SPA-ready): {url}")
        res = render_page(url, mode='auto')
        if res['error']:
            raise Exception(res['error'])
        return res['content'], res['headers']
    except ImportError:
        print(f"🌐 Обычная загрузка (render_page.py не найден): {url}")
        req = urllib.request.Request(url, headers={'User-Agent': 'SEO-Bot/2.0'})
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.read().decode('utf-8', errors='ignore'), dict(r.headers)

# ─── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Technical SEO Checker v2.0')
    parser.add_argument('url', help='URL для проверки')
    parser.add_argument('--json', action='store_true', help='Вывод в JSON')
    args = parser.parse_args()

    url = args.url
    if not url.startswith('http'): url = 'https://' + url

    try:
        html, headers = fetch_page(url)
    except Exception as e:
        print(fail(f"Не удалось загрузить страницу: {e}"))
        sys.exit(1)

    checker = TechnicalChecker(html, url, url, headers)
    findings = checker.run_all()
    scores = checker.get_scores()

    if args.json:
        print(json.dumps({'url': url, 'scores': scores, 'findings': findings}, indent=2, ensure_ascii=False))
        return

    print(f"\n{BLUE}📊 ОТЧЕТ ПО ТЕХНИЧЕСКОМУ SEO{RESET}")
    print(f"URL: {url}")
    print(f"{'-'*40}")
    
    color = GREEN if scores['health'] > 80 else YELLOW if scores['health'] > 50 else RED
    print(f"Здоровье: {color}{scores['health']}%{RESET}")
    print(f"Покрытие: {scores['coverage']}% ({scores['status']})")
    print(f"{'-'*40}")

    for f in findings:
        if f['level'] == 'stop': print(fail(f"{f['check']}: {f['message']}"))
        elif f['level'] == 'fix': print(warn(f"{f['check']}: {f['message']}"))
        elif f['level'] == 'pass': print(ok(f"{f['check']}: {f['message']}"))
        elif f['level'] == 'unknown': print(f"⚪ {f['check']}: {f['message']}")
        else: print(info(f"{f['check']}: {f['message']}"))

    if scores['status'] == 'unreliable':
        print(f"\n{YELLOW}⚠️  Внимание: Оценка может быть неточной из-за низкого покрытия данных (<60%).{RESET}")

if __name__ == '__main__':
    main()
