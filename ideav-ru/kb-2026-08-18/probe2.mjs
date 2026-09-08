import { chromium } from '/root/dizain/.claude/skills/screen-audit/scripts/node_modules/playwright/index.mjs';
const CHROME = '/root/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome';
const slugs = process.argv.slice(2);
const browser = await chromium.launch({ executablePath: CHROME, args: ['--no-sandbox'] });
const out = {};
for (const s of slugs) {
  const url = `https://ideav.ru/knowledge-base/${s}.html`;
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();
  await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(2500);
  out[s] = await page.evaluate(() => {
    const norm = t => (t||'').replace(/\s+/g,' ').trim();
    const lds = [...document.querySelectorAll('script[type="application/ld+json"]')].map(e => ({
      dataAttr: e.getAttribute('data-jsonld'), len: e.textContent.length,
      types: (() => { const t=[]; try{ const w=n=>{if(Array.isArray(n))n.forEach(w); else if(n&&typeof n==='object'){if(n['@type'])t.push(n['@type']); Object.values(n).forEach(w);}}; w(JSON.parse(e.textContent)); }catch(_){t.push('ERR');} return t; })(),
      hasDatePub: /"datePublished"/.test(e.textContent),
      hasDateMod: /"dateModified"/.test(e.textContent),
      logo: (e.textContent.match(/"logo":\{[^}]*"url":"([^"]+)"/)||[])[1] || null,
    }));
    const main = document.querySelector('article');
    const links = [...document.querySelectorAll('a[href]')];
    const inArticle = main ? [...main.querySelectorAll('a[href]')] : [];
    const imgs = [...document.querySelectorAll('img')];
    return {
      h1: [...document.querySelectorAll('h1')].map(h=>norm(h.textContent)),
      h2: [...document.querySelectorAll('h2')].map(h=>({t:norm(h.textContent), fs:getComputedStyle(h).fontSize, w:getComputedStyle(h).fontWeight, tt:getComputedStyle(h).textTransform, color:getComputedStyle(h).color})),
      h3count: document.querySelectorAll('h3').length,
      ldBlocks: lds,
      totalLinks: links.length,
      articleLinks: inArticle.map(a=>norm(a.textContent).slice(0,40)+' → '+a.getAttribute('href')),
      externalLinks: links.filter(a=>/^https?:\/\//.test(a.getAttribute('href')) && !/ideav\.ru/.test(a.getAttribute('href'))).map(a=>a.getAttribute('href')+' rel='+(a.getAttribute('rel')||'-')),
      imgs: imgs.map(i=>({src:(i.getAttribute('src')||'').slice(0,70), alt:i.getAttribute('alt'), nw:i.naturalWidth, cw:i.clientWidth, loading:i.getAttribute('loading')})),
      canonical: (document.querySelector('link[rel=canonical]')||{}).href||null,
      ogImage: (document.querySelector('meta[property="og:image"]')||{}).content||null,
      title: document.title,
      metaDesc: (document.querySelector('meta[name=description]')||{}).content||null,
      prerenderLeft: !!document.querySelector('#kb-prerender'),
      lang: document.documentElement.lang || null,
      breadcrumbVisible: !!document.querySelector('nav[aria-label*="рошк"], [class*=breadcrumb]'),
    };
  });
  await ctx.close();
}
await browser.close();
console.log(JSON.stringify(out, null, 2));
