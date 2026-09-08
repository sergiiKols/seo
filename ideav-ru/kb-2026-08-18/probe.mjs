// Зонд для замера №3 (18.08.2026). Один и тот же метод для всех страниц.
// Запуск: node probe.mjs <url> [phrase1] [phrase2] ...
// Печатает JSON: сырой curl-HTML отдельно, отрендеренный DOM отдельно.
import { chromium } from '/root/dizain/.claude/skills/screen-audit/scripts/node_modules/playwright/index.mjs';

const url = process.argv[2];
const phrases = process.argv.slice(3);
if (!url) { console.error('usage: node probe.mjs <url> [phrases...]'); process.exit(1); }

const strip = (html) => html
  .replace(/<script[\s\S]*?<\/script>/gi, ' ')
  .replace(/<style[\s\S]*?<\/style>/gi, ' ')
  .replace(/<[^>]+>/g, ' ')
  .replace(/&nbsp;/g, ' ')
  .replace(/\s+/g, ' ')
  .trim();
const words = (t) => (t.match(/[A-Za-zА-Яа-яЁё0-9][A-Za-zА-Яа-яЁё0-9-]*/g) || []).length;

const res = await fetch(url, { headers: { 'User-Agent': 'Mozilla/5.0 (compatible; seo-audit/3)' } });
const raw = await res.text();
const rawText = strip(raw);

const ld = [];
for (const m of raw.matchAll(/<script[^>]+application\/ld\+json[^>]*>([\s\S]*?)<\/script>/gi)) {
  try { ld.push(JSON.parse(m[1].trim())); } catch { ld.push({ __parseError: true }); }
}
const flat = [];
const walk = (n) => { if (Array.isArray(n)) n.forEach(walk); else if (n && typeof n === 'object') { flat.push(n); Object.values(n).forEach(walk); } };
walk(ld);
const articles = flat.filter(n => typeof n['@type'] === 'string' && /Article|BlogPosting|TechArticle/.test(n['@type']));

const out = {
  url,
  http: res.status,
  raw: {
    bytes: Buffer.byteLength(raw, 'utf8'),
    words: words(rawText),
    h1: [...raw.matchAll(/<h1[^>]*>([\s\S]*?)<\/h1>/gi)].map(m => strip(m[1])),
    h2count: (raw.match(/<h2[\s>]/gi) || []).length,
    hasForm: /<form[\s>]/i.test(raw),
    hasFileInput: /<input[^>]+type=["']?file/i.test(raw),
    hasTextarea: /<textarea[\s>]/i.test(raw),
    ogImage: (raw.match(/<meta[^>]+property=["']og:image["'][^>]+content=["']([^"']+)/i) || [])[1] || null,
    title: strip((raw.match(/<title[^>]*>([\s\S]*?)<\/title>/i) || [])[1] || ''),
    jsBundles: [...new Set((raw.match(/[A-Za-z0-9_-]+-[A-Za-z0-9_-]{8}\.js/g) || []))],
    articleDates: articles.map(a => ({ type: a['@type'], datePublished: a.datePublished ?? null, dateModified: a.dateModified ?? null })),
    linksToAgentPlatforms: (raw.match(/href=["'][^"']*agent-platforms\.html/gi) || []).length,
    // неразрывный пробел после однобуквенных предлогов (метод замеров 05.08/12.08)
    missingNbsp: (rawText.match(/(^|[\s («"])[вВкКсСоОуУиИаАяЯ]\s(?=[A-Za-zА-Яа-яЁё0-9])/g) || []).length,
    phrases: Object.fromEntries(phrases.map(p => [p, rawText.toLowerCase().includes(p.toLowerCase())])),
  },
};

const CHROME = '/root/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome';
const browser = await chromium.launch({ executablePath: CHROME, args: ['--no-sandbox'] });
const collect = async (width, height) => {
  const ctx = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(String(e.message).slice(0, 200)));
  await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(2500);
  const data = await page.evaluate(() => {
    const norm = s => (s || '').replace(/\s+/g, ' ').trim();
    const header = document.querySelector('header') || document.querySelector('[class*="header"]');
    const btn = document.querySelector('button.text-slate-500');
    const allBtns = [...document.querySelectorAll('button')].map(b => ({
      cls: b.className && b.className.toString ? b.className.toString().slice(0, 60) : '',
      text: norm(b.textContent), aria: b.getAttribute('aria-label'), title: b.getAttribute('title'),
    })).filter(b => !b.text && !b.aria && !b.title);
    return {
      h1: [...document.querySelectorAll('h1')].map(h => norm(h.textContent)),
      h2count: document.querySelectorAll('h2').length,
      words: (norm(document.body.innerText).match(/[A-Za-zА-Яа-яЁё0-9][A-Za-zА-Яа-яЁё0-9-]*/g) || []).length,
      hasForm: !!document.querySelector('form'),
      hasFileInput: !!document.querySelector('input[type=file]'),
      hasTextarea: !!document.querySelector('textarea'),
      headerScrollWidth: header ? header.scrollWidth : null,
      headerClientWidth: header ? header.clientWidth : null,
      docScrollWidth: document.documentElement.scrollWidth,
      docClientWidth: document.documentElement.clientWidth,
      slateButton: btn ? { text: norm(btn.textContent), aria: btn.getAttribute('aria-label'), title: btn.getAttribute('title') } : null,
      namelessButtons: allBtns.length,
      namelessButtonsSample: allBtns.slice(0, 3),
      navLinks: [...document.querySelectorAll('header a, nav a')].map(a => norm(a.textContent) + ' → ' + (a.getAttribute('href') || '')).slice(0, 40),
      linksToAgentPlatforms: document.querySelectorAll('a[href*="agent-platforms"]').length,
      bodyText: norm(document.body.innerText),
    };
  });
  await ctx.close();
  return { ...data, consoleErrors: errors };
};

const r1440 = await collect(1440, 900);
const r768 = await collect(768, 1024);
await browser.close();

const bt = r1440.bodyText.toLowerCase();
out.rendered = {
  w1440: { ...r1440, bodyText: undefined, bodyTextLen: r1440.bodyText.length },
  w768: { headerScrollWidth: r768.headerScrollWidth, headerClientWidth: r768.headerClientWidth,
          docScrollWidth: r768.docScrollWidth, docClientWidth: r768.docClientWidth,
          overflowPx: r768.headerScrollWidth != null ? r768.headerScrollWidth - r768.headerClientWidth : null,
          h1: r768.h1 },
  phrases: Object.fromEntries(phrases.map(p => [p, bt.includes(p.toLowerCase())])),
  h1RawVsRendered: JSON.stringify(out.raw.h1) === JSON.stringify(r1440.h1) ? 'СОВПАДАЕТ' : 'РАСХОЖДЕНИЕ',
};
console.log(JSON.stringify(out, null, 2));
