import { chromium } from '/root/dizain/.claude/skills/screen-audit/scripts/node_modules/playwright/index.mjs';
import { readFileSync, writeFileSync } from 'node:fs';
const CHROME = '/root/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome';
const urls = readFileSync('/root/seo/ideav-ru/kb-2026-08-18/kb-urls.txt','utf8').trim().split('\n');
const strip = h => h.replace(/<script[\s\S]*?<\/script>/gi,' ').replace(/<style[\s\S]*?<\/style>/gi,' ').replace(/<[^>]+>/g,' ').replace(/&nbsp;/g,' ').replace(/\s+/g,' ').trim();
const W = t => (t.match(/[A-Za-zА-Яа-яЁё0-9][A-Za-zА-Яа-яЁё0-9-]*/g)||[]).length;
const browser = await chromium.launch({ executablePath: CHROME, args: ['--no-sandbox'] });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();
const rows = [];
for (const u of urls) {
  const r = await fetch(u, { headers: { 'User-Agent': 'Mozilla/5.0 (compatible; seo-audit/3)' } });
  const raw = await r.text();
  const rawTitle = (raw.match(/<title[^>]*>([\s\S]*?)<\/title>/i)||[])[1]||'';
  const rawDesc = (raw.match(/<meta name="description" content="([^"]*)"/i)||[])[1]||'';
  const rawW = W(strip(raw));
  const rawH1 = strip((raw.match(/<h1[^>]*>([\s\S]*?)<\/h1>/i)||[])[1]||'');
  const rawH2 = (raw.match(/<h2[\s>]/gi)||[]).length;
  await page.goto(u, { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(2000);
  const d = await page.evaluate(() => {
    const n = s => (s||'').replace(/\s+/g,' ').trim();
    return { title: document.title, desc: (document.querySelector('meta[name=description]')||{}).content||'',
      words: (n(document.body.innerText).match(/[A-Za-zА-Яа-яЁё0-9][A-Za-zА-Яа-яЁё0-9-]*/g)||[]).length,
      h1: [...document.querySelectorAll('h1')].map(h=>n(h.textContent)), h2: document.querySelectorAll('h2').length,
      ld: document.querySelectorAll('script[type="application/ld+json"]').length,
      ctaExcel: !!document.querySelector('article a[href*="excel-to-app"]'),
      overflow: 0 };
  });
  rows.push({ slug: u.split('/').pop(), rawW, spaW: d.words, rawTitle, spaTitle: d.title, rawDescLen: rawDesc.length, spaDescLen: d.desc.length,
    titleSame: rawTitle===d.title, descSame: rawDesc===d.desc, h1Same: JSON.stringify([rawH1])===JSON.stringify(d.h1), rawH2, spaH2: d.h2, ldBlocks: d.ld, ctaExcel: d.ctaExcel });
  process.stderr.write('.');
}
await browser.close();
writeFileSync('/root/seo/ideav-ru/kb-2026-08-18/sweep27-rendered.json', JSON.stringify(rows,null,1));
console.log('slug|rawW|spaW|%скрыто|titleSame|descSame|h1Same|rawH2|spaH2|ldBlocks|ctaExcel');
rows.forEach(r=>console.log([r.slug,r.rawW,r.spaW,Math.round((1-r.rawW/r.spaW)*100)+'%',r.titleSame,r.descSame,r.h1Same,r.rawH2,r.spaH2,r.ldBlocks,r.ctaExcel].join('|')));
const s=(f)=>rows.filter(f).length;
console.log('ИТОГ: titleSame',s(r=>r.titleSame),'/27; descSame',s(r=>r.descSame),'/27; h1Same',s(r=>r.h1Same),'/27; ldBlocks==3',s(r=>r.ldBlocks===3),'/27; ctaExcel',s(r=>r.ctaExcel),'/27');
console.log('слов сырой суммарно',rows.reduce((a,b)=>a+b.rawW,0),'| после JS',rows.reduce((a,b)=>a+b.spaW,0));
