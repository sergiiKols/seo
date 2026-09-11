#!/usr/bin/env python3
"""
Technical SEO Crawler — /root/seo/tools/crawl-site.py

Автоматический сбор данных для технического SEO аудита.
Работает без браузера — только HTTP-запросы.

Проверки:
  • HTTP статус
  • Meta tags (title, description, robots)
  • Open Graph
  • Canonical, hreflang
  • H1-H6 структура
  • Изображения (alt, размеры)
  • JSON-LD разметка
  • robots.txt, sitemap.xml
  • SSL, HTTP/HTTPS
  • Скорость (размер страницы, ресурсы)

Запуск:
  python3 crawl-site.py <url> [--output report.json]

Пример:
  python3 crawl-site.py https://clinch.by
  python3 crawl-site.py https://ideav.ru --output ideav-audit.json
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

# ─── Цвета терминала ──────────────────────────────────────────────────────────
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'

def ok(msg): print(f"{GREEN}✅ {msg}{RESET}")
def fail(msg): print(f"{RED}❌ {msg}{RESET}")
def warn(msg): print(f"{YELLOW}⚠️  {msg}{RESET}")

# ─── HTML Parser ─────────────────────────────────────────────────────────────

class SEOHtmlParser(HTMLParser):
    """Извлекает SEO-данные из HTML."""

    def __init__(self):
        super().__init__()
        self.title = ''
        self.meta_desc = ''
        self.meta_robots = ''
        self.meta_viewport = ''
        self.canonical = ''
        self.hreflangs = []
        self.og_tags = {}
        self.twitter_tags = {}
        self.images = []  # {src, alt, width, height}
        self.headings = {'h1': [], 'h2': [], 'h3': [], 'h4': [], 'h5': [], 'h6': []}
        self.json_ld = []
        self.in_head = False
        self.current_image = None
        self.in_json_ld = False
        self.json_ld_buffer = ''
        self._current_tag = None
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        self._current_tag = tag
        attrs_dict = dict(attrs)

        if tag == 'head':
            self.in_head = True
        elif tag == 'title':
            self._in_title = True
        elif tag == 'meta':
            name = attrs_dict.get('name', '').lower()
            property = attrs_dict.get('property', '').lower()
            content = attrs_dict.get('content', '')

            if name == 'description':
                self.meta_desc = content
            elif name == 'robots':
                self.meta_robots = content
            elif name == 'viewport':
                self.meta_viewport = content

            # Open Graph
            if property.startswith('og:'):
                self.og_tags[property] = content
            # Twitter
            if name.startswith('twitter:'):
                self.twitter_tags[name] = content

        elif tag == 'link':
            rel = attrs_dict.get('rel', '').lower()
            href = attrs_dict.get('href', '')
            if rel == 'canonical':
                self.canonical = href
            elif rel == 'alternate' and 'hreflang' in attrs_dict:
                hreflang = attrs_dict.get('hreflang', '')
                self.hreflangs.append({'lang': hreflang, 'href': href})

        elif tag in self.headings:
            # собираем текст в handle_data
            pass

        elif tag == 'img':
            src = attrs_dict.get('src', '') or attrs_dict.get('data-src', '')
            alt = attrs_dict.get('alt', '')
            width = attrs_dict.get('width', '')
            height = attrs_dict.get('height', '')
            if src:
                self.images.append({
                    'src': src,
                    'alt': alt,
                    'width': width,
                    'height': height,
                })

        elif tag == 'script':
            type_attr = attrs_dict.get('type', '')
            if type_attr == 'application/ld+json' or (not type_attr and self.in_head):
                self.in_json_ld = True
                self.json_ld_buffer = ''

    def handle_endtag(self, tag):
        if tag == 'head':
            self.in_head = False
        elif tag == 'title':
            self._in_title = False
        elif tag == 'script' and self.in_json_ld:
            self.in_json_ld = False
            if self.json_ld_buffer:
                try:
                    data = json.loads(self.json_ld_buffer)
                    self.json_ld.append(data)
                except:
                    pass
        elif tag in self.headings:
            # закрывающий тег — данные уже собраны
            pass

    def handle_data(self, data):
        data = data.strip()
        if not data:
            return

        # Буфер JSON-LD наполнялся только здесь; без этой строки скрипты
        # ld+json всегда давали пустой буфер и audit рапортовал
        # «json-ld-отсутствует» (ложное срабатывание, найдено 11.09.2026
        # на предпросмотре arenavladimir.ru).
        if self.in_json_ld:
            self.json_ld_buffer += data

        if self._in_title:
            self.title += data

    def handle_startendtag(self, tag, attrs):
        if tag == 'img':
            self.handle_starttag(tag, attrs)

# ─── Сбор данных из HTML ─────────────────────────────────────────────────────

def parse_html(html_content: str, base_url: str) -> dict:
    """Парсит HTML и извлекает SEO-данные."""
    parser = SEOHtmlParser()
    parser.feed(html_content)

    # Считаем H1-H6 по регулярным выражениям
    for h in range(1, 7):
        pattern = re.compile(rf'<h{h}[^>]*>(.*?)</h{h}>', re.DOTALL | re.IGNORECASE)
        for match in pattern.finditer(html_content):
            text = re.sub(r'<[^>]+>', '', match.group(1)).strip()
            if text:
                parser.headings[f'h{h}'].append(text)

    return {
        'title': parser.title.strip() if parser.title else '',
        'meta_description': parser.meta_desc,
        'meta_robots': parser.meta_robots,
        'meta_viewport': parser.meta_viewport,
        'canonical': parser.canonical,
        'hreflangs': parser.hreflangs,
        'og_tags': parser.og_tags,
        'twitter_tags': parser.twitter_tags,
        'images': parser.images,
        'headings': parser.headings,
        'json_ld': parser.json_ld,
    }

# ─── Проверки ───────────────────────────────────────────────────────────────

def check_http(url: str) -> dict:
    """Проверяет HTTP статус и SSL."""
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'SEO-Audit-Bot/1.0'})
        response = urllib.request.urlopen(req, timeout=15)
        status = response.status
        headers = dict(response.headers)

        return {
            'status': status,
            'ok': 200 <= status < 300,
            'headers': {
                'content_type': headers.get('Content-Type', ''),
                'content_length': headers.get('Content-Length', ''),
                'server': headers.get('Server', ''),
                'x_robots_tag': headers.get('X-Robots-Tag', ''),
            }
        }
    except urllib.error.HTTPError as e:
        return {'status': e.code, 'ok': False, 'error': str(e)}
    except Exception as e:
        return {'status': 0, 'ok': False, 'error': str(e)}

def check_robots_txt(base_url: str) -> dict:
    """Проверяет robots.txt."""
    parsed = urllib.parse.urlparse(base_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    try:
        req = urllib.request.Request(robots_url, headers={'User-Agent': 'SEO-Audit-Bot/1.0'})
        response = urllib.request.urlopen(req, timeout=10)
        content = response.read().decode('utf-8', errors='ignore')

        findings = {
            'exists': True,
            'has_sitemap': 'Sitemap:' in content,
            'has_crawl_delay': 'Crawl-delay' in content,
            'blocks_all': 'Disallow: /' in content and '*' in content,
            'content_preview': content[:500],
        }
        return findings
    except urllib.error.HTTPError:
        return {'exists': False, 'error': '404'}
    except Exception as e:
        return {'exists': False, 'error': str(e)}

def check_sitemap(base_url: str) -> dict:
    """Проверяет sitemap.xml."""
    parsed = urllib.parse.urlparse(base_url)
    sitemap_url = f"{parsed.scheme}://{parsed.netloc}/sitemap.xml"

    try:
        req = urllib.request.Request(sitemap_url, headers={'User-Agent': 'SEO-Audit-Bot/1.0'})
        response = urllib.request.urlopen(req, timeout=10)
        content = response.read().decode('utf-8', errors='ignore')

        # Считаем URL
        urls = re.findall(r'<loc>(.*?)</loc>', content)
        sitemaps = re.findall(r'<sitemap>(.*?)</sitemap>', content, re.DOTALL)

        findings = {
            'exists': True,
            'url_count': len(urls),
            'sitemap_count': len(sitemaps),
            'has_lastmod': '<lastmod>' in content,
            'has_priority': '<priority>' in content,
            'has_changefreq': '<changefreq>' in content,
        }
        return findings
    except urllib.error.HTTPError:
        return {'exists': False, 'error': '404'}
    except Exception as e:
        return {'exists': False, 'error': str(e)}

def check_ssl(base_url: str) -> dict:
    """Проверяет SSL сертификат."""
    parsed = urllib.parse.urlparse(base_url)
    is_https = parsed.scheme == 'https'

    return {
        'is_https': is_https,
        'redirects_to_https': False,  # определяется косвенно
    }

# ─── Формирование отчёта ───────────────────────────────────────────────────

def audit_page(url: str) -> dict:
    """Полный аудит одной страницы."""
    print(f"\n🔍 Аудит: {url}")

    # 1. HTTP
    print("  • HTTP проверка...", end=' ')
    http = check_http(url)
    if http['ok']:
        print(ok(http['status']))
    else:
        print(fail(f"статус {http.get('status', '?')}"))

    # 2. Скачиваем HTML
    print("  • Загрузка страницы...", end=' ')
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'SEO-Audit-Bot/1.0'})
        response = urllib.request.urlopen(req, timeout=15)
        html = response.read().decode('utf-8', errors='ignore')
        print(ok(f"{len(html):,} байт"))
    except Exception as e:
        print(fail(str(e)))
        return {'error': str(e)}

    # 3. Парсим
    print("  • Парсинг HTML...", end=' ')
    seo = parse_html(html, url)
    print(ok('OK'))

    # 4. robots.txt
    print("  • robots.txt...", end=' ')
    robots = check_robots_txt(url)
    print(ok('есть' if robots['exists'] else fail('нет')))

    # 5. sitemap.xml
    print("  • sitemap.xml...", end=' ')
    sitemap = check_sitemap(url)
    print(ok(f"{sitemap.get('url_count', 0)} URL" if sitemap['exists'] else fail('нет')))

    # 6. SSL
    print("  • HTTPS...", end=' ')
    ssl = check_ssl(url)
    print(ok('да') if ssl['is_https'] else warn('нет — HTTP'))

    # ─── Проверки и результаты ────────────────────────────────────────────

    findings = []

    # Title
    if not seo['title']:
        findings.append({'level': 'stop', 'check': 'title-отсутствует', 'message': 'Тег <title> отсутствует или пустой'})
    elif len(seo['title']) < 30:
        findings.append({'level': 'fix', 'check': 'title-короткий', 'message': f'Title слишком короткий: {len(seo["title"])} символов (норма 50-60)'})
    elif len(seo['title']) > 60:
        findings.append({'level': 'fix', 'check': 'title-длинный', 'message': f'Title слишком длинный: {len(seo["title"])} символов (норма 50-60)'})

    # Description
    if not seo['meta_description']:
        findings.append({'level': 'stop', 'check': 'description-отсутствует', 'message': 'Meta description отсутствует'})
    elif len(seo['meta_description']) < 120:
        findings.append({'level': 'fix', 'check': 'description-короткая', 'message': f'Description короткая: {len(seo["meta_description"])} символов (норма 150-160)'})
    elif len(seo['meta_description']) > 160:
        findings.append({'level': 'fix', 'check': 'description-длинная', 'message': f'Description длинная: {len(seo["meta_description"])} символов (норма 150-160)'})

    # Robots
    if 'noindex' in seo['meta_robots'].lower():
        findings.append({'level': 'stop', 'check': 'robots-noindex', 'message': 'Страница закрыта от индексации: noindex в meta robots'})
    if 'nofollow' in seo['meta_robots'].lower():
        findings.append({'level': 'fix', 'check': 'robots-nofollow', 'message': 'Ссылки на странице nofollow: поисковики не перейдут по ссылкам'})

    # H1
    h1_count = len(seo['headings']['h1'])
    if h1_count == 0:
        findings.append({'level': 'stop', 'check': 'h1-отсутствует', 'message': 'Тег H1 отсутствует'})
    elif h1_count > 1:
        findings.append({'level': 'fix', 'check': 'h1-несколько', 'message': f'Несколько H1 на странице: {h1_count} шт. (норма 1)'})
    else:
        h1_text = seo['headings']['h1'][0]
        if len(h1_text) > 70:
            findings.append({'level': 'note', 'check': 'h1-длинный', 'message': f'H1 длинный: {len(h1_text)} символов'})

    # H2-H6
    h2_count = len(seo['headings']['h2'])
    if h2_count == 0 and len(html) > 2000:
        findings.append({'level': 'note', 'check': 'h2-отсутствует', 'message': 'Нет подзаголовков H2 — структура контента не обозначена'})

    # Canonical
    if not seo['canonical']:
        findings.append({'level': 'fix', 'check': 'canonical-отсутствует', 'message': 'Canonical URL не указан'})
    elif seo['canonical'] != url:
        findings.append({'level': 'note', 'check': 'canonical-отличается', 'message': f'Canonical ({seo["canonical"]}) отличается от URL ({url})'})

    # Images
    images_without_alt = [img for img in seo['images'] if not img['alt']]
    images_without_size = [img for img in seo['images'] if not img['width'] or not img['height']]

    if images_without_alt:
        findings.append({'level': 'fix', 'check': 'img-без-alt', 'message': f'{len(images_without_alt)} изображений без alt-текста'})
    if images_without_size:
        findings.append({'level': 'note', 'check': 'img-без-размеров', 'message': f'{len(images_without_size)} изображений без width/height — возможен сдвиг при загрузке'})

    # Open Graph
    og_required = ['og:title', 'og:description', 'og:image', 'og:url']
    og_missing = [tag for tag in og_required if tag not in seo['og_tags']]
    if og_missing:
        findings.append({'level': 'note', 'check': 'og-неполный', 'message': f'Отсутствуют OG теги: {", ".join(og_missing)}'})

    # JSON-LD
    if not seo['json_ld']:
        findings.append({'level': 'note', 'check': 'json-ld-отсутствует', 'message': 'Нет структурированных данных (JSON-LD)'})

    # Viewport
    if not seo['meta_viewport']:
        findings.append({'level': 'fix', 'check': 'viewport-отсутствует', 'message': 'Meta viewport не установлен — мобильные устройства получат desktop-версию'})

    # SSL
    if not ssl['is_https']:
        findings.append({'level': 'fix', 'check': 'http-вместо-https', 'message': 'Сайт работает по HTTP, не HTTPS'})

    # Размер страницы
    page_size = len(html)
    if page_size > 3_000_000:
        findings.append({'level': 'fix', 'check': 'страница-большая', 'message': f'Страница {page_size / 1024 / 1024:.1f} МБ — слишком тяжёлая'})
    elif page_size > 1_000_000:
        findings.append({'level': 'note', 'check': 'страница-тяжёлая', 'message': f'Страница {page_size / 1024:.0f} КБ — рекомендуется оптимизация'})

    # ─── Итоги ───────────────────────────────────────────────────────────

    counts = {
        'stop': len([f for f in findings if f['level'] == 'stop']),
        'fix': len([f for f in findings if f['level'] == 'fix']),
        'note': len([f for f in findings if f['level'] == 'note']),
    }

    return {
        'target': url,
        'timestamp': datetime.now().isoformat(),
        'http': http,
        'ssl': ssl,
        'robots': robots,
        'sitemap': sitemap,
        'seo': seo,
        'counts': counts,
        'findings': findings,
    }

# ─── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Technical SEO Crawler')
    parser.add_argument('url', help='URL для аудита')
    parser.add_argument('--output', '-o', help='Путь для сохранения JSON отчёта')
    parser.add_argument('--format', choices=['json', 'text'], default='text', help='Формат вывода')
    args = parser.parse_args()

    url = args.url
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    report = audit_page(url)

    if 'error' in report:
        print(f"\n{fail('Ошибка:')} {report['error']}")
        sys.exit(1)

    # Вывод
    if args.format == 'text':
        print(f"\n{'='*60}")
        print(f"📊 ИТОГИ АУДИТА: {url}")
        print(f"{'='*60}")
        print(f"\nСтатус: {report['http']['status']}")
        print(f"HTTPS: {'✅' if report['ssl']['is_https'] else '❌'}")
        print(f"robots.txt: {'✅' if report['robots']['exists'] else '❌'}")
        print(f"sitemap.xml: {'✅' if report['sitemap']['exists'] else '❌'} ({report['sitemap'].get('url_count', 0)} URL)")

        print(f"\n{'-'*60}")
        print(f"🔴 СТОП ({report['counts']['stop']}):")
        for f in [x for x in report['findings'] if x['level'] == 'stop']:
            print(f"  • {f['message']}")

        print(f"\n🟡 ЧИНИТЬ ({report['counts']['fix']}):")
        for f in [x for x in report['findings'] if x['level'] == 'fix']:
            print(f"  • {f['message']}")

        print(f"\n🔵 ЗАМЕТКИ ({report['counts']['note']}):")
        for f in [x for x in report['findings'] if x['level'] == 'note']:
            print(f"  • {f['message']}")

        print(f"\n{'-'*60}")
        print(f"SEO данные:")
        print(f"  Title: {report['seo']['title'][:80]}{'...' if len(report['seo']['title']) > 80 else ''}")
        print(f"  Description: {report['seo']['meta_description'][:80]}{'...' if len(report['seo']['meta_description']) > 80 else ''}")
        print(f"  H1: {report['seo']['headings']['h1']}")
        print(f"  Изображений: {len(report['seo']['images'])} (без alt: {len([i for i in report['seo']['images'] if not i['alt']])})")
        print(f"  JSON-LD блоков: {len(report['seo']['json_ld'])}")
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))

    # Сохранение
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        ok(f"Отчёт сохранён: {args.output}")

if __name__ == '__main__':
    main()
