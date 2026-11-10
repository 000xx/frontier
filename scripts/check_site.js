// Renders the front page and every frontier page from site/js/data.js without a browser,
// and fails if any page throws, prints a broken value, has a dead in-site link,
// or does not link to every other page. Run after scripts/build_site_data.py.
// Usage: node scripts/check_site.js
const path = require('path');
globalThis.window = globalThis;
require(path.join(__dirname, '..', 'site', 'js', 'data.js'));
const Site = require(path.join(__dirname, '..', 'site', 'js', 'app.js'));

const BROKEN = /\bNaN\b|\bundefined\b|\bInfinity\b|\[object Object\]/;
let failures = 0, pages = 0;

// Every page must link to every frontier, and every in-site link must lead somewhere.
function checkLinks(html) {
  const ids = new Set(Site.data().frontiers.map((f) => f.id));
  const links = new Set([...html.matchAll(/href="#([^"]*)"/g)].map((m) => m[1]));
  for (const l of links) if (!ids.has(l) && !Site.anchors[l]) throw new Error('link to "#' + l + '" leads nowhere');
  for (const id of ids) if (!links.has(id)) throw new Error('no link to the "' + id + '" page');
  for (const a of Object.keys(Site.anchors)) if (!links.has(a)) throw new Error('no link to "#' + a + '"');
}

function check(name, make) {
  pages += 1;
  try {
    const html = make();
    checkLinks(html);
    const bad = html.replace(/<title>[^<]*<\/title>/g, '').match(BROKEN);
    if (!html || html.length < 400) throw new Error('page is empty');
    if (bad) throw new Error('page contains "' + bad[0] + '" near: ' + html.slice(Math.max(0, bad.index - 80), bad.index + 40).replace(/\s+/g, ' '));
  } catch (err) {
    failures += 1;
    console.error('FAIL ' + name + ': ' + err.message);
  }
}

const data = Site.data();
check('front page', () => Site.home());
// The front page's search and filters redraw only the tiles, so check that part on its own too.
check('front page tiles, filtered', () => { Site.filterHome('cost', null, null); const html = Site.tilesList(); Site.filterHome(); return Site.home().replace(/<div id="tiles-list">[\s\S]*?<\/div><\/section><\/div>/, html) + html; });
check('front page tiles, no match', () => { Site.filterHome('no such frontier'); const html = Site.tilesList(); Site.filterHome(); if (html.indexOf('No frontier matches') < 0) throw new Error('no empty message'); return Site.home() + html; });
for (const f of data.frontiers) {
  const block = Site.block(f);
  if (!block && !f.items.length && !f.candidates.length) {
    failures += 1;
    console.error('FAIL ' + f.id + ': no records, observations, items or candidates, so the page would be empty');
    continue;
  }
  check(f.id, () => Site.frontier(f));
  if (block) for (const sid of Site.seriesIds(f, block)) {
    check(f.id + ' / ' + sid, () => { Site.select(f.id, sid); return Site.frontier(f); });
  }
}
console.log('Checked ' + pages + ' page views across ' + data.frontiers.length + ' frontiers: ' + failures + ' failure(s).');
process.exit(failures ? 1 : 0);
