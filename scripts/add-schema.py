#!/usr/bin/env python3
"""
Add Schema.org — /root/seo/tools/add-schema.py

Генерирует JSON-LD Schema.org разметку для страниц.
Вдохновлено: blogseo.io methodology

Поддерживает типы:
  • Article — блоговые статьи
  • FAQPage — вопросы и ответы
  • Product — товары
  • BreadcrumbList — хлебные крошки
  • Organization — информация о компании
  • WebSite — общие данные сайта

Запуск:
  python3 add-schema.py <type> <url> --title "Заголовок" --author "Автор" --date "2024-01-01"
  python3 add-schema.py article https://example.com/article --title "..." --output schema.json

Примеры:
  python3 add-schema.py article https://clinch.by/boxing-gloves \
    --title "Как выбрать боксёрские перчатки" \
    --author "Clinch" \
    --date "2026-08-29" \
    --description "Руководство по выбору боксёрских перчаток"

  python3 add-schema.py faq https://clinch.by/faq \
    --title "Частые вопросы" \
    --questions "Как выбрать размер?|По таблице размеров" \
                 "Какие материалы лучше?|Кожа долговечнее PU"
"""

import argparse
import json
import sys
from datetime import datetime

# ─── Schema.org генераторы ───────────────────────────────────────────────────

def schema_article(url: str, title: str, author: str, date: str, description: str, image: str = '') -> dict:
    """Генерирует Article schema."""
    schema = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": title,
        "description": description,
        "url": url,
        "datePublished": date,
        "author": {
            "@type": "Person",
            "name": author,
        },
        "publisher": {
            "@type": "Organization",
            "name": "Clinch",
            "logo": {
                "@type": "ImageObject",
                "url": "https://clinch.by/logo.png"
            }
        }
    }
    if image:
        schema["image"] = {
            "@type": "ImageObject",
            "url": image
        }
    return schema

def schema_faq(url: str, title: str, questions: list) -> dict:
    """Генерирует FAQPage schema."""
    qas = []
    for q, a in questions:
        qas.append({
            "@type": "Question",
            "name": q,
            "acceptedAnswer": {
                "@type": "Answer",
                "text": a
            }
        })

    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": qas
    }

def schema_product(name: str, url: str, description: str, price: str, currency: str = "BYN",
                   brand: str = '', availability: str = "https://schema.org/InStock",
                   image: str = '') -> dict:
    """Генерирует Product schema."""
    schema = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": name,
        "description": description,
        "url": url,
        "offers": {
            "@type": "Offer",
            "price": price,
            "priceCurrency": currency,
            "availability": availability,
            "seller": {
                "@type": "Organization",
                "name": "Clinch"
            }
        }
    }
    if brand:
        schema["brand"] = {"@type": "Brand", "name": brand}
    if image:
        schema["image"] = image
    return schema

def schema_breadcrumb(url: str, items: list) -> dict:
    """Генерирует BreadcrumbList schema."""
    item_list = []
    for i, (name, href) in enumerate(items):
        item_list.append({
            "@type": "ListItem",
            "position": i + 1,
            "name": name,
            "item": href
        })

    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": item_list
    }

def schema_organization(name: str, url: str, logo: str, description: str,
                        same_as: list = None) -> dict:
    """Генерирует Organization schema."""
    schema = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": name,
        "url": url,
        "description": description,
        "logo": logo
    }
    if same_as:
        schema["sameAs"] = same_as
    return schema

def schema_website(name: str, url: str, description: str, search_url: str = '') -> dict:
    """Генерирует WebSite schema."""
    schema = {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": name,
        "url": url,
        "description": description
    }
    if search_url:
        schema["potentialAction"] = {
            "@type": "SearchAction",
            "target": {
                "@type": "EntryPoint",
                "urlTemplate": search_url
            },
            "query-input": "required name=q"
        }
    return schema

def schema_local_business(name: str, url: str, address: str, phone: str,
                          hours: str, geo: dict = None) -> dict:
    """Генерирует LocalBusiness schema (для clinch.by)."""
    schema = {
        "@context": "https://schema.org",
        "@type": "SportingGoodsStore",
        "name": name,
        "url": url,
        "telephone": phone,
        "address": {
            "@type": "PostalAddress",
            "streetAddress": address,
            "addressLocality": "Гомель",
            "addressCountry": "BY"
        },
        "openingHoursSpecification": {
            "@type": "OpeningHoursSpecification",
            "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
            "opens": "10:00",
            "closes": "20:00"
        }
    }
    if geo:
        schema["geo"] = {
            "@type": "GeoCoordinates",
            "latitude": geo.get("lat", ""),
            "longitude": geo.get("lon", "")
        }
    return schema

# ─── HTML вставка ──────────────────────────────────────────────────────────

def format_html_script(schema: dict, indent: int = 2) -> str:
    """Форматирует JSON-LD для вставки в HTML <head>."""
    json_str = json.dumps(schema, ensure_ascii=False, indent=indent)
    return f'<script type="application/ld+json">\n{json_str}\n</script>'

# ─── CLI ─────────────────────────────────────────────────────────────────

def parse_questions(q_args: list) -> list:
    """Парсит вопросы из формата 'вопрос|ответ'."""
    questions = []
    for qa in q_args:
        if '|' in qa:
            parts = qa.split('|', 1)
            questions.append((parts[0].strip(), parts[1].strip()))
    return questions

def main():
    parser = argparse.ArgumentParser(description='Add Schema.org JSON-LD markup')
    parser.add_argument('type', choices=['article', 'faq', 'product', 'breadcrumb', 'organization', 'website', 'local'],
                       help='Тип Schema.org разметки')
    parser.add_argument('url', help='URL страницы')
    parser.add_argument('--title', '-t', help='Заголовок/название')
    parser.add_argument('--author', '-a', help='Автор')
    parser.add_argument('--date', '-d', help='Дата публикации (YYYY-MM-DD)')
    parser.add_argument('--description', help='Описание')
    parser.add_argument('--image', '-i', help='URL изображения')
    parser.add_argument('--price', help='Цена товара')
    parser.add_argument('--currency', default='BYN', help='Валюта (по умолчанию: BYN)')
    parser.add_argument('--brand', help='Бренд')
    parser.add_argument('--questions', '-q', nargs='+', help='Вопросы в формате "вопрос|ответ"')
    parser.add_argument('--items', help='Элементы хлебных крошек в формате "имя|url" через запятую')
    parser.add_argument('--phone', help='Телефон (для local business)')
    parser.add_argument('--address', help='Адрес (для local business)')
    parser.add_argument('--name', help='Название организации')
    parser.add_argument('--output', '-o', help='Сохранить в файл')
    parser.add_argument('--html', action='store_true', help='Вывести в формате HTML <script>')
    args = parser.parse_args()

    # Генерация
    if args.type == 'article':
        if not args.title or not args.description:
            print("❌ Для article требуется --title и --description")
            sys.exit(1)
        schema = schema_article(
            url=args.url,
            title=args.title,
            author=args.author or 'Admin',
            date=args.date or datetime.now().strftime('%Y-%m-%d'),
            description=args.description,
            image=args.image
        )

    elif args.type == 'faq':
        if not args.questions:
            print("❌ Для faq требуется --questions 'вопрос|ответ'")
            sys.exit(1)
        questions = parse_questions(args.questions)
        schema = schema_faq(
            url=args.url,
            title=args.title or 'FAQ',
            questions=questions
        )

    elif args.type == 'product':
        if not args.title or not args.price:
            print("❌ Для product требуется --title и --price")
            sys.exit(1)
        schema = schema_product(
            name=args.title,
            url=args.url,
            description=args.description or '',
            price=args.price,
            currency=args.currency,
            brand=args.brand,
            image=args.image
        )

    elif args.type == 'breadcrumb':
        if not args.items:
            print("❌ Для breadcrumb требуется --items")
            sys.exit(1)
        items = []
        for item in args.items.split(','):
            if '|' in item:
                parts = item.split('|', 1)
                items.append((parts[0].strip(), parts[1].strip()))
        schema = schema_breadcrumb(url=args.url, items=items)

    elif args.type == 'organization':
        if not args.name:
            print("❌ Для organization требуется --name")
            sys.exit(1)
        schema = schema_organization(
            name=args.name,
            url=args.url,
            logo=args.image or '',
            description=args.description or ''
        )

    elif args.type == 'website':
        schema = schema_website(
            name=args.name or 'Сайт',
            url=args.url,
            description=args.description or ''
        )

    elif args.type == 'local':
        if not args.name:
            print("❌ Для local требуется --name")
            sys.exit(1)
        schema = schema_local_business(
            name=args.name,
            url=args.url,
            address=args.address or '',
            phone=args.phone or '',
            hours='10:00-20:00'
        )

    # Вывод
    if args.html:
        output = format_html_script(schema)
    else:
        output = json.dumps(schema, ensure_ascii=False, indent=2)

    print(output)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output)
        print(f"\n✅ Сохранено: {args.output}")

if __name__ == '__main__':
    main()
