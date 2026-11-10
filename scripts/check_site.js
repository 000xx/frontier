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
// Every tile carries a small drawing of its data, except a problem list, which must stay a plain list.
for (const f of data.frontiers) {
  const html = Site.tile(f), drawn = /<svg class="spark"[^>]*data-sweep[^>]*>.*<(path|circle|rect) [^>]*(fill|stroke)="#(0F1317|E4531A)"/.test(html);
  if (drawn === (f.shape === 'problem-list')) { failures += 1; console.error('FAIL ' + f.id + ': ' + (drawn ? 'a problem-list tile must not carry a drawing' : 'the tile has no small drawing')); }
}
// A credit line the data gives must be printed under every chart and bar on the page, word for word.
function checkCredits(f, html) {
  const line = Site.esc(Site.creditLine(f));
  for (const c of f.credits) if (c.line && !line.includes(Site.esc(c.line))) throw new Error('credit line dropped: ' + c.line);
  if (!line) return;
  const charts = (html.match(/<svg (class="scalebar" )?role="img" data-sweep/g) || []).length;
  const shown = html.split('<p class="credit">' + line + '</p>').length - 1;
  if (shown < charts) throw new Error(charts + ' charts but the credit line is printed ' + shown + ' time(s)');
  if (!html.includes('Data credits and terms')) throw new Error('no "Data credits and terms" section');
}
for (const f of data.frontiers) {
  const block = Site.block(f);
  if (!block && !f.items.length && !f.candidates.length) {
    failures += 1;
    console.error('FAIL ' + f.id + ': no records, observations, items or candidates, so the page would be empty');
    continue;
  }
  check(f.id, () => {
    const html = Site.frontier(f);
    // The list and stage views must be on the page exactly where the data calls for them.
    const has = (h2) => html.includes('<h2>' + h2 + '</h2>');
    if (Site.gridMode(f) !== (has('The list at a glance') || has('The claims and where they stand'))) throw new Error('list grid shown or missing against the data');
    if (Site.claimMode(f) !== has('The claims and where they stand')) throw new Error('claim cards shown or missing against the data');
    if (Site.itemTimeMode(f) !== has('The list over time')) throw new Error('list timeline shown or missing against the data');
    if (Site.stageDatesMode(f) !== has('When each stage was reached')) throw new Error('stage dates shown or missing against the data');
    // A problem list stays a list: no grid, no counts and nothing drawn over time.
    if (f.shape === 'problem-list' && (/class="(split|tally|gcells|gcards)/.test(html) || has('The list over time'))) throw new Error('a problem list must not show a count, a grid or a chart over time');
    checkCredits(f, html);
    return html;
  });
  if (block) for (const sid of Site.seriesIds(f, block)) {
    check(f.id + ' / ' + sid, () => {
      Site.select(f.id, sid);
      const html = Site.frontier(f);
      // A shape view that applies to this series must be on the page, and must not appear where it does not apply.
      if (Site.costMode(f, sid) !== html.includes('<h2>How far the cost has fallen</h2>')) throw new Error('cost-curve view shown or missing against the data');
      if (Site.ladderMode(f, sid) !== html.includes('<h2>The ladder of powers of ten</h2>')) throw new Error('scale ladder shown or missing against the data');
      if ((block === 'observations' && Site.funnelMode(f)) !== html.includes('<h2>The measurements side by side</h2>')) throw new Error('measurement comparison shown or missing against the data');
      if (block === 'records') {
        if (Site.gaugeMode(f, sid) !== /<h2>Distance to the (line|limit)<\/h2>/.test(html)) throw new Error('threshold gauge shown or missing against the data');
        if (Site.reignMode(f, sid) !== html.includes('<h2>Who has held the record</h2>')) throw new Error('record-holder ribbon shown or missing against the data');
        if (Site.paceMode(f, sid) !== html.includes('<h2>The pace of records</h2>')) throw new Error('pace of records shown or missing against the data');
        if (Site.recClaimMode(f) !== html.includes('<h2>Where each claim stands</h2>')) throw new Error('claim cards for records shown or missing against the data');
        // The coming-down view and the to-scale line-up: on the page where the data calls for them, with one row or disc per record.
        const down = Site.downMode(f, sid), lineup = Site.lineupMode(f, sid), nRec = Site.recordCount(f, sid);
        if (down !== /<h2>How far the (limit|record) has come down<\/h2>/.test(html)) throw new Error('coming-down view shown or missing against the data');
        if (lineup !== html.includes('<h2>Drawn to scale</h2>')) throw new Error('to-scale line-up shown or missing against the data');
        const steps = (html.match(/<li class="rstep/g) || []).length, discs = (html.match(/<circle [^>]*><title>/g) || []).length;
        const want = (down ? nRec : 0) + (lineup && !Site.discMode(f) ? nRec : 0);
        if (steps !== want) throw new Error(steps + ' record bars drawn, but the data calls for ' + want);
        if (lineup && Site.discMode(f) && discs !== nRec) throw new Error(discs + ' discs drawn for ' + nRec + ' records');
        if ((down || lineup) && (html.match(/<li class="rstep now"/g) || []).length > (down ? 1 : 0) + (lineup && !Site.discMode(f) ? 1 : 0)) throw new Error('more than one record bar is marked as the current one');
        // A retracted result is never the record: it must be marked as withdrawn, and the headline must be a result that stands.
        const rows = f.records[sid], gone = rows.filter((r) => r[4] === 'retracted');
        if (gone.length && gone.length < rows.length) {
          if (!html.includes('>Withdrawn<')) throw new Error('a retracted result is not marked as withdrawn');
          const h = Site.headline(f, sid);
          if (gone.some((r) => r[0] === h.date && r[1] === h.value)) throw new Error('the headline record is a retracted result');
        }
      }
      checkCredits(f, html);
      return html;
    });
  }
}
console.log('Checked ' + pages + ' page views across ' + data.frontiers.length + ' frontiers: ' + failures + ' failure(s).');
process.exit(failures ? 1 : 0);
