/*
  Frontier in Numbers: draws every page from window.FRONTIER_DATA (site/js/data.js).

  A frontier page is assembled from the blocks its data file holds:
    records               -> record chart, ranking of series, history table (and a two-axis chart when metric.axes exist)
      + threshold-gauge   -> the current record is also drawn against the line it has to cross (metric.target or metric.limit)
      + reign-timeline    -> a ribbon of who has held the record, one block per holder, and a table of holders
      + three or more records in the series -> the pace of records: one tick per record, the longest wait, the wait since the latest
      + claim-scoreboard  -> one card per result with its status, holder, conditions and note
      + lower is better on a log scale (limits, uncertainties) -> how far the record has come down: one bar per record, each reaching further toward the target
      + to-scale-lineup   -> the records drawn to scale side by side: discs when the measure is a diameter, bars from zero otherwise
      (a retracted result stays on the chart and in the tables, struck through, but never counts as a record)
    observations          -> line chart with ranges and a table (or a points chart when each series is a single point)
      + coverage-meter    -> percentages are also drawn as a filled share of the whole, with what is left
      + race-to-zero      -> the first series is also drawn against zero: distance to go, and a log axis for big falls
      + cost-curve        -> how many times cheaper the latest figure is than the first, and a ribbon of when each halving was reached
      + precision-funnel  -> every measurement side by side on one value axis, with the range the source gives, grouped by method
    records or observations
      + scale-ladder      -> the powers of ten the series has passed, on a log bar from its first figure to the next power of ten
    stages + candidates   -> stage table, and a dated track per candidate where `history` has dates
    items                 -> a grid of the whole list by status, the dated entries on a time axis, then the filterable list
      + claim-scoreboard  -> the grid becomes one card per claim, with who made it, where it stands and the note
      (a problem-list frontier gets the filterable list only: no grid, no counts, no chart over time)
    events, reading, sources, credits -> the reference sections
  Credit lines (from a dataset NOTICE.md, or from a source's notes) are printed under every chart and bar of the frontier.
  Front-page tiles carry a small drawing of the same data: a line, the list as squares, or a row of stages per candidate.
  A new frontier that uses these blocks needs no change here. To add a new view,
  write a function that returns HTML for a block and call it from frontier().
  All drawing functions return strings, so scripts/check_site.js can run them without a browser.
*/
(function () {
  var root = typeof window !== 'undefined' ? window : globalThis;
  var D = root.FRONTIER_DATA;
  var MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  var STATUS = { claimed: 'Claimed', reviewed: 'Peer reviewed', 'peer-reviewed': 'Peer reviewed', peer_reviewed: 'Peer reviewed', confirmed: 'Independently confirmed', retracted: 'Retracted' };
  var ITEM_STATUS = { open: 'Open', done: 'Done', partial: 'Partial', disputed: 'Disputed' };
  var SHAPES = { 'problem-list': 'Problem list' };
  var HOME_ANCHORS = { home: 1, frontiers: 1, method: 1, domains: 1 };
  var chosen = {};     // frontier id -> selected series id
  var itemState = {};  // frontier id -> { q, status, group, shown }
  var homeState = { q: '', domain: 'all', shape: 'all' };  // the front page's search and filters

  /* ---------- small helpers ---------- */
  function esc(s) {
    return String(s === null || s === undefined ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; });
  }
  function parseDate(s) {
    var p = String(s).split('-').map(Number);
    return { y: p[0], m: p[1] || null, d: p[2] || null, t: p[0] + ((p[1] || 6.5) - 1) / 12 + ((p[2] || 15) - 1) / 365 };
  }
  function fmtDate(s) {
    if (!s) return '';
    var p = parseDate(s);
    return (p.d && p.d !== 1 ? p.d + ' ' : '') + (p.m ? MONTHS[p.m - 1] + ' ' : '') + p.y;
  }
  function sup(n) {
    var map = { '-': '⁻', 0: '⁰', 1: '¹', 2: '²', 3: '³', 4: '⁴', 5: '⁵', 6: '⁶', 7: '⁷', 8: '⁸', 9: '⁹' };
    return String(n).split('').map(function (c) { return map[c] || c; }).join('');
  }
  function fmt(v) {
    if (v === null || v === undefined || isNaN(v)) return '';
    var a = Math.abs(v);
    if (a !== 0 && (a >= 1e15 || a < 1e-3)) {
      var e = Math.floor(Math.log10(a)), m = Math.round(v / Math.pow(10, e) * 10) / 10;
      if (Math.abs(m) >= 10) { m = m / 10; e += 1; }
      return (m === 1 ? '' : m + '×') + '10' + sup(e);
    }
    if (a >= 1000) return Math.round(v).toLocaleString('en-US');
    if (a >= 100) return String(Math.round(v * 10) / 10);
    if (a < 1 && a !== 0) return String(Number(v.toPrecision(3))); // small values keep three figures, so 0.0024 is not printed as 0
    return String(Math.round(v * 100) / 100);
  }
  function isPct(f) { return f.metric.unit === '%' || f.metric.unit === 'percent'; }
  function suffix(f) { return isPct(f) ? '%' : ''; }
  function unitText(f) { return isPct(f) ? '' : f.metric.unit; }
  function val(f, v) { return fmt(v) + suffix(f); }
  function nowT() { var n = new Date(); return n.getFullYear() + n.getMonth() / 12 + (n.getDate() - 1) / 365; }
  function ago(s) {
    if (!parseDate(s).m) return '';
    var y = nowT() - parseDate(s).t;
    if (y < 1 / 12) return 'this month';
    if (y < 1) return Math.round(y * 12) + ' months ago';
    return (Math.round(y * 10) / 10) + ' years ago';
  }
  function shapeLabel(f) { return SHAPES[f.shape] || (f.shape ? f.shape.replace(/-/g, ' ').replace(/^./, function (c) { return c.toUpperCase(); }) : ''); }
  function mark(status, color, size) {
    var s = size || 12, inner;
    if (status === 'confirmed') inner = '<circle cx="6" cy="6" r="5.25" fill="' + color + '"/>';
    else {
      inner = '<circle cx="6" cy="6" r="4.5" fill="none" stroke="' + color + '" stroke-width="1.5"/>';
      if (STATUS[status] === 'Peer reviewed') inner += '<path d="M6 1.5 A4.5 4.5 0 0 1 6 10.5 Z" fill="' + color + '"/>';
      if (status === 'retracted') inner += '<path d="M2.5 9.5 L9.5 2.5" stroke="' + color + '" stroke-width="1.5"/>';
    }
    return '<svg aria-hidden="true" width="' + s + '" height="' + s + '" viewBox="0 0 12 12">' + inner + '</svg>';
  }
  function statusHtml(status, color) { return status ? '<span class="status">' + mark(status, color) + esc(STATUS[status] || status) + '</span>' : ''; }
  function LOGO(c) {
    return '<svg aria-hidden="true" width="28" height="28" viewBox="0 0 28 28"><path d="M2 24 H9 V17 H16 V10 H23 V3" fill="none" stroke="' + c + '" stroke-width="2.5"/><circle cx="23" cy="4" r="3.5" fill="#FF7A40"/></svg>';
  }
  var ARROW = '<svg aria-hidden="true" width="16" height="16" viewBox="0 0 16 16"><path d="M2 8 H13 M9 4 L13 8 L9 12" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>';
  /* Frontiers in the site's domain order, so menus, tiles and previous/next links all agree. */
  function ordered() {
    return D.frontiers.slice().sort(function (a, b) {
      var d = D.domains.indexOf(a.domain) - D.domains.indexOf(b.domain);
      return d || (a.title < b.title ? -1 : a.title > b.title ? 1 : 0);
    });
  }
  function byDomain() {
    var out = [];
    ordered().forEach(function (f) {
      var last = out[out.length - 1];
      if (!last || last.name !== f.domain) out.push(last = { name: f.domain, list: [] });
      last.list.push(f);
    });
    return out;
  }
  function frontierLinks(currentId) {
    return byDomain().map(function (g) {
      return '<div class="ig"><h3>' + esc(g.name) + '</h3><ul>' + g.list.map(function (f) {
        return '<li><a href="#' + esc(f.id) + '"' + (f.id === currentId ? ' aria-current="page"' : '') + '>' + esc(f.title) + '</a></li>';
      }).join('') + '</ul></div>';
    }).join('');
  }
  function nav(color, currentId) {
    return '<a class="brand" href="#home">' + LOGO(color) + '<span>' + esc(D.site.name) + '</span></a>' +
      '<nav aria-label="Main"><details class="menu"><summary>All ' + D.frontiers.length + ' frontiers</summary>' +
      '<div class="menu-panel">' + frontierLinks(currentId) + '</div></details>' +
      '<a href="#frontiers">Overview</a><a href="#method">Method</a><a href="#domains">Domains</a></nav>';
  }
  function siteFooter(currentId) {
    return '<footer class="footer dark"><div class="wrap">' +
      '<div class="frow"><p class="l">Every number links to its source. Every record carries a status.</p>' +
      '<nav aria-label="Site"><a href="#home">Front page</a><a href="#frontiers">Overview</a><a href="#method">Method</a><a href="#domains">Domains</a></nav></div>' +
      '<nav class="index" aria-label="All frontiers">' + frontierLinks(currentId) + '</nav>' +
      '<p class="foot-note">Photograph: NASA.</p></div></footer>';
  }
  function link(url, html) { return url ? '<a href="' + esc(url) + '" target="_blank" rel="noopener">' + html + '</a>' : html; }
  function sourceLink(f, id) {
    var s = f.sources.filter(function (x) { return x.id === id; })[0];
    return s && s.url ? '<a href="' + esc(s.url) + '" target="_blank" rel="noopener">Source</a>' : '<span class="need">Source needed</span>';
  }

  /* ---------- reading the data ---------- */
  function keys(o) { return Object.keys(o || {}); }
  function hasRecords(f) { return keys(f.records).length > 0; }
  function hasObs(f) { return keys(f.observations).length > 0; }
  function block(f) { return hasRecords(f) ? 'records' : hasObs(f) ? 'observations' : null; }
  function better(f, a, b) { return f.metric.direction === 'lower' ? a < b : a > b; }
  function seriesIds(f, b) {
    var map = f[b], out = [];
    f.series.forEach(function (s) { if (map[s.id] && map[s.id].length) out.push(s.id); });
    keys(map).forEach(function (id) { if (out.indexOf(id) < 0 && map[id].length) out.push(id); });
    return out;
  }
  function seriesMeta(f, id) {
    var m = f.series.filter(function (s) { return s.id === id; })[0];
    return m || { id: id, label: f.metric.name || f.title, group: '' };
  }
  function seriesName(m) { return m.group && m.group !== m.label ? m.group + ': ' + m.label : m.label; }
  /* Records: the entries that beat everything before them, in the direction that counts as progress. */
  function withdrawn(r) { return r[4] === 'retracted'; }
  function progression(f, rows) {
    var best = null, out = [], live = rows.filter(function (r) { return !withdrawn(r); });
    if (live.length) rows = live; // a retracted result is not a record; a series with nothing else is left as it is
    rows.forEach(function (r) { if (best === null || better(f, r[1], best)) { out.push({ r: r, gain: best === null ? null : r[1] - best }); best = r[1]; } });
    return out;
  }
  /* Observations where every series is a single point (one rocket, one year) are drawn as points, not lines. */
  function pointsMode(f) {
    var ids = seriesIds(f, 'observations');
    return ids.length > 3 && ids.every(function (id) { return f.observations[id].length === 1; });
  }
  function bestSeries(f, b) {
    var best = null, v = null;
    seriesIds(f, b).forEach(function (id) {
      var rows = b === 'records' ? progression(f, f[b][id]).map(function (p) { return p.r; }) : f[b][id];
      rows.forEach(function (r) { if (v === null || better(f, r[1], v)) { v = r[1]; best = id; } });
    });
    return best;
  }
  /* A frontier's chart shapes (primary first, then secondary) decide how its observations are framed. */
  function hasShape(f, s) { return f.shape === s || (f.shapes || []).indexOf(s) >= 0; }
  function allObs(f) { var out = []; seriesIds(f, 'observations').forEach(function (id) { f.observations[id].forEach(function (r) { out.push(r[1]); }); }); return out; }
  /* Coverage meter: every figure is a percentage of a whole, so the whole (100%) can be drawn without a new number. */
  function coverageMode(f) {
    return hasObs(f) && !hasRecords(f) && hasShape(f, 'coverage-meter') && isPct(f) && !pointsMode(f) &&
      allObs(f).every(function (v) { return v >= 0 && v <= 100; });
  }
  /* Race to zero: only the series the metric itself describes (the first one) is framed against zero.
     Other series on the same page can measure something else, such as vaccine coverage. */
  function zeroMode(f, sid) {
    return hasObs(f) && !hasRecords(f) && hasShape(f, 'race-to-zero') && f.metric.direction === 'lower' && !pointsMode(f) &&
      seriesIds(f, 'observations')[0] === sid && f.observations[sid].every(function (r) { return r[1] >= 0; });
  }
  /* A fall of a hundredfold or more only shows on a log scale; smaller falls stay linear, where zero is the baseline. */
  function zeroScale(rows) {
    var pos = rows.map(function (r) { return r[1]; }).filter(function (v) { return v > 0; });
    return pos.length > 1 && Math.max.apply(null, pos) / Math.min.apply(null, pos) >= 100 ? 'log' : 'linear';
  }
  /* Threshold gauge: the line a record has to cross is the metric's target, or failing that its limit. */
  function gaugeLine(f, sid) {
    var out = null;
    ['target', 'limit'].forEach(function (k) {
      var m = f.metric[k];
      if (!out && m && typeof m.value === 'number' && (!m.series || m.series === sid)) out = { kind: k, value: m.value, label: m.label || '', by: m.by || '' };
    });
    return out;
  }
  function gaugeMode(f, sid) {
    var log = f.metric.scale === 'log', line = hasRecords(f) && hasShape(f, 'threshold-gauge') && f.metric.direction !== 'lower' ? gaugeLine(f, sid) : null;
    return !!line && line.value > 0 && f.records[sid].every(function (r) { return log ? r[1] > 0 : r[1] >= 0; });
  }
  /* Reign timeline: consecutive records by the same holder are one reign, which lasts until someone else's record. */
  function reigns(f, sid) {
    var out = [];
    progression(f, f.records[sid]).forEach(function (p) {
      var last = out[out.length - 1], who = p.r[2] || '';
      if (last && last.who === who) { last.n += 1; last.best = p.r; last.dates.push(p.r[0]); }
      else out.push({ who: who, from: p.r[0], n: 1, best: p.r, dates: [p.r[0]], until: null });
    });
    out.forEach(function (x, i) { if (out[i + 1]) x.until = out[i + 1].from; });
    return out;
  }
  function reignMode(f, sid) {
    return hasRecords(f) && hasShape(f, 'reign-timeline') && reigns(f, sid).length > 1 && f.records[sid].every(function (r) { return r[2]; });
  }
  /* The pace of records: drawn when the selected series has had at least three records, so there are two waits to compare. */
  function paceMode(f, sid) { return hasRecords(f) && progression(f, f.records[sid]).length >= 3; }
  /* The time from one date to a later one, as precisely as the two dates allow. */
  function waitText(a, b) {
    var x = parseDate(a), y = parseDate(b), n;
    if (!x.m || !y.m) { n = y.y - x.y; return n < 1 ? 'Same year' : 'About ' + n + (n === 1 ? ' year' : ' years'); }
    if (!x.d || !y.d) {
      n = (y.y - x.y) * 12 + y.m - x.m;
      return n < 1 ? 'Same month' : n < 24 ? 'About ' + n + (n === 1 ? ' month' : ' months') : 'About ' + (Math.round(n / 12 * 10) / 10) + ' years';
    }
    n = Math.round((Date.UTC(y.y, y.m - 1, y.d) - Date.UTC(x.y, x.m - 1, x.d)) / 864e5);
    if (n < 61) return n < 1 ? 'Same day' : n + (n === 1 ? ' day' : ' days');
    return n < 730 ? Math.round(n / 30.44) + ' months' : (Math.round(n / 365.25 * 10) / 10) + ' years';
  }
  /* Coming down: a record that is a limit or an uncertainty, where lower is better and the scale is log. The scale ladder
     already covers the series that name it, so those are left to it. */
  function downMode(f, sid) {
    if (!hasRecords(f) || f.metric.direction !== 'lower' || f.metric.scale !== 'log' || hasShape(f, 'scale-ladder')) return false;
    var prog = progression(f, f.records[sid]);
    return prog.length > 1 && prog.every(function (p) { return p.r[1] > 0; });
  }
  function isLimit(f) { return hasShape(f, 'closing-bounds') || hasShape(f, 'exclusion-map'); }
  /* To-scale line-up: the records of a series side by side, each drawn in proportion to its value. */
  function lineupMode(f, sid) {
    if (!hasRecords(f) || !hasShape(f, 'to-scale-lineup') || f.metric.direction === 'lower' || f.metric.scale === 'log') return false;
    var prog = progression(f, f.records[sid]);
    return prog.length > 1 && prog.every(function (p) { return p.r[1] > 0; });
  }
  /* When the measure is itself a diameter, the line-up can be drawn as discs of that diameter. */
  function discMode(f) { return /diameter/i.test(f.metric.name || '') && /^(mm|cm|m|km|metres?|meters?|kilometres?|kilometers?)$/i.test(f.metric.unit || ''); }
  /* Claim scoreboard on a records frontier: the claims are the records themselves, each with its status. */
  function recClaimMode(f) { return hasRecords(f) && hasShape(f, 'claim-scoreboard'); }
  /* Precision funnel: measurements of one quantity by several methods, compared by the range each source gives. */
  function ranged(r) { return r[2] !== null && r[2] !== undefined && r[3] !== null && r[3] !== undefined; }
  function funnelRows(f) {
    var out = [];
    seriesIds(f, 'observations').forEach(function (id) { f.observations[id].forEach(function (r) { out.push({ id: id, r: r }); }); });
    return out;
  }
  function funnelMode(f) {
    return hasObs(f) && !hasRecords(f) && hasShape(f, 'precision-funnel') && !pointsMode(f) &&
      funnelRows(f).filter(function (x) { return ranged(x.r); }).length >= 2;
  }
  /* Item lists. A problem list is shown as a list only, with no counts and nothing drawn over time. */
  var ITEM_ORDER = ['done', 'partial', 'disputed', 'open'], MARK_AS = { done: 'confirmed', partial: 'peer_reviewed', disputed: 'retracted' };
  function itemMark(s, color, size) { return mark(MARK_AS[s] || 'claimed', color, size); }
  function gridMode(f) { return f.items.length > 0 && f.items.length <= 400 && f.shape !== 'problem-list'; }
  function claimMode(f) { return gridMode(f) && f.shape === 'claim-scoreboard'; }
  function datedItems(f) { return f.items.filter(function (i) { return i[5]; }); }
  function itemTimeMode(f) { var n = datedItems(f).length; return gridMode(f) && n >= 3 && n * 2 >= f.items.length; }
  /* The newest dated entry, or null when the dates cannot say which is newest (two in the same year, one dated to the year only). */
  function newestItem(f) {
    var top = null, clash = false;
    datedItems(f).forEach(function (i) {
      if (!top) { top = i; return; }
      var a = parseDate(i[5]), b = parseDate(top[5]);
      var same = a.y === b.y && (!a.m || !b.m || (a.m === b.m && (!a.d || !b.d || a.d === b.d)));
      if (same) { clash = true; if (a.t > b.t) top = i; }
      else if (a.t > b.t) { top = i; clash = false; }
    });
    return clash ? null : top;
  }
  function itemCounts(list) {
    var n = {}; list.forEach(function (i) { n[i[3]] = (n[i[3]] || 0) + 1; });
    return ITEM_ORDER.filter(function (s) { return n[s]; }).map(function (s) { return { s: s, n: n[s] }; });
  }
  /* Stage dates: every dated entry in a candidate's history. */
  function stageDates(f) {
    var out = [];
    f.candidates.forEach(function (c) { (c.history || []).forEach(function (h) { if (h.date) out.push({ c: c, h: h, i: f.stages.indexOf(h.stage) }); }); });
    return out;
  }
  function stageDatesMode(f) { return stageDates(f).length >= 2; }
  /* Cost curve: the figures of the selected series as { d, v, who }. Where every series is a single entry
     (one rocket, one year) the curve is the cheapest entry so far, in date order. */
  function costRows(f, sid) {
    if (!pointsMode(f)) return (f.observations[sid] || []).map(function (r) { return { d: r[0], v: r[1], who: '' }; });
    var all = [], best = null, out = [];
    seriesIds(f, 'observations').forEach(function (id) { var r = f.observations[id][0]; all.push({ d: r[0], v: r[1], who: seriesMeta(f, id).label }); });
    all.sort(function (a, b) { return parseDate(a.d).t - parseDate(b.d).t || a.v - b.v; });
    all.forEach(function (r) { if (best === null || r.v < best) { out.push(r); best = r.v; } });
    return out;
  }
  function costMode(f, sid) {
    if (!hasObs(f) || hasRecords(f) || !hasShape(f, 'cost-curve') || f.metric.direction !== 'lower') return false;
    var rows = costRows(f, sid);
    return rows.length > 1 && rows.every(function (r) { return r.v > 0; }) && rows[rows.length - 1].v < rows[0].v;
  }
  /* Each halving of the first figure, with the first row at or below it. One row can reach several halvings. */
  function halvings(rows) {
    var first = rows[0].v, out = [], k = 1;
    rows.forEach(function (r) { while (r.v <= first / Math.pow(2, k)) { out.push({ k: k, level: first / Math.pow(2, k), r: r }); k += 1; } });
    return out;
  }
  /* Scale ladder: the best-so-far figures of a series as { d, v, who }, and the powers of ten they passed on the way. */
  function ladderRows(f, sid) {
    var b = block(f); if (!b || !f[b][sid] || (b === 'observations' && pointsMode(f))) return [];
    return progression(f, f[b][sid]).map(function (p) { return { d: p.r[0], v: p.r[1], who: b === 'records' ? p.r[2] || '' : '' }; });
  }
  function ladderMode(f, sid) {
    var rows = hasShape(f, 'scale-ladder') ? ladderRows(f, sid) : [];
    return rows.length > 1 && rows.every(function (r) { return r.v > 0; });
  }
  function pow10(e) { return Number('1e' + e); }
  function pow10Label(e, plain) { return plain ? fmt(pow10(e)) : '10' + sup(e); }
  function rungs(f, rows) {
    var down = f.metric.direction === 'lower', first = rows[0].v, top = rows[rows.length - 1].v, e = Math.round(Math.log10(first)), out = [];
    function beyond(p, v) { return down ? p < v : p > v; }       // is the power of ten p further on than the figure v?
    while (!beyond(pow10(e), first)) e += down ? -1 : 1;
    while (beyond(pow10(e - (down ? -1 : 1)), first)) e -= down ? -1 : 1;
    for (; !beyond(pow10(e), top); e += down ? -1 : 1) out.push({ e: e, p: pow10(e), r: rows.filter(function (r) { return !beyond(pow10(e), r.v); })[0] });
    return { passed: out, next: e };
  }
  function peakRow(rows) { var p = rows[0]; rows.forEach(function (r) { if (r[1] > p[1]) p = r; }); return p; }
  function selectedId(f) {
    var b = block(f); if (!b) return null;
    var ids = seriesIds(f, b);
    if (ids.indexOf(chosen[f.id]) >= 0) return chosen[f.id];
    if (ids.indexOf(f.featured) >= 0) return f.featured;
    return b === 'records' ? bestSeries(f, b) : ids[0];
  }
  /* The one number a frontier leads with, or null when it has none (a problem list has no score). */
  function headline(f, sid) {
    var b = block(f); if (!b) return null;
    sid = sid || selectedId(f);
    var rows = f[b][sid], meta = seriesMeta(f, sid);
    if (b === 'records') {
      var prog = progression(f, rows), top = prog[prog.length - 1];
      return { value: top.r[1], date: top.r[0], who: top.r[2], status: top.r[4], label: meta.label, gain: top.gain, prev: prog.length > 1 ? prog[prog.length - 2].r : null, kind: 'Current record' };
    }
    if (pointsMode(f)) {
      var bid = bestSeries(f, b), r = f[b][bid][0];
      return { value: r[1], date: r[0], who: seriesMeta(f, bid).label, status: '', label: seriesMeta(f, bid).label, kind: f.metric.direction === 'lower' ? 'Lowest so far' : 'Highest so far' };
    }
    var last = rows[rows.length - 1], before = rows.length > 1 ? rows[rows.length - 2] : null;
    return { value: last[1], date: last[0], who: '', status: '', label: meta.label, low: last[2], high: last[3], gain: before ? last[1] - before[1] : null, prev: before, kind: 'Latest figure' };
  }

  /* ---------- charts ---------- */
  function palette(dark) {
    return dark
      ? { line: '#FF7A40', text: '#B6BCC3', strong: '#F4F5F1', grid: '#2A3037', axis: '#5B636C', faint: '#4A525B', bg: '#0F1317', mark: '#B6BCC3', band: 'rgba(255,122,64,0.16)', hot: '#FFFFFF' }
      : { line: '#0F1317', text: '#4F5760', strong: '#0F1317', grid: '#D3D6CF', axis: '#0F1317', faint: '#B9BDB5', bg: '#FAFAF7', mark: '#1E34D8', band: 'rgba(15,19,23,0.10)', hot: '#E4531A' };
  }
  function niceStep(span, n) {
    var raw = span / n, p = Math.pow(10, Math.floor(Math.log10(raw))), m = raw / p;
    return (m <= 1 ? 1 : m <= 2 ? 2 : m <= 2.5 ? 2.5 : m <= 5 ? 5 : 10) * p;
  }
  /* A value axis, linear or log, as { Y, ticks:[{v,label}] } over height H. */
  function valueAxis(values, scale, H, sfx) {
    var vs = values.filter(function (v) { return v !== null && v !== undefined && !isNaN(v) && (scale !== 'log' || v > 0); });
    var lo = Math.min.apply(null, vs), hi = Math.max.apply(null, vs), ticks = [], v;
    if (scale === 'log') {
      var a = Math.floor(Math.log10(lo)), b = Math.ceil(Math.log10(hi)); if (a === b) b += 1;
      var every = Math.max(1, Math.ceil((b - a) / 7));
      for (v = a; v <= b; v += 1) if ((v - a) % every === 0) ticks.push({ v: Math.pow(10, v), label: (v >= -3 && v <= 4 ? fmt(Math.pow(10, v)) : '10' + sup(v)) + sfx });
      return { Y: function (x) { return H - (Math.log10(Math.max(x, Math.pow(10, a))) - a) / (b - a) * H; }, ticks: ticks };
    }
    var base = lo < 0 ? lo : 0, step = niceStep((hi - base) || 1, 5), top = Math.ceil(hi * 1.02 / step) * step;
    for (v = base + step; v <= top + step / 1000; v += step) ticks.push({ v: v, label: fmt(v) + sfx });
    return { Y: function (x) { return H - (x - base) / (top - base) * H; }, ticks: ticks };
  }
  function timeTicks(t0, t1) {
    var span = t1 - t0, step = span > 60 ? 20 : span > 25 ? 10 : span > 12 ? 5 : span > 6 ? 2 : 1, out = [], y;
    for (y = Math.ceil(t0 / step) * step; y <= t1; y += step) out.push(y);
    return out;
  }
  /* Marks after the FG marker sit inside a clip rectangle. In the browser the rectangle widens as the chart
     scrolls into view, so the chart draws itself from left to right. Without scripting the clip is full width. */
  var FG = '<!--fg-->', sweepN = 0;
  function sweep(o, W, H, cursor) {
    var parts = o.split(FG), id = 'sw' + (++sweepN);
    if (parts.length < 2) return o;
    return parts[0] + '<clipPath id="' + id + '"><rect class="sw-rect" x="-14" y="-40" width="' + (W + 28) + '" height="' + (H + 80) + '"/></clipPath>' +
      '<g clip-path="url(#' + id + ')">' + parts[1] + '</g>' +
      (cursor ? '<g class="sw-cursor" visibility="hidden"><path d="M0 -4 V' + H + '" stroke="#E4531A" stroke-width="1.5"/><text y="-9" text-anchor="middle" font-size="13" font-weight="500" fill="#E4531A"></text></g>' : '');
  }
  function frame(o, W, H, aria, credit, span, box) {
    return '<div class="chart-box"><svg role="img" data-sweep data-w="' + W + '"' + (span ? ' data-t0="' + span[0] + '" data-t1="' + span[1] + '"' : '') +
      ' aria-label="' + esc(aria) + '" viewBox="' + (box || '-96 -22 ' + (W + 114) + ' ' + (H + 58)) + '">' + sweep(o, W, H, true) + '</svg></div>' +
      (credit ? '<p class="credit">' + esc(credit) + '</p>' : '');
  }
  /* The credit printed under every chart of a frontier: each credit line the data gives, once, in the source's or the data file's own words. */
  function creditLine(f) {
    var seen = {};
    return f.credits.map(function (c) { return c.line; }).filter(function (l) { if (!l || seen[l]) return false; seen[l] = 1; return true; })
      .reduce(function (all, l) { return !all ? l : all + (/[.!?]$/.test(all) ? ' ' : ' · ') + l; }, '');
  }

  /* Value over time. lines: [{pts:[[t,v]], step, faint, band:[[t,lo,hi]]}], dots: [[t,v,strong]], marks: [{v,label}] */
  function timeChart(f, o, dark) {
    var c = palette(dark), W = 880, H = 400, tN = nowT(), ts = [], vs = [], out = '', anyStep = false;
    o.lines.forEach(function (l) {
      if (l.step) anyStep = true;
      l.pts.forEach(function (p) { ts.push(p[0]); vs.push(p[1]); });
      (l.band || []).forEach(function (b) { vs.push(b[1], b[2]); });
    });
    (o.dots || []).forEach(function (d) { ts.push(d[0]); vs.push(d[1]); });
    (o.marks || []).forEach(function (m) { vs.push(m.v); });
    var tMax = Math.max.apply(null, ts), t0 = Math.floor(Math.min.apply(null, ts)), t1 = Math.ceil((anyStep ? Math.max(tMax, tN) : tMax) + 0.1);
    if (t1 - t0 < 2) t0 -= 1;
    /* o.whole fixes the axis from nothing to the whole. o.zero marks zero as the line to reach; on a log scale,
       which has no zero, zero gets a rail of its own under a break in the axis. */
    var scale = o.scale || f.metric.scale, rail = o.zero && scale === 'log', Hp = rail ? H - 44 : H, raw, k5;
    if (o.whole) {
      raw = { Y: function (x) { return H - x / o.whole * H; }, ticks: [] };
      for (k5 = 1; k5 <= 5; k5 += 1) raw.ticks.push({ v: o.whole * k5 / 5, label: fmt(o.whole * k5 / 5) + suffix(f) });
    } else raw = valueAxis(vs, scale, Hp, suffix(f));
    var ax = { ticks: raw.ticks, Y: function (v) { return rail && v <= 0 ? H : raw.Y(v); } };
    function X(t) { return (t - t0) / (t1 - t0) * W; }
    ax.ticks.forEach(function (k) {
      out += '<path d="M0 ' + ax.Y(k.v).toFixed(1) + ' H' + W + '" stroke="' + c.grid + '" stroke-width="1"/>' +
        '<text x="-12" y="' + (ax.Y(k.v) + 4.5).toFixed(1) + '" fill="' + c.text + '" font-size="13" text-anchor="end">' + esc(k.label) + '</text>';
    });
    out += '<path d="M0 ' + H + ' H' + W + '" stroke="' + (o.zero ? c.mark : c.axis) + '" stroke-width="' + (o.zero ? 2 : 1) + '"/>';
    if (o.zero) {
      out += '<text x="-12" y="' + (H + 4.5) + '" fill="' + c.mark + '" font-size="13" font-weight="500" text-anchor="end">0</text>' +
        '<text x="0" y="' + (H - 9) + '" fill="' + c.mark + '" stroke="' + c.bg + '" stroke-width="4" paint-order="stroke" font-size="13">Zero</text>';
      if (rail) out += '<path d="M-7 ' + (Hp + 20) + ' l14 -7 M-7 ' + (Hp + 28) + ' l14 -7" stroke="' + c.axis + '" stroke-width="1.5" fill="none"/>';
    }
    timeTicks(t0, t1).forEach(function (y) {
      out += '<path d="M' + X(y).toFixed(1) + ' ' + H + ' V' + (H + 6) + '" stroke="' + c.axis + '" stroke-width="1"/>' +
        '<text x="' + X(y).toFixed(1) + '" y="' + (H + 26) + '" fill="' + c.text + '" font-size="13" text-anchor="middle">' + y + '</text>';
    });
    out += FG;
    (o.marks || []).forEach(function (m) {
      var y = ax.Y(m.v);
      out += '<path d="M0 ' + y.toFixed(1) + ' H' + W + '" stroke="' + c.mark + '" stroke-width="1.5" stroke-dasharray="3 5" fill="none"/>' +
        '<text x="0" y="' + (y - 9).toFixed(1) + '" fill="' + c.mark + '" stroke="' + c.bg + '" stroke-width="4" paint-order="stroke" font-size="13">' + esc(m.label) + '</text>';
    });
    function path(l) {
      var d = '';
      l.pts.forEach(function (p, i) {
        var x = X(p[0]).toFixed(1), y = ax.Y(p[1]).toFixed(1);
        d += !i ? 'M' + x + ' ' + y : l.step ? ' H' + x + ' V' + y : ' L' + x + ' ' + y;
      });
      return l.step ? d + ' H' + X(Math.max(tN, tMax)).toFixed(1) : d;
    }
    o.lines.filter(function (l) { return l.faint; }).forEach(function (l) {
      if (l.pts.length) out += '<path d="' + path(l) + '" fill="none" stroke="' + c.faint + '" stroke-width="1"/>';
    });
    o.lines.filter(function (l) { return !l.faint; }).forEach(function (l) {
      if (l.band && l.band.length > 1) {
        var up = l.band.map(function (b) { return X(b[0]).toFixed(1) + ' ' + ax.Y(b[2]).toFixed(1); });
        var dn = l.band.slice().reverse().map(function (b) { return X(b[0]).toFixed(1) + ' ' + ax.Y(b[1]).toFixed(1); });
        out += '<path d="M' + up.concat(dn).join(' L') + ' Z" fill="' + c.band + '" stroke="none"/>';
      }
      if (o.whole && l.pts.length > 1) out += '<path d="' + path(l) + ' V' + H + ' H' + X(l.pts[0][0]).toFixed(1) + ' Z" fill="' + c.band + '" stroke="none"/>';
      out += '<path d="' + path(l) + '" fill="none" stroke="' + c.line + '" stroke-width="2.5"/>';
      var dots = '';
      l.pts.forEach(function (p) { dots += '<circle cx="' + X(p[0]).toFixed(1) + '" cy="' + ax.Y(p[1]).toFixed(1) + '" r="3"/>'; });
      if (l.pts.length <= 80) out += '<g fill="' + c.bg + '" stroke="' + c.line + '" stroke-width="1.5">' + dots + '</g>';
    });
    (o.dots || []).forEach(function (d) {
      out += '<circle cx="' + X(d[0]).toFixed(1) + '" cy="' + ax.Y(d[1]).toFixed(1) + '" r="' + (d[2] ? 4 : 3.5) + '" fill="' + (d[2] ? c.line : c.bg) + '" stroke="' + c.line + '" stroke-width="1.5"><title>' + esc(d[3] || '') + '</title></circle>' +
        (d[4] ? '<path d="M' + (X(d[0]) - 6).toFixed(1) + ' ' + (ax.Y(d[1]) + 6).toFixed(1) + ' l12 -12" stroke="' + c.line + '" stroke-width="1.5"/>' : '');
    });
    if (o.label) {
      var lx = X(o.label.t), ly = ax.Y(o.label.v), end = lx > W * 0.35, below = ly < 34 || (o.label.below && ly + 34 < H); // a line falling to its last point leaves room underneath
      if (o.zero && ly < H - 14) out += '<path d="M' + lx.toFixed(1) + ' ' + (ly + 8).toFixed(1) + ' V' + (H - 2) + '" stroke="#E4531A" stroke-width="1.5" stroke-dasharray="2 4" fill="none"/>';
      out += '<circle cx="' + lx.toFixed(1) + '" cy="' + ly.toFixed(1) + '" r="11" fill="#E4531A" fill-opacity="0.22"/>' +
        '<circle cx="' + lx.toFixed(1) + '" cy="' + ly.toFixed(1) + '" r="5.5" fill="' + c.hot + '"/>' +
        '<text x="' + (lx + (end ? -14 : 14)).toFixed(1) + '" y="' + (ly + (below ? 26 : -14)).toFixed(1) + '" fill="' + c.strong + '" stroke="' + c.bg + '" stroke-width="5" paint-order="stroke" font-size="14" font-weight="500" text-anchor="' + (end ? 'end' : 'start') + '">' + esc(o.label.text) + '</text>';
    }
    return frame(out, W, H, o.aria, creditLine(f), [t0, t1]);
  }

  function recordsChart(f, sid, dark) {
    var lines = [], sel = null;
    seriesIds(f, 'records').forEach(function (id) {
      var prog = progression(f, f.records[id]);
      var l = { pts: prog.map(function (p) { return [parseDate(p.r[0]).t, p.r[1]]; }), step: true, faint: id !== sid };
      if (id === sid) sel = prog;
      lines.push(l);
    });
    var top = sel[sel.length - 1].r, marks = [];
    ['limit', 'target'].forEach(function (k) {
      var m = f.metric[k];
      if (m && (!m.series || m.series === sid)) marks.push({ v: m.value, label: (k === 'limit' ? 'Limit: ' : 'Target: ') + fmt(m.value) + suffix(f) });
    });
    var struck = f.records[sid].filter(withdrawn).map(function (r) {
      return [parseDate(r[0]).t, r[1], false, 'Retracted: ' + val(f, r[1]) + (r[2] ? ' · ' + r[2] : '') + ' · ' + fmtDate(r[0]), true];
    });
    return timeChart(f, {
      lines: lines, marks: marks, dots: sel.length < f.records[sid].length ? struck : [],
      label: { t: parseDate(top[0]).t, v: top[1], text: val(f, top[1]) + (top[2] ? ' · ' + top[2] : '') + ' · ' + fmtDate(top[0]) },
      aria: 'Record chart for ' + seriesName(seriesMeta(f, sid)) + ': ' + val(f, sel[0].r[1]) + ' in ' + parseDate(sel[0].r[0]).y + ' to ' + val(f, top[1]) + ' in ' + parseDate(top[0]).y + '.'
    }, dark);
  }
  function obsChart(f, sid, dark) {
    var o;
    if (pointsMode(f)) {
      var bid = bestSeries(f, 'observations'), dots = [], br = f.observations[bid][0];
      seriesIds(f, 'observations').forEach(function (id) {
        var r = f.observations[id][0];
        dots.push([parseDate(r[0]).t, r[1], id === bid, seriesMeta(f, id).label + ': ' + val(f, r[1]) + ' (' + fmtDate(r[0]) + ')']);
      });
      o = { lines: [], dots: dots, label: { t: parseDate(br[0]).t, v: br[1], text: val(f, br[1]) + ' · ' + seriesMeta(f, bid).label + ' · ' + fmtDate(br[0]) },
        aria: 'Each point is one entry, placed by date. ' + (f.metric.direction === 'lower' ? 'Lowest' : 'Highest') + ': ' + seriesMeta(f, bid).label + ' at ' + val(f, br[1]) + '.' };
    } else {
      var rows = f.observations[sid], maxSel = Math.max.apply(null, rows.map(function (r) { return Math.abs(r[1]); })), lines = [];
      seriesIds(f, 'observations').forEach(function (id) {
        var rs = f.observations[id], mx = Math.max.apply(null, rs.map(function (r) { return Math.abs(r[1]); }));
        if (id !== sid && (mx > maxSel * 20 || mx < maxSel / 20)) return; // a different scale: leave it to the picker
        lines.push({ pts: rs.map(function (r) { return [parseDate(r[0]).t, r[1]]; }), faint: id !== sid,
          band: id === sid ? rs.filter(function (r) { return r[2] !== null && r[3] !== null; }).map(function (r) { return [parseDate(r[0]).t, r[2], r[3]]; }) : null });
      });
      var last = rows[rows.length - 1];
      o = { lines: lines, label: { t: parseDate(last[0]).t, v: last[1], text: val(f, last[1]) + ' · ' + fmtDate(last[0]) },
        aria: seriesMeta(f, sid).label + ': ' + val(f, rows[0][1]) + ' in ' + parseDate(rows[0][0]).y + ' to ' + val(f, last[1]) + ' in ' + parseDate(last[0]).y + '.' };
    }
    o.marks = [];
    ['limit', 'target'].forEach(function (k) { var m = f.metric[k]; if (m) o.marks.push({ v: m.value, label: (k === 'limit' ? 'Limit: ' : 'Target: ') + fmt(m.value) + suffix(f) }); });
    if (coverageMode(f)) {
      o.whole = 100;
      if (!o.marks.some(function (m) { return m.v === 100; })) o.marks.push({ v: 100, label: 'The whole: 100%' });
    } else if (zeroMode(f, sid)) {
      var zr = f.observations[sid];
      o.zero = true; o.scale = zeroScale(zr); o.label.below = zr.length > 1 && zr[zr.length - 2][1] > zr[zr.length - 1][1];
    }
    return timeChart(f, o, dark);
  }
  /* The main value against a second measured quantity (metric.axes[0]), for target-zone charts. */
  function scatterChart(f, sid) {
    var ax0 = f.metric.axes[0], c = palette(false), W = 880, H = 400, pts = [], xs = [], ys = [], out = '';
    seriesIds(f, 'records').forEach(function (id) {
      f.records[id].forEach(function (r) {
        var x = r[6] ? r[6][ax0.id] : null;
        if (x === null || x === undefined || x <= 0 || r[1] <= 0) return;
        pts.push({ x: x, y: r[1], on: id === sid, tip: r[2] + ' · ' + fmtDate(r[0]) }); xs.push(x); ys.push(r[1]);
      });
    });
    if (pts.length < 3) return '';
    var target = f.metric.target; if (target) ys.push(target.value);
    var xLog = Math.max.apply(null, xs) / Math.min.apply(null, xs) > 50;
    var ya = valueAxis(ys, f.metric.scale, H, suffix(f)), xa = valueAxis(xs, xLog ? 'log' : 'linear', W, '');
    function X(v) { return W - xa.Y(v); }
    ya.ticks.forEach(function (k) {
      out += '<path d="M0 ' + ya.Y(k.v).toFixed(1) + ' H' + W + '" stroke="' + c.grid + '" stroke-width="1"/>' +
        '<text x="-12" y="' + (ya.Y(k.v) + 4.5).toFixed(1) + '" fill="' + c.text + '" font-size="13" text-anchor="end">' + esc(k.label) + '</text>';
    });
    out += '<path d="M0 ' + H + ' H' + W + '" stroke="' + c.axis + '" stroke-width="1"/>';
    xa.ticks.forEach(function (k) {
      out += '<path d="M' + X(k.v).toFixed(1) + ' ' + H + ' V' + (H + 6) + '" stroke="' + c.axis + '" stroke-width="1"/>' +
        '<text x="' + X(k.v).toFixed(1) + '" y="' + (H + 26) + '" fill="' + c.text + '" font-size="13" text-anchor="middle">' + esc(k.label) + '</text>';
    });
    out += FG;
    if (target) {
      var ty = ya.Y(target.value);
      out += '<rect x="0" y="0" width="' + W + '" height="' + Math.max(0, ty).toFixed(1) + '" fill="rgba(30,52,216,0.06)"/>' +
        '<path d="M0 ' + ty.toFixed(1) + ' H' + W + '" stroke="' + c.mark + '" stroke-width="1.5" stroke-dasharray="3 5" fill="none"/>' +
        '<text x="0" y="' + (ty - 9).toFixed(1) + '" fill="' + c.mark + '" font-size="13">Target zone: above ' + fmt(target.value) + '</text>';
    }
    pts.sort(function (a, b) { return a.on - b.on; }).forEach(function (p) {
      out += '<circle cx="' + X(p.x).toFixed(1) + '" cy="' + ya.Y(p.y).toFixed(1) + '" r="' + (p.on ? 5 : 3.5) + '" fill="' + (p.on ? '#E4531A' : c.bg) + '" stroke="' + (p.on ? '#E4531A' : c.faint) + '" stroke-width="1.5"><title>' + esc(p.tip) + '</title></circle>';
    });
    var name = ax0.name.split(' (')[0];
    return '<div class="wrap block"><h2>' + esc(f.metric.name) + ' against ' + esc(name.charAt(0).toLowerCase() + name.slice(1)) + '</h2><div class="card">' +
      frame(out, W, H, 'Each point is one result: ' + f.metric.name + ' on the vertical axis, ' + name + ' on the horizontal axis.', creditLine(f)) + '</div>' +
      '<p class="small">Horizontal axis: ' + esc(ax0.name) + ', in ' + esc(ax0.unit) + '. Orange points are the selected series. ' + (target ? esc(target.label) + '.' : '') + '</p></div>';
  }
  /* A small line for the front-page tiles. */
  function spark(f) {
    var b = block(f); if (!b) return '';
    var pts;
    if (b === 'observations' && pointsMode(f)) {
      pts = []; seriesIds(f, b).forEach(function (id) { var r = f[b][id][0]; pts.push([parseDate(r[0]).t, r[1]]); });
      pts.sort(function (a, c) { return a[0] - c[0]; });
    } else {
      var rows = f[b][selectedId(f)];
      pts = (b === 'records' ? progression(f, rows).map(function (p) { return p.r; }) : rows).map(function (r) { return [parseDate(r[0]).t, r[1]]; });
    }
    if (!pts.length) return '';
    if (pts.length < 2) {
      /* A single result: one mark, and for a record the level it has stood at since. */
      var held = b === 'records' && nowT() > pts[0][0];
      return '<svg class="spark" aria-hidden="true" data-sweep data-w="240" viewBox="0 0 240 56">' + sweep(FG +
        (held ? '<path d="M4 28 H236" fill="none" stroke="#0F1317" stroke-width="2"/>' : '') +
        '<circle cx="' + (held ? 4 : 236) + '" cy="28" r="4" fill="#E4531A"/>', 240, 56, false) + '</svg>';
    }
    var log = f.metric.scale === 'log', tr = function (v) { return log ? Math.log10(Math.max(v, 1e-300)) : v; };
    var t0 = pts[0][0], t1 = Math.max(pts[pts.length - 1][0], b === 'records' ? nowT() : 0), vs = pts.map(function (p) { return tr(p[1]); });
    var lo = Math.min.apply(null, vs), hi = Math.max.apply(null, vs); if (hi === lo) hi = lo + 1;
    function X(t) { return (t - t0) / ((t1 - t0) || 1) * 232 + 4; }
    function Y(v) { return 50 - (tr(v) - lo) / (hi - lo) * 44; }
    var d = '', step = b === 'records', dotsOnly = b === 'observations' && pointsMode(f), last = pts[pts.length - 1], body;
    pts.forEach(function (p, i) { d += !i ? 'M' + X(p[0]).toFixed(1) + ' ' + Y(p[1]).toFixed(1) : step ? ' H' + X(p[0]).toFixed(1) + ' V' + Y(p[1]).toFixed(1) : ' L' + X(p[0]).toFixed(1) + ' ' + Y(p[1]).toFixed(1); });
    if (step) d += ' H' + X(t1).toFixed(1);
    body = dotsOnly ? pts.map(function (p) { return '<circle cx="' + X(p[0]).toFixed(1) + '" cy="' + Y(p[1]).toFixed(1) + '" r="2" fill="#0F1317"/>'; }).join('')
      : '<path d="' + d + '" fill="none" stroke="#0F1317" stroke-width="2"/><circle cx="' + X(last[0]).toFixed(1) + '" cy="' + Y(last[1]).toFixed(1) + '" r="4" fill="#E4531A"/>';
    return '<svg class="spark" aria-hidden="true" data-sweep data-w="240" viewBox="0 0 240 56">' + sweep(FG + body, 240, 56, false) + '</svg>';
  }
  /* A tile's small drawing of an item list: one square per entry, in the order the data lists them, drawn by status as on the page. */
  function listSpark(f) {
    var n = f.items.length, sizes = [14, 12, 10, 8, 7, 6, 5, 4, 3], s = 3, g = 1, cols = 60, k, newest = newestItem(f), o = '';
    for (k = 0; k < sizes.length; k += 1) {
      var gg = sizes[k] >= 8 ? 3 : sizes[k] >= 5 ? 2 : 1, cc = Math.floor((240 + gg) / (sizes[k] + gg));
      if (Math.ceil(n / cc) * (sizes[k] + gg) - gg <= 56) { s = sizes[k]; g = gg; cols = cc; break; }
    }
    var top = 56 - (Math.ceil(n / cols) * (s + g) - g), sw = s >= 8 ? 1.5 : 1;
    f.items.forEach(function (i, j) {
      var x = (j % cols) * (s + g), y = top + Math.floor(j / cols) * (s + g), col = i === newest ? '#E4531A' : '#0F1317', st = i[3];
      if (st === 'done') { o += '<rect x="' + x + '" y="' + y + '" width="' + s + '" height="' + s + '" fill="' + col + '"/>'; return; }
      o += '<rect x="' + (x + sw / 2) + '" y="' + (y + sw / 2) + '" width="' + (s - sw) + '" height="' + (s - sw) + '" fill="none" stroke="' + col + '" stroke-width="' + sw + '"/>';
      if (st === 'partial') o += '<rect x="' + x + '" y="' + y + '" width="' + s / 2 + '" height="' + s + '" fill="' + col + '"/>';
      if (st === 'disputed') o += '<path d="M' + x + ' ' + (y + s) + ' L' + (x + s) + ' ' + y + '" stroke="' + col + '" stroke-width="' + sw + '"/>';
    });
    return '<svg class="spark" aria-hidden="true" data-sweep data-w="240" viewBox="0 0 240 56">' + sweep(FG + o, 240, 56, false) + '</svg>';
  }
  /* A tile's small drawing of a stage timeline: one row per candidate, one segment per stage, filled as far as it has got. */
  function furthestStage(f) { var at = -1; f.candidates.forEach(function (c) { at = Math.max(at, f.stages.indexOf(c.stage)); }); return at; }
  function stageSpark(f) {
    var n = f.stages.length, rows = f.candidates.slice().sort(function (a, b) { return f.stages.indexOf(b.stage) - f.stages.indexOf(a.stage); });
    if (!n || !rows.length) return '';
    var gap = rows.length > 8 ? 1 : 4, rh = Math.min(8, (56 - gap * (rows.length - 1)) / rows.length), w = (240 - 3 * (n - 1)) / n;
    var top = 56 - (rows.length * (rh + gap) - gap), o = '', fg = '';
    rows.forEach(function (c, k) {
      var at = f.stages.indexOf(c.stage), y = (top + k * (rh + gap)).toFixed(1), i;
      for (i = 0; i < n; i += 1) {
        var r = '<rect x="' + (i * (w + 3)).toFixed(1) + '" y="' + y + '" width="' + w.toFixed(1) + '" height="' + rh.toFixed(1) + '" fill="' + (i < at ? '#0F1317' : i === at ? '#E4531A' : '#E3E5DF') + '"/>';
        if (i <= at) fg += r; else o += r;
      }
    });
    return '<svg class="spark" aria-hidden="true" data-sweep data-w="240" viewBox="0 0 240 56">' + sweep(o + FG + fg, 240, 56, false) + '</svg>';
  }
  /* The small drawing on a tile. A problem list gets none: it is a list, not a score. */
  function tileChart(f) {
    if (block(f)) return spark(f);
    if (f.candidates.length) return stageSpark(f);
    return gridMode(f) ? listSpark(f) : '';
  }

  /* ---------- front page ---------- */
  function bigNumber(f, h) {
    return '<div class="big' + (fmt(h.value).length > 12 ? ' long xlong' : fmt(h.value).length > 6 ? ' long' : '') + '">' + fmt(h.value) + (suffix(f) ? '<span class="unit">' + suffix(f) + '</span>' : '') + '</div>' +
      (unitText(f) ? '<div class="unitline">' + esc(unitText(f)) + '</div>' : '');
  }
  function tile(f) {
    var h = headline(f), draft = f.dataStatus === 'draft', far = !h && f.candidates.length ? furthestStage(f) : -1;
    return '<a class="tile" href="#' + esc(f.id) + '"><span class="trow eyebrow"><span>' + esc(f.subfield || f.domain) + '</span><span>' + esc(shapeLabel(f)) + '</span></span>' +
      (h ? '<span class="tnum">' + fmt(h.value) + (suffix(f) ? '<i>' + suffix(f) + '</i>' : '') + '</span>' + (unitText(f) ? '<span class="tunit">' + esc(unitText(f)) + '</span>' : '')
        : far >= 0 ? '<span class="tnum words">' + esc(f.stages[far]) + '</span><span class="tunit">furthest stage reached · ' + f.candidates.length + ' tracked</span>'
        : '<span class="tnum words">' + (f.items.length && f.shape !== 'problem-list' ? fmt(f.items.length) + ' listed' : esc(shapeLabel(f))) + '</span>') +
      '<span class="ttitle">' + esc(f.title) + '</span>' + tileChart(f) +
      '<span class="trow tfoot"><span>' + (h ? esc((h.who ? h.who + ' · ' : '') + fmtDate(h.date)) : 'Updated ' + esc(fmtDate(f.lastChecked))) + '</span>' +
      (draft ? '<span class="draft">Draft data</span>' : h && h.status ? statusHtml(h.status, '#0F1317') : '') + '</span></a>';
  }
  /* The front page's tiles, grouped by domain and narrowed by the search box and the two filters. */
  function tileMatches(f) {
    var q = homeState.q.trim().toLowerCase();
    return (homeState.domain === 'all' || f.domain === homeState.domain) && (homeState.shape === 'all' || f.shape === homeState.shape) &&
      (!q || [f.title, f.domain, f.subfield, shapeLabel(f), f.metric.name, f.summary].join(' ').toLowerCase().indexOf(q) >= 0);
  }
  function tilesList() {
    var shown = 0, filtered = homeState.q.trim() || homeState.domain !== 'all' || homeState.shape !== 'all';
    var groups = byDomain().map(function (g) {
      var list = g.list.filter(tileMatches); shown += list.length;
      return list.length ? '<section class="tgroup"><h3><span>' + esc(g.name) + '</span><span class="eyebrow">' + list.length + (list.length === 1 ? ' frontier' : ' frontiers') + '</span></h3>' +
        '<div class="tiles">' + list.map(tile).join('') + '</div></section>' : '';
    }).join('');
    return '<p class="small" aria-live="polite">' + (filtered ? 'Showing ' + shown + ' of ' + D.frontiers.length + ' frontiers.' : 'Showing all ' + D.frontiers.length + ' frontiers, grouped by domain.') + '</p>' +
      (shown ? groups : '<p class="empty">No frontier matches that search.</p>') +
      (filtered ? '<button type="button" class="more" id="home-clear">Clear the search and filters</button>' : '');
  }
  function tilesFilters() {
    var doms = byDomain(), shapes = [], n = {};
    ordered().forEach(function (f) { if (!n[f.shape]) { n[f.shape] = 0; shapes.push(f.shape); } n[f.shape] += 1; });
    shapes.sort(function (a, b) { return n[b] - n[a] || (a < b ? -1 : 1); });
    return '<div class="filters" role="search"><div class="grow"><label for="home-q">Search the frontiers</label><input id="home-q" type="search" value="' + esc(homeState.q) + '" placeholder="Name, field or measure"></div>' +
      '<div><label for="home-domain">Domain</label><select id="home-domain"><option value="all">All domains</option>' + doms.map(function (g) {
        return '<option value="' + esc(g.name) + '"' + (homeState.domain === g.name ? ' selected' : '') + '>' + esc(g.name) + ' (' + g.list.length + ')</option>'; }).join('') + '</select></div>' +
      '<div><label for="home-shape">Chart shape</label><select id="home-shape"><option value="all">All shapes</option>' + shapes.map(function (s) {
        return '<option value="' + esc(s) + '"' + (homeState.shape === s ? ' selected' : '') + '>' + esc(shapeLabel({ shape: s })) + ' (' + n[s] + ')</option>'; }).join('') + '</select></div></div>';
  }
  function home() {
    var lead = D.frontiers.filter(function (x) { return x.id === D.site.lead && hasRecords(x); })[0] || D.frontiers.filter(hasRecords)[0];
    var inDomain = {}; ordered().forEach(function (x) { (inDomain[x.domain] = inDomain[x.domain] || []).push(x); });
    var feature = '';
    if (lead) {
      var sid = selectedId(lead), h = headline(lead, sid), total = 0, ids = seriesIds(lead, 'records');
      ids.forEach(function (id) { total += lead.records[id].length; });
      feature = '<section class="feature dark" id="live"><div class="wrap inner">' +
        '<div class="row eyebrow"><span>' + esc(lead.domain) + ' · ' + esc(lead.subfield) + '</span><span>' + esc(shapeLabel(lead)) + '</span></div>' +
        '<div class="main"><div class="copy">' + bigNumber(lead, h) +
          '<h2>' + esc(lead.title) + (ids.length > 1 ? ': ' + esc(h.label) : '') + '</h2>' +
          '<p class="lede">One line on a chart of ' + fmt(total) + ' results across ' + ids.length + ' series, going back to ' + parseDate(firstDate(lead)).y + '.</p>' +
          '<div class="meta"><span>' + esc(h.who) + ' · ' + esc(fmtDate(h.date)) + '</span>' + statusHtml(h.status, '#F4F5F1') + '</div>' +
          '<div><a class="pill pill-hot" href="#' + esc(lead.id) + '">Open the full record ' + ARROW + '</a></div>' +
        '</div><div class="chart">' + recordsChart(lead, sid, true) + '</div></div></div></section>';
    }
    var doms = D.domains.map(function (name, i) {
      var list = inDomain[name] || [];
      return '<li class="' + (list.length ? 'on' : '') + '"><span class="n">' + (i < 9 ? '0' : '') + (i + 1) + '</span><span class="dn"><span>' + esc(name) + '</span>' +
        (list.length ? '<span class="dl">' + list.map(function (x) { return '<a href="#' + esc(x.id) + '">' + esc(x.title) + '</a>'; }).join('') + '</span>' : '') + '</span>' +
        (list.length ? '<span class="live"><i></i>' + list.length + ' live</span>' : '') + '</li>';
    }).join('');
    var queue = D.planned.length ? '<ul class="rows">' + D.planned.map(function (x) {
      return '<li><span class="d">' + esc(x.domain) + '</span><span class="t">' + esc(x.title) + '</span><span class="s">' + esc(x.shape) + '</span><span class="w">Next in the queue</span></li>';
    }).join('') + '</ul>' : '';

    return '<div class="stack">' +
      '<section class="hero dark"><img src="img/moon.jpg" alt="The cratered surface of the Moon seen from orbit, with black sky above the horizon"><div class="fade" aria-hidden="true"></div>' +
        '<div class="wrap inner"><div class="top"><header class="nav">' + nav('#F4F5F1') + '</header>' +
          '<div><div class="eyebrow">Science and technology, by the numbers</div><h1>How far has the frontier moved?</h1></div></div>' +
          '<div class="foot"><p>The current record on the hardest problems in science and technology. Each one is charted, linked to its source and marked with how well it has been checked.</p>' +
          '<a class="pill pill-ghost" href="#frontiers">See all ' + D.frontiers.length + ' frontiers ' + ARROW + '</a></div></div></section>' + feature + '</div>' +

      '<section class="band" id="frontiers"><div class="wrap"><div class="head"><h2>' + D.frontiers.length + ' frontiers so far</h2>' +
        '<p>Each one gets the chart that fits it. New ones appear here as their data is sourced and checked.</p></div>' +
        tilesFilters() + '<div id="tiles-list">' + tilesList() + '</div>' + queue + '</div></section>' +

      '<section class="band" id="method"><div class="wrap"><div class="head"><h2>Every record carries a status</h2>' +
        '<p>A number is only as good as the checking behind it, so the mark travels with the number.</p></div>' +
        '<div class="marks">' +
          '<div class="mark">' + mark('claimed', '#0F1317', 22) + '<div><strong>Claimed</strong><span>Announced by the team that did the work.</span></div></div>' +
          '<div class="mark">' + mark('peer_reviewed', '#0F1317', 22) + '<div><strong>Peer reviewed</strong><span>Published after review by other researchers.</span></div></div>' +
          '<div class="mark">' + mark('confirmed', '#0F1317', 22) + '<div><strong>Independently confirmed</strong><span>Measured or reproduced by a separate group.</span></div></div>' +
          '<div class="mark">' + mark('retracted', '#0F1317', 22) + '<div><strong>Retracted</strong><span>Withdrawn or shown not to hold.</span></div></div>' +
        '</div></div></section>' +

      '<section class="section-dark dark" id="domains"><div class="wrap"><div class="head"><h2>' + D.domains.length + ' domains</h2>' +
        '<p>The full map of what the site will cover, in order from the sciences to technology. Domains with frontiers link straight to them.</p></div>' +
        '<ol class="domains">' + doms + '</ol></div></section>' + siteFooter(null);
  }
  function firstDate(f) {
    var m = '9999';
    seriesIds(f, 'records').forEach(function (id) { var r = f.records[id][0]; if (r && r[0] < m) m = r[0]; });
    return m;
  }

  /* ---------- frontier page sections ---------- */
  function picker(f, b, sid) {
    var ids = seriesIds(f, b); if (ids.length < 2) return '';
    var groups = [], by = {};
    ids.forEach(function (id) { var m = seriesMeta(f, id), g = m.group || ''; if (!by[g]) { by[g] = []; groups.push(g); } by[g].push(m); });
    var opts = groups.map(function (g) {
      var inner = by[g].map(function (m) { return '<option value="' + esc(m.id) + '"' + (m.id === sid ? ' selected' : '') + '>' + esc(m.label) + '</option>'; }).join('');
      return g ? '<optgroup label="' + esc(g) + '">' + inner + '</optgroup>' : inner;
    }).join('');
    return '<div class="picker"><label for="series">Series</label><select id="series">' + opts + '</select></div>';
  }
  function recordsSections(f, sid) {
    var rows = f.records[sid], prog = progression(f, rows), top = prog[prog.length - 1], meta = seriesMeta(f, sid), ids = seriesIds(f, 'records');
    var out = '<div class="wrap block"><h2>' + esc(seriesName(meta)) + '</h2><div class="card">' + recordsChart(f, sid, false) + '</div>' +
      '<p class="small">The dark line is the record for the selected series.' + (ids.length > 1 ? ' Thin lines are the other series.' : '') + (top.r[3] ? ' Current record: ' + esc(top.r[3]) + '.' : '') +
      (rows.some(withdrawn) && prog.length < rows.length ? ' A struck ring is a result that was later retracted: it stays on the chart but does not count as a record.' : '') + '</p></div>';
    if (gaugeMode(f, sid)) out += gaugeSection(f, sid);
    if (ladderMode(f, sid)) out += ladderSection(f, sid);
    if (downMode(f, sid)) out += downSection(f, sid);
    if (lineupMode(f, sid)) out += lineupSection(f, sid);
    if (f.metric.axes.length) out += scatterChart(f, sid);
    if (reignMode(f, sid)) out += reignSection(f, sid);
    if (paceMode(f, sid)) out += paceSection(f, sid);
    if (recClaimMode(f)) out += recClaimSection(f);
    if (ids.length > 1) {
      var board = ids.map(function (id) { var p = progression(f, f.records[id]); return { m: seriesMeta(f, id), top: p[p.length - 1].r }; })
        .sort(function (a, b) { return better(f, a.top[1], b.top[1]) ? -1 : 1; });
      var log = f.metric.scale === 'log', vals = board.map(function (x) { return log ? Math.log10(x.top[1]) : x.top[1]; });
      var lo = log ? Math.min.apply(null, vals) - 1 : 0, hi = Math.max.apply(null, vals);
      out += '<div class="wrap block"><h2>Where each series stands</h2><div class="tbl"><table class="board"><thead><tr>' +
        '<th scope="col">#</th><th scope="col">Series</th><th scope="col">Record</th><th scope="col"><span class="vh">Relative size</span></th><th scope="col">Holder</th><th scope="col">Set</th></tr></thead><tbody>' +
        board.map(function (x, i) {
          var on = x.m.id === sid, w = ((log ? Math.log10(x.top[1]) : x.top[1]) - lo) / ((hi - lo) || 1) * 100;
          return '<tr class="' + (on ? 'now' : '') + '"><td class="rank">' + (i + 1) + '</td>' +
            '<td><button type="button" class="pick" data-series="' + esc(x.m.id) + '"' + (on ? ' aria-current="true"' : '') + '>' + esc(x.m.label) + '</button>' + (x.m.group ? '<div class="sub">' + esc(x.m.group) + '</div>' : '') + '</td>' +
            '<td class="v">' + val(f, x.top[1]) + '</td><td class="barcell"><div class="bar" aria-hidden="true"><i style="width:' + Math.max(2, w).toFixed(1) + '%"></i></div></td>' +
            '<td>' + esc(x.top[2]) + '</td><td class="date">' + esc(fmtDate(x.top[0])) + '</td></tr>';
        }).join('') + '</tbody></table></div>' + (log ? '<p class="small">Bars are on a log scale.</p>' : '') + '</div>';
    }
    var isRec = {}; prog.forEach(function (p) { isRec[rows.indexOf(p.r)] = p; });
    out += '<div class="wrap block"><h2>History: ' + esc(meta.label) + '</h2><div class="tbl"><table><thead><tr>' +
      '<th scope="col">Date</th><th scope="col">Result</th><th scope="col">Gain</th><th scope="col">Holder</th><th scope="col">Conditions</th><th scope="col">Status</th><th scope="col">Source</th></tr></thead><tbody>' +
      rows.map(function (r, i) {
        var p = isRec[i];
        return '<tr class="' + (p && p === top ? 'now' : '') + '"><td class="date">' + esc(fmtDate(r[0])) + '</td><td class="v' + (p ? '' : ' dim') + '">' + val(f, r[1]) + '</td>' +
          '<td class="g">' + (p ? (p.gain === null ? 'First' : (p.gain > 0 ? '+' : '') + fmt(p.gain)) : withdrawn(r) ? 'Withdrawn' : 'Not a record') + '</td><td>' + esc(r[2]) + '</td><td class="cond">' + esc(r[3]) + '</td>' +
          '<td>' + statusHtml(r[4], '#0F1317') + '</td><td>' + sourceLink(f, r[5]) + '</td></tr>';
      }).reverse().join('') + '</tbody></table></div></div>';
    return out;
  }
  /* One bar drawn to scale: `frac` of the full width is filled, the newest end in orange. ticks: [{at, blue}] */
  function scaleBar(frac, aria, ticks, credit) {
    var W = 880, w = Math.max(0, Math.min(1, frac)) * W, cap = Math.min(6, w);
    var o = '<rect x="0" y="7" width="' + W + '" height="18" fill="#E3E5DF"/>' + FG +
      '<rect x="0" y="7" width="' + w.toFixed(1) + '" height="18" fill="#0F1317"/>' +
      '<rect x="' + (w - cap).toFixed(1) + '" y="7" width="' + cap.toFixed(1) + '" height="18" fill="#E4531A"/>' +
      (ticks || []).map(function (t) { return '<rect x="' + Math.max(0, Math.min(W - 3, t.at * W - 1.5)).toFixed(1) + '" y="0" width="3" height="32" fill="' + (t.blue ? '#1E34D8' : '#0F1317') + '"/>'; }).join('');
    return '<svg class="scalebar" role="img" data-sweep data-w="' + W + '" aria-label="' + esc(aria) + '" viewBox="0 0 ' + W + ' 32" preserveAspectRatio="none">' + sweep(o, W, 32, false) + '</svg>' +
      (credit ? '<p class="credit">' + esc(credit) + '</p>' : '');
  }
  function cell(cls, label, value) { return '<div class="' + cls + '"><dt>' + label + '</dt><dd>' + value + '</dd></div>'; }
  /* Threshold gauge: the current record drawn against the line it has to cross. On a linear measure the bar starts
     at zero; on a log measure, which has no zero, it starts at the first record in the series. */
  function gaugeSection(f, sid) {
    var line = gaugeLine(f, sid), prog = progression(f, f.records[sid]), top = prog[prog.length - 1].r, first = prog[0].r;
    var L = line.value, log = f.metric.scale === 'log', reached = top[1] >= L, past = top[1] > L, span = Math.max(L, top[1]), hit = null;
    prog.forEach(function (p) { if (!hit && p.r[1] >= L) hit = p.r; });
    function lg(v) { return Math.log10(v); }
    function at(v) { return log ? (lg(v) - lg(first[1])) / (lg(span) - lg(first[1])) : v / span; }
    var drawn = !log || (prog.length > 1 && first[1] < span), ticks = [];
    if (drawn && !log && prog.length > 1) ticks.push({ at: at(first[1]) });
    if (drawn) ticks.push({ at: at(L), blue: true });
    var name = line.kind === 'limit' ? 'limit' : 'line';
    return '<div class="wrap block"><h2>Distance to the ' + name + '</h2>' +
      (drawn ? scaleBar(at(top[1]), 'A bar running ' + (log ? 'on a log scale from the first record in this series, ' + val(f, first[1]) + ',' : 'from zero') + ' to ' +
        (past ? 'the current record' : 'the ' + name + ', ' + val(f, L)) + '. The filled part is the current record, ' + val(f, top[1]) + ', set ' + fmtDate(top[0]) + '.' +
        (past ? ' A blue tick marks the ' + name + ', ' + val(f, L) + '.' : ''), ticks, creditLine(f)) : '') +
      '<dl class="split">' + cell('now', 'Current record · ' + esc(fmtDate(top[0])), val(f, top[1])) +
        (reached ? cell('words', past ? 'Went past the ' + name : 'Reached the ' + name, esc(fmtDate(hit[0]))) : log ? '' : cell('', 'Still to go', val(f, L - top[1]))) +
        (prog.length > 1 ? cell('', 'First record here · ' + esc(fmtDate(first[0])), val(f, first[1])) : '') +
        cell('goal', (line.kind === 'limit' ? 'The limit' : 'The line to cross') + (line.by ? ' · by ' + esc(fmtDate(line.by)) : ''), val(f, L)) + '</dl>' +
      '<p class="small">' + (unitText(f) ? 'Figures are in ' + esc(unitText(f)) + '. ' : '') +
        (drawn ? (log ? 'The bar is a log scale, so equal lengths are equal multiples. It runs from the first record in this series to ' : 'The bar runs from zero to ') +
          (past ? 'the current record, which is past the ' + name : 'the ' + name) + '. The dark part is the current record' +
          (ticks.length > 1 ? ', the black tick is the first record in this series' : '') + ' and the blue tick is the ' + name + '. '
          : 'This series has a single record, so there is no bar to draw on a log scale. ') +
        (!reached && !log ? 'Still to go is the ' + name + ' minus the current record, worked out here and not a figure from the source. ' : '') +
        (line.label ? (line.kind === 'limit' ? 'The limit: ' : 'The line: ') + esc(line.label) + '.' : '') + '</p></div>';
  }
  /* Reign timeline: a ribbon with one block per holder, from the date they took the record to the date it was beaten. */
  function shortName(who) { var s = who.split(/[,(\/]/)[0].trim(); return s.length < who.length ? s + '…' : s; }
  function reignSection(f, sid) {
    var rs = reigns(f, sid), cur = rs[rs.length - 1], c = palette(false), W = 880, H = 62, tN = nowT(), out = '', holders = [], nRec = 0;
    var t0 = Math.floor(parseDate(rs[0].from).t), t1 = Math.ceil(tN + 0.1);
    function X(t) { return (t - t0) / (t1 - t0) * W; }
    rs.forEach(function (x) { if (holders.indexOf(x.who) < 0) holders.push(x.who); nRec += x.n; });
    out += '<path d="M0 ' + H + ' H' + W + '" stroke="' + c.axis + '" stroke-width="1"/>';
    timeTicks(t0, t1).forEach(function (y) {
      out += '<path d="M' + X(y).toFixed(1) + ' ' + H + ' V' + (H + 6) + '" stroke="' + c.axis + '" stroke-width="1"/>' +
        '<text x="' + X(y).toFixed(1) + '" y="' + (H + 26) + '" fill="' + c.text + '" font-size="13" text-anchor="middle">' + y + '</text>';
    });
    out += FG;
    rs.forEach(function (x, i) {
      var on = x === cur, a = X(parseDate(x.from).t), b = x.until ? X(parseDate(x.until).t) : X(tN), w = Math.max(1.5, b - a - 1), label = shortName(x.who);
      out += '<rect x="' + a.toFixed(1) + '" y="16" width="' + w.toFixed(1) + '" height="' + (H - 16) + '" fill="' + (on ? '#E4531A' : i % 2 ? '#4F5760' : '#0F1317') + '">' +
        '<title>' + esc(x.who + ': ' + fmtDate(x.from) + (x.until ? ' to ' + fmtDate(x.until) : ' to now')) + '</title></rect>';
      if (label.length * 7.9 + 16 <= w) out += '<text x="' + (a + 8).toFixed(1) + '" y="' + (16 + (H - 16) / 2 + 4.5).toFixed(1) + '" fill="' + (on ? '#0F1317' : '#F4F5F1') + '" font-size="13" font-weight="500" pointer-events="none">' + esc(label) + '</text>';
      x.dates.forEach(function (d, k) { out += '<path d="M' + (X(parseDate(d).t) + 0.75).toFixed(1) + ' 4 V13" stroke="' + (on && k === x.dates.length - 1 ? '#E4531A' : c.axis) + '" stroke-width="1.5"/>'; });
    });
    var body = rs.slice().reverse().map(function (x) {
      return '<tr class="' + (x === cur ? 'now' : '') + '"><td><strong>' + esc(x.who) + '</strong></td><td class="date">' + esc(fmtDate(x.from)) + '</td>' +
        '<td class="date">' + (x.until ? esc(fmtDate(x.until)) : 'Holds it now') + '</td><td class="g">' + x.n + '</td><td class="v">' + val(f, x.best[1]) + '</td></tr>';
    }).join('');
    return '<div class="wrap block"><h2>Who has held the record</h2>' +
      '<dl class="split">' + cell('now words', 'Current holder · since ' + esc(fmtDate(cur.from)), esc(cur.who)) +
        cell('', 'Holders so far', fmt(holders.length)) + cell('', 'Records they set', fmt(nRec)) + '</dl>' +
      '<div class="card">' + frame(out, W, H, 'A ribbon of who has held the record from ' + parseDate(rs[0].from).y + ' to now, one block per holder. ' + holders.length + ' holders. Current holder: ' + cur.who + ', since ' + fmtDate(cur.from) + '.',
        creditLine(f), [t0, t1], '-10 -24 ' + (W + 20) + ' ' + (H + 58)) + '</div>' +
      '<p class="small">Each block is one holder’s time with the record, from the date they took it to the date someone else beat it. The orange block is the current holder. ' +
        'The marks above the ribbon are the records themselves, the newest in orange; a holder who beats their own record keeps the same block. Every holder is named in the table below' +
        (seriesIds(f, 'records').length > 1 ? ', which covers the selected series only' : '') + '.</p>' +
      '<div class="tbl"><table class="reigns"><thead><tr><th scope="col">Holder</th><th scope="col">Took the record</th><th scope="col">Held it until</th><th scope="col">Records set</th><th scope="col">Best in that time</th></tr></thead><tbody>' + body + '</tbody></table></div></div>';
  }
  /* The pace of records: one tick per record on a time axis, with the longest wait between two records marked. */
  function paceSection(f, sid) {
    var rows = f.records[sid], prog = progression(f, rows), c = palette(false), W = 880, H = 62, tN = nowT(), out = '', fg = '';
    var ds = prog.map(function (p) { return p.r[0]; }), ts = ds.map(function (d) { return parseDate(d).t; }), n = ds.length, last = ds[n - 1], k = 1, i;
    var t0 = Math.floor(ts[0]), t1 = Math.ceil(Math.max(tN, ts[n - 1]) + 0.1);
    if (t1 - t0 < 2) t0 -= 1;
    function X(t) { return (t - t0) / (t1 - t0) * W; }
    for (i = 2; i < n; i += 1) if (ts[i] - ts[i - 1] > ts[k] - ts[k - 1]) k = i;
    out += '<path d="M0 ' + H + ' H' + W + '" stroke="' + c.axis + '" stroke-width="1"/>';
    timeTicks(t0, t1).forEach(function (y) {
      out += '<path d="M' + X(y).toFixed(1) + ' ' + H + ' V' + (H + 6) + '" stroke="' + c.axis + '" stroke-width="1"/>' +
        '<text x="' + X(y).toFixed(1) + '" y="' + (H + 26) + '" fill="' + c.text + '" font-size="13" text-anchor="middle">' + y + '</text>';
    });
    var a = X(ts[k - 1]), b = X(ts[k]), mid = (a + b) / 2, anchor = mid < 170 ? 'start' : mid > W - 170 ? 'end' : 'middle';
    fg += '<path d="M' + a.toFixed(1) + ' 12 V7 H' + b.toFixed(1) + ' V12" fill="none" stroke="' + c.text + '" stroke-width="1"/>' +
      '<text x="' + (anchor === 'start' ? a : anchor === 'end' ? b : mid).toFixed(1) + '" y="-2" fill="' + c.text + '" font-size="13" text-anchor="' + anchor + '">Longest wait</text>';
    prog.forEach(function (p, j) {
      var on = j === n - 1;
      fg += '<path d="M' + X(ts[j]).toFixed(1) + ' 16 V' + H + '" stroke="' + (on ? '#E4531A' : c.line) + '" stroke-width="' + (on ? 3 : 1.5) + '">' +
        '<title>' + esc(val(f, p.r[1]) + (p.r[2] ? ' · ' + p.r[2] : '') + ' · ' + fmtDate(p.r[0])) + '</title></path>';
    });
    var gone = prog.length < rows.length ? rows.filter(withdrawn) : [];
    gone.forEach(function (r) {
      var x = X(parseDate(r[0]).t), y = H / 2 + 8;
      fg += '<g><title>' + esc('Retracted: ' + val(f, r[1]) + (r[2] ? ' · ' + r[2] : '') + ' · ' + fmtDate(r[0])) + '</title>' +
        '<circle cx="' + x.toFixed(1) + '" cy="' + y + '" r="4.5" fill="' + c.bg + '" stroke="' + c.line + '" stroke-width="1.5"/>' +
        '<path d="M' + (x - 6).toFixed(1) + ' ' + (y + 6) + ' l12 -12" stroke="' + c.line + '" stroke-width="1.5"/></g>';
    });
    var checked = f.lastChecked && parseDate(f.lastChecked).t >= ts[n - 1] ? f.lastChecked : '';
    var longer = checked && parseDate(checked).t - ts[n - 1] > ts[k] - ts[k - 1];
    return '<div class="wrap block"><h2>The pace of records</h2>' +
      '<dl class="split">' + cell('now', 'Latest record · ' + esc(fmtDate(last)), val(f, prog[n - 1].r[1])) +
        cell('', 'Records in this series', fmt(n)) +
        cell('words', 'Longest wait between two records · ' + esc(fmtDate(ds[k - 1])) + ' to ' + esc(fmtDate(ds[k])), esc(waitText(ds[k - 1], ds[k]))) +
        (checked ? cell('words', 'Since the latest record · as of the last check, ' + esc(fmtDate(checked)), esc(waitText(last, checked))) : '') + '</dl>' +
      '<div class="card">' + frame(out + FG + fg, W, H, 'One tick for each of the ' + n + ' records in this series, placed by date from ' + parseDate(ds[0]).y + ' to ' + parseDate(last).y +
        '. The longest wait between two records ran from ' + fmtDate(ds[k - 1]) + ' to ' + fmtDate(ds[k]) + '. Latest record: ' + fmtDate(last) + '.',
        creditLine(f), [t0, t1], '-10 -24 ' + (W + 20) + ' ' + (H + 58)) + '</div>' +
      '<p class="small">Each tick is a date on which a new record was set in this series; the orange tick is the latest. The bracket spans the longest wait between two records in a row. ' +
        (gone.length ? 'A struck ring is a result that was later retracted, which is not counted. ' : '') +
        (longer ? 'The wait since the latest record is already longer than any wait between two records here. ' : '') +
        'The count and the waits are worked out on the page from the dates in the data, and are not figures from a source. A date the data gives only to the month or year makes a wait approximate.' +
        (f.dataStatus === 'draft' ? ' This is draft data: a record missing from it would make a wait look longer than it was.' : '') + '</p></div>';
  }
  /* One row per record, oldest first, each with a bar. at(v) gives the filled share of the bar; goalAt, when given,
     is where the blue target mark sits. extra(p, i) is an optional line under the value. */
  function stepRows(f, prog, at, goalAt, extra) {
    var n = prog.length;
    return '<ol class="rsteps">' + prog.map(function (p, i) {
      var r = p.r, on = i === n - 1, w = Math.max(0, Math.min(1, at(r[1]))) * 100, x = extra ? extra(p, i) : '';
      return '<li class="rstep' + (on ? ' now' : '') + '"><div class="st-when">' + esc(fmtDate(r[0])) + '</div>' +
        '<div class="st-who"><strong>' + esc(r[2]) + '</strong>' + (r[3] ? '<span class="st-sub">' + esc(r[3]) + '</span>' : '') + '</div>' +
        '<div class="st-v"><span class="st-n">' + val(f, r[1]) + '</span>' + (x ? '<span class="st-sub">' + x + '</span>' : '') + '</div>' +
        '<div class="st-bar" aria-hidden="true"><i style="width:' + w.toFixed(2) + '%"></i>' +
          (goalAt === null || goalAt === undefined ? '' : '<b style="left:' + (Math.max(0, Math.min(1, goalAt)) * 100).toFixed(2) + '%"></b>') + '</div></li>';
    }).join('') + '</ol>' + (creditLine(f) ? '<p class="credit">' + esc(creditLine(f)) + '</p>' : '');
  }
  /* Coming down: how far each record reached below the first one, on a log scale, with the target marked where the data has one. */
  function downSection(f, sid) {
    var prog = progression(f, f.records[sid]), first = prog[0].r, top = prog[prog.length - 1].r, line = gaugeLine(f, sid), lim = isLimit(f), word = lim ? 'limit' : 'record';
    var goal = line && line.value > 0 ? line.value : null, reached = goal !== null && top[1] <= goal, end = goal !== null && !reached ? goal : top[1];
    function lg(v) { return Math.log10(v); }
    function at(v) { return (lg(first[1]) - lg(v)) / (lg(first[1]) - lg(end)); }
    var goalName = line && line.kind === 'limit' ? 'The limit' : 'The target';
    return '<div class="wrap block"><h2>How far the ' + word + ' has come down</h2>' +
      '<dl class="split">' + cell('', 'First ' + word + ' here · ' + esc(fmtDate(first[0])), val(f, first[1])) +
        cell('now', 'Current ' + word + ' · ' + esc(fmtDate(top[0])), val(f, top[1])) +
        cell('', 'Times lower than the first', fmt(first[1] / top[1]) + '×') +
        (goal !== null ? cell('goal', goalName + (line.by ? ' · by ' + esc(fmtDate(line.by)) : ''), val(f, goal)) : '') +
        (goal !== null && !reached ? cell('', 'Still to go', fmt(top[1] / goal) + '×') : '') + '</dl>' +
      stepRows(f, prog, at, goal === null ? null : at(goal), function (p, i) { return i ? fmt(prog[i - 1].r[1] / p.r[1]) + '× lower than the one before' : 'Where this series starts'; }) +
      '<p class="small">' + (unitText(f) ? 'Figures are in ' + esc(unitText(f)) + '. ' : '') +
        'One bar for each ' + word + ' in this series, oldest at the top. The bars are a log scale, so equal lengths are equal multiples: each starts at the first ' + word + ' here and runs as far as that ' + word + ' got' +
        (goal !== null && !reached ? ', and the full width is ' + goalName.toLowerCase() + ', marked in blue' : ', and the full width is the current ' + word + (goal !== null ? '; the blue mark is ' + goalName.toLowerCase() + ', which it has passed' : '')) + '. The orange bar is the current ' + word + '. ' +
        'The multiples (times lower' + (goal !== null && !reached ? ', still to go' : '') + ') are one figure on this page divided by another, worked out here and not figures from a source. Where the conditions differ from one ' + word + ' to the next, a multiple does not compare like with like. ' +
        (line && line.label ? goalName + ': ' + esc(line.label) + '. ' : '') +
        (hasShape(f, 'closing-bounds') ? 'The data holds upper limits only, so nothing is drawn closing in from below. ' : '') +
        (hasShape(f, 'exclusion-map') ? 'Each figure is the single value its source reports, under the conditions shown beside it; the data does not hold whole exclusion curves, so no map is drawn. ' : '') +
        (seriesIds(f, 'records').length > 1 ? 'This is the selected series only.' : '') + '</p></div>';
  }
  /* To-scale line-up: discs with diameters in proportion when the measure is a diameter, otherwise bars from zero. */
  function lineupSection(f, sid) {
    var prog = progression(f, f.records[sid]), first = prog[0].r, top = prog[prog.length - 1].r, n = prog.length, disc = discMode(f), c = palette(false), body, note;
    var u = unitText(f) ? ' ' + unitText(f) : '';
    if (disc) {
      var W = 880, gap = 20, cols = prog.map(function (p) {
        var name = shortName(p.r[2] || ''), v = val(f, p.r[1]) + u;
        return { p: p, name: name, v: v, lw: Math.max(name.length * 7.9, v.length * 9.4, 40) + 6 };
      });
      var s = (W - gap * (n - 1)) / cols.reduce(function (a, x) { return a + x.p.r[1]; }, 0), k, total = 0;
      function width() { return cols.reduce(function (a, x) { return a + Math.max(x.p.r[1] * s, x.lw); }, 0) + gap * (n - 1); }
      for (k = 0; k < 80 && (total = width()) > W; k += 1) s *= 0.97;
      var D2 = top[1] * s, H = D2 + 68, x0 = (W - total) / 2, o = '<path d="M0 ' + D2.toFixed(1) + ' H' + W + '" stroke="' + c.axis + '" stroke-width="1"/>' + FG;
      cols.forEach(function (x, i) {
        var w = Math.max(x.p.r[1] * s, x.lw), cx = x0 + w / 2, r = x.p.r[1] * s / 2, on = i === n - 1;
        o += '<circle cx="' + cx.toFixed(1) + '" cy="' + (D2 - r).toFixed(1) + '" r="' + r.toFixed(1) + '" fill="' + (on ? '#E4531A' : '#0F1317') + '"><title>' + esc(x.v + ' · ' + x.p.r[2] + ' · ' + fmtDate(x.p.r[0])) + '</title></circle>' +
          '<text x="' + cx.toFixed(1) + '" y="' + (D2 + 22).toFixed(1) + '" fill="' + c.strong + '" font-size="15" font-weight="600" text-anchor="middle">' + esc(x.v) + '</text>' +
          '<text x="' + cx.toFixed(1) + '" y="' + (D2 + 41).toFixed(1) + '" fill="' + c.text + '" font-size="13" text-anchor="middle">' + esc(x.name) + '</text>' +
          '<text x="' + cx.toFixed(1) + '" y="' + (D2 + 58).toFixed(1) + '" fill="' + c.text + '" font-size="13" text-anchor="middle">' + parseDate(x.p.r[0]).y + '</text>';
        x0 += w + gap;
      });
      body = '<div class="card">' + frame(o, W, H, 'The ' + n + ' records of this series as discs side by side, oldest on the left, each with its diameter drawn to the same scale. From ' + val(f, first[1]) + u + ' (' + parseDate(first[0]).y + ') to the current record, ' +
        val(f, top[1]) + u + ' (' + parseDate(top[0]).y + ').', creditLine(f), null, '-10 -12 ' + (W + 20) + ' ' + (H + 18)) + '</div>';
      note = 'Each disc is one record holder, oldest on the left, with its diameter drawn in proportion to the figure in the data; the orange disc is the current record. Only the diameter is to scale: the discs say nothing about the shape or make-up of the real thing. Full names, dates and conditions are in the history below.';
    } else {
      body = stepRows(f, prog, function (v) { return v / top[1]; }, null, null);
      note = 'One bar for each record in this series, oldest at the top. Every bar starts at zero and the full width is the current record, in orange, so the lengths are in true proportion. ' +
        'The bars compare the measure itself' + (u ? ' (' + esc(unitText(f)) + ')' : '') + '. The data has no field for physical size here, so the things themselves are not drawn to scale; any sizes the source gives are in the conditions beside each record.';
    }
    return '<div class="wrap block"><h2>Drawn to scale</h2>' +
      '<dl class="split">' + cell('', 'First record here · ' + esc(fmtDate(first[0])), val(f, first[1])) +
        cell('now', 'Current record · ' + esc(fmtDate(top[0])), val(f, top[1])) + '</dl>' + body +
      '<p class="small">' + (u ? 'Figures are in ' + esc(unitText(f)) + '. ' : '') + note +
        (f.dataStatus === 'draft' ? ' This is draft data, so records may be missing from the line-up.' : '') +
        (seriesIds(f, 'records').length > 1 ? ' This is the selected series only.' : '') + '</p></div>';
  }
  /* Claim scoreboard on a records frontier: one card per result, newest first, with where the claim stands. */
  var REC_STATUS = ['confirmed', 'peer_reviewed', 'claimed', 'retracted'];
  function recClaimSection(f) {
    var all = [], ids = seriesIds(f, 'records'), n = {}, order = REC_STATUS.slice();
    ids.forEach(function (id) { f.records[id].forEach(function (r) { all.push({ m: seriesMeta(f, id), r: r }); }); });
    all.sort(function (x, y) { return parseDate(y.r[0]).t - parseDate(x.r[0]).t; });
    all.forEach(function (x) { var s = x.r[4] || 'not stated'; n[s] = (n[s] || 0) + 1; if (order.indexOf(s) < 0) order.push(s); });
    order = order.filter(function (s) { return n[s]; });
    var newest = all.length > 1 && all[0].r[0] === all[1].r[0] ? null : all[0];
    var cards = all.map(function (x) {
      var r = x.r, on = x === newest;
      return '<li class="gcard' + (on ? ' new' : '') + (withdrawn(r) ? ' gone' : '') + '"><span class="gtop">' + mark(r[4], on ? '#E4531A' : '#0F1317', 14) +
        '<span>' + esc(STATUS[r[4]] || r[4] || 'Status not stated') + ' · ' + esc(fmtDate(r[0])) + (ids.length > 1 ? ' · ' + esc(x.m.label) : '') + '</span></span>' +
        '<strong>' + val(f, r[1]) + (unitText(f) ? ' ' + esc(unitText(f)) : '') + '</strong>' +
        (r[2] ? '<span class="sub by">' + esc(r[2]) + '</span>' : '') + (r[3] ? '<span class="sub">' + esc(r[3]) + '</span>' : '') +
        (r[7] ? '<span class="gnote">' + esc(r[7]) + '</span>' : '') + '<span class="sub">' + sourceLink(f, r[5]) + '</span></li>';
    }).join('');
    return '<div class="wrap block"><h2>Where each claim stands</h2>' +
      '<dl class="split">' + order.map(function (s) { return cell('', esc(STATUS[s] || s), fmt(n[s])); }).join('') + cell('', 'Results listed', fmt(all.length)) + '</dl>' +
      '<div class="ggs"><section class="gg"><ul class="gcards claims">' + cards + '</ul></section></div>' +
      '<p class="small gkey">' + order.map(function (s) { return statusHtml(s, '#0F1317'); }).join('') + (newest ? '<span class="status">' + mark(newest.r[4], '#E4531A') + 'Most recent</span>' : '') + '</p>' +
      '<p class="small">One card per result in the data, newest first' + (ids.length > 1 ? ', across all ' + ids.length + ' series' : '') + '. The mark shows where each claim stands: a ring is a claim by the people who made it, ' +
        'a half-filled ring has passed peer review, a solid mark has been confirmed independently, and a struck ring was retracted. A retracted result stays on the page but does not count as a record. ' +
        'The counts are counts of the results listed here, worked out on the page and not a figure from a source' + (f.dataStatus === 'draft' ? '; this is draft data, so the list may not be complete' : '') + '.</p></div>';
  }
  /* Precision funnel: every measurement on one value axis, a dot for the central value and a bar for the range the source gives. */
  function funnelSection(f) {
    var all = funnelRows(f), ids = seriesIds(f, 'observations'), c = palette(false), W = 880, vs = [], newest = all[0], tie = false, out = '', fg = '', y = 0, k;
    all.forEach(function (x) { vs.push(x.r[1]); if (ranged(x.r)) vs.push(x.r[2], x.r[3]); if (x.r[0] > newest.r[0]) newest = x; });
    all.forEach(function (x) { if (x !== newest && x.r[0] === newest.r[0]) tie = true; });
    if (tie) newest = null;
    var lo = Math.min.apply(null, vs), hi = Math.max.apply(null, vs), step = niceStep((hi - lo) || 1, 6);
    var a = Math.floor(lo / step) * step, b = Math.ceil(hi / step) * step; if (a === b) b = a + step;
    function X(v) { return (v - a) / (b - a) * W; }
    var heads = '';
    ids.forEach(function (id) {
      var rows = f.observations[id];
      y += 30;
      heads += '<text x="0" y="' + y + '" fill="' + c.strong + '" stroke="' + c.bg + '" stroke-width="5" paint-order="stroke" font-family="Space Grotesk, Helvetica Neue, Arial, sans-serif" font-size="16" font-weight="600">' + esc(seriesMeta(f, id).label) + '</text>';
      y += 6;
      rows.forEach(function (r, i) {
        var latest = i === rows.length - 1, on = !!newest && newest.r === r, col = on ? '#E4531A' : latest ? c.line : c.text, sw = latest ? 2.5 : 1.5, has = ranged(r);
        y += 24;
        var cy = y - 8, x = X(r[1]), x0 = has ? X(r[2]) : x, x1 = has ? X(r[3]) : x;
        var text = fmt(r[1]) + (has ? '' : ' · no range in the data'), right = x1 + 12 + text.length * 7.9 <= W;
        heads += '<text x="-12" y="' + (cy + 4.5) + '" fill="' + (latest ? c.strong : c.text) + '" font-size="13" text-anchor="end">' + esc(fmtDate(r[0])) + '</text>';
        fg += '<g><title>' + esc(seriesMeta(f, id).label + ' · ' + fmtDate(r[0]) + ' · ' + fmt(r[1]) + (has ? ' (' + fmt(r[2]) + ' to ' + fmt(r[3]) + ')' : '')) + '</title>' +
          (has ? '<path d="M' + x0.toFixed(1) + ' ' + cy + ' H' + x1.toFixed(1) + ' M' + x0.toFixed(1) + ' ' + (cy - 5) + ' v10 M' + x1.toFixed(1) + ' ' + (cy - 5) + ' v10" fill="none" stroke="' + col + '" stroke-width="' + sw + '"/>' +
            '<circle cx="' + x.toFixed(1) + '" cy="' + cy + '" r="5" fill="' + col + '" stroke="' + c.bg + '" stroke-width="1.5"/>'
            : '<circle cx="' + x.toFixed(1) + '" cy="' + cy + '" r="4.25" fill="' + c.bg + '" stroke="' + col + '" stroke-width="1.5"/>') +
          '<text x="' + (right ? x1 + 12 : x0 - 12).toFixed(1) + '" y="' + (cy + 4.5) + '" fill="' + (on ? '#B03A08' : latest ? c.strong : c.text) + '" stroke="' + c.bg + '" stroke-width="4" paint-order="stroke" font-size="13"' +
            (latest ? ' font-weight="500"' : '') + ' text-anchor="' + (right ? 'start' : 'end') + '">' + esc(text) + '</text></g>';
      });
      y += 10;
    });
    var H = y + 6, grid = '', nT = Math.round((b - a) / step);
    for (k = 0; k <= nT; k += 1) {
      var gx = X(a + k * step).toFixed(1);
      grid += '<path d="M' + gx + ' 0 V' + (H + 6) + '" stroke="' + c.grid + '" stroke-width="1"/>' +
        '<text x="' + gx + '" y="' + (H + 26) + '" fill="' + c.text + '" font-size="13" text-anchor="middle">' + esc(fmt(a + k * step) + suffix(f)) + '</text>';
    }
    out = grid + '<path d="M0 ' + H + ' H' + W + '" stroke="' + c.axis + '" stroke-width="1"/>' + heads + FG + fg;
    var nr = newest && newest.r, without = all.filter(function (x) { return !ranged(x.r); }).length;
    return '<div class="wrap block"><h2>The measurements side by side</h2>' +
      '<dl class="split">' + (nr ? cell('now', 'Newest measurement · ' + esc(fmtDate(nr[0])) + ' · ' + esc(seriesMeta(f, newest.id).label), val(f, nr[1])) +
          (ranged(nr) ? cell('words', 'The range its source gives', fmt(nr[2]) + ' to ' + fmt(nr[3])) : '') : '') +
        cell('', 'Methods', fmt(ids.length)) + cell('', 'Measurements', fmt(all.length)) + '</dl>' +
      '<div class="card">' + frame(out, W, H, all.length + ' measurements by ' + ids.length + ' methods on one axis from ' + fmt(a) + ' to ' + fmt(b) + (unitText(f) ? ' ' + unitText(f) : '') +
        ', each drawn as its central value with the range its source gives.' + (nr ? ' Newest: ' + val(f, nr[1]) + ', ' + seriesMeta(f, newest.id).label + ', ' + fmtDate(nr[0]) + '.' : ''),
        creditLine(f), null, '-112 -8 ' + (W + 132) + ' ' + (H + 44)) + '</div>' +
      '<p class="small">Each row is one measurement, grouped by method with the oldest first. The dot is the central value and the bar is the range the data records for it, as its source gives it' +
        (unitText(f) ? ', in ' + esc(unitText(f)) : '') + '. A shorter bar is a more precise measurement. Where the bars of two measurements do not overlap, the two differ by more than the ranges they state. ' +
        'The heavier row in each group is that method’s latest' + (nr ? ', and the orange row is the newest of all' : '') + '.' +
        (without ? ' ' + without + ' of the ' + all.length + ' measurements have no range in the data and are drawn as an open ring; their sources may still state one.' : '') +
        ' The counts of methods and measurements are counts of the entries listed here, worked out on the page.</p></div>';
  }
  /* Coverage meter: the latest figure as a filled share of the whole, with what is left. */
  function coverageSection(f, sid) {
    var rows = f.observations[sid], first = rows[0], last = rows[rows.length - 1], t = f.metric.target, ticks = [];
    if (rows.length > 1) ticks.push({ at: first[1] / 100 });
    if (t && t.value < 100) ticks.push({ at: t.value / 100, blue: true });
    return '<div class="wrap block"><h2>How much of the whole</h2>' +
      scaleBar(last[1] / 100, 'A bar standing for the whole, 100%. ' + val(f, last[1]) + ' of it is filled, as of ' + fmtDate(last[0]) + '.', ticks, creditLine(f)) +
      '<dl class="split">' + cell('now', 'Latest figure · ' + esc(fmtDate(last[0])), val(f, last[1])) +
        cell('', 'The rest of the whole', val(f, 100 - last[1])) +
        (rows.length > 1 ? cell('', 'First figure here · ' + esc(fmtDate(first[0])), val(f, first[1])) : '') +
        (t ? cell('goal', 'Target' + (t.by ? ' · by ' + esc(fmtDate(t.by)) : ''), val(f, t.value)) : '') + '</dl>' +
      '<p class="small">The bar is the whole, 100%. The dark part is the latest figure' + (rows.length > 1 ? ', and the black tick is the first figure in this series' : '') +
        (t && t.value < 100 ? '; the blue tick is the target' : '') + '. The rest is 100% minus the latest figure, worked out here and not a figure from the source.' +
        (t ? ' Target: ' + esc(t.label) + '.' : '') + '</p></div>';
  }
  /* Race to zero: how far the latest figure still is from zero, next to the highest figure in the series. */
  function zeroSection(f, sid) {
    var rows = f.observations[sid], last = rows[rows.length - 1], peak = peakRow(rows), frac = peak[1] > 0 ? last[1] / peak[1] : 0;
    return '<div class="wrap block"><h2>Distance to zero</h2>' +
      (peak[1] > 0 ? scaleBar(frac, 'A bar as long as the highest figure in this series, ' + val(f, peak[1]) + ' in ' + fmtDate(peak[0]) + '. The filled part is the latest figure, ' + val(f, last[1]) + ' in ' + fmtDate(last[0]) + '.', null, creditLine(f)) : '') +
      '<dl class="split">' + cell('', 'Highest in this series · ' + esc(fmtDate(peak[0])), val(f, peak[1])) +
        cell('now', 'Latest figure · ' + esc(fmtDate(last[0])), val(f, last[1])) +
        cell('goal', 'The line to reach', '0') + '</dl>' +
      '<p class="small">' + (unitText(f) ? 'Figures are in ' + esc(unitText(f)) + '. ' : '') + 'The bar is as long as the highest figure in this series, and the dark part is the latest figure drawn to the same scale' +
        (peak[1] > 0 && frac < 0.004 ? ', which is too small to see at this size' : '') + '.</p></div>';
  }
  /* Cost curve: how many times cheaper the latest figure is than the first, and when each halving of the first figure was reached. */
  function costSection(f, sid) {
    var rows = costRows(f, sid), pm = pointsMode(f), first = rows[0], last = rows[rows.length - 1], hs = halvings(rows), c = palette(false), W = 880, H = 62, out = '', fg = '';
    var t0 = Math.floor(parseDate(first.d).t), t1 = Math.ceil(parseDate(last.d).t + 0.1), newest = hs[hs.length - 1];
    function X(t) { return (t - t0) / (t1 - t0) * W; }
    function named(r) { return (r.who ? esc(r.who) + ' · ' : '') + esc(fmtDate(r.d)); }
    var ribbon = '', table = '';
    if (hs.length) {
      out += '<path d="M0 ' + H + ' H' + W + '" stroke="' + c.axis + '" stroke-width="1"/>';
      timeTicks(t0, t1).forEach(function (y) {
        out += '<path d="M' + X(y).toFixed(1) + ' ' + H + ' V' + (H + 6) + '" stroke="' + c.axis + '" stroke-width="1"/>' +
          '<text x="' + X(y).toFixed(1) + '" y="' + (H + 26) + '" fill="' + c.text + '" font-size="13" text-anchor="middle">' + y + '</text>';
      });
      var from = X(parseDate(first.d).t);
      hs.forEach(function (h, i) {
        var to = X(parseDate(h.r.d).t), on = h === newest, w = Math.max(1.5, to - from - 1);
        fg += '<rect x="' + from.toFixed(1) + '" y="16" width="' + w.toFixed(1) + '" height="' + (H - 16) + '" fill="' + (on ? '#E4531A' : i % 2 ? '#4F5760' : '#0F1317') + '">' +
          '<title>' + esc('Halving ' + h.k + ': at or below ' + val(f, h.level) + ' from ' + fmtDate(h.r.d)) + '</title></rect>';
        if (String(h.k).length * 7.9 + 14 <= w) fg += '<text x="' + (from + 7).toFixed(1) + '" y="' + (16 + (H - 16) / 2 + 4.5).toFixed(1) + '" fill="' + (on ? '#0F1317' : '#F4F5F1') + '" font-size="13" font-weight="500" pointer-events="none">' + h.k + '</text>';
        fg += '<path d="M' + to.toFixed(1) + ' 4 V13" stroke="' + (on ? '#E4531A' : c.axis) + '" stroke-width="1.5"/>';
        from = to;
      });
      var end = X(parseDate(last.d).t);
      if (end - from > 1.5) fg += '<rect x="' + from.toFixed(1) + '" y="16" width="' + (end - from).toFixed(1) + '" height="' + (H - 16) + '" fill="#E3E5DF"><title>' + esc('Since halving ' + newest.k + ', up to ' + fmtDate(last.d)) + '</title></rect>';
      ribbon = '<div class="card">' + frame(out + FG + fg, W, H, 'A ribbon from ' + parseDate(first.d).y + ' to ' + parseDate(last.d).y + ' with one block per halving of the first figure, ' + val(f, first.v) + '. ' + hs.length +
        (hs.length === 1 ? ' halving' : ' halvings') + ' reached; the latest was reached ' + fmtDate(newest.r.d) + '.', creditLine(f), [t0, t1], '-10 -24 ' + (W + 20) + ' ' + (H + 58)) + '</div>';
      table = '<div class="tbl"><table class="halvings"><thead><tr><th scope="col">Halving</th><th scope="col">First figure halved this many times</th><th scope="col">First at or below it</th>' +
        (pm ? '<th scope="col">Which</th>' : '') + '<th scope="col">Figure then</th></tr></thead><tbody>' +
        hs.slice().reverse().map(function (h) {
          return '<tr class="' + (h === newest ? 'now' : '') + '"><td><span class="snum' + (h === newest ? ' at' : '') + '">' + h.k + '</span></td><td class="g">' + val(f, h.level) + '</td>' +
            '<td class="date">' + esc(fmtDate(h.r.d)) + '</td>' + (pm ? '<td>' + esc(h.r.who) + '</td>' : '') + '<td class="v">' + val(f, h.r.v) + '</td></tr>';
        }).join('') + '</tbody></table></div>';
    }
    return '<div class="wrap block"><h2>How far the cost has fallen</h2>' +
      '<dl class="split">' + cell('', (pm ? 'First entry · ' : 'First figure here · ') + named(first), val(f, first.v)) +
        cell('now', (pm ? 'Cheapest so far · ' : 'Latest figure · ') + named(last), val(f, last.v)) +
        cell('', 'Times cheaper', fmt(first.v / last.v) + '×') +
        cell('', 'Halvings reached', fmt(hs.length)) + '</dl>' + ribbon +
      '<p class="small">' + (unitText(f) ? 'Figures are in ' + esc(unitText(f)) + '. ' : '') +
        (pm ? 'Each entry here is a different one, so the curve is the cheapest entry so far, taken in date order. ' : '') +
        'Times cheaper is the first figure divided by the ' + (pm ? 'cheapest' : 'latest') + ', and a halving is counted each time a figure is at or below half the level before it, starting from the first figure. ' +
        'Both are worked out here from the figures on this page and are not figures from the source. ' +
        (hs.length ? 'Each block of the ribbon is the time one halving took: a narrow block is a fast halving. The orange block is the most recent one' +
            (parseDate(last.d).t > parseDate(newest.r.d).t ? ', and the pale stretch is the time since' : '') + '. A cost that later rose again keeps the halvings it had already reached.'
          : 'The cost has not yet fallen to half the first figure, so there is no halving to draw.') + '</p>' + table + '</div>';
  }
  /* Scale ladder: the powers of ten a series has passed, drawn on a log bar from its first figure to the next power of ten. */
  function ladderSection(f, sid) {
    var rows = ladderRows(f, sid), first = rows[0], top = rows[rows.length - 1], rg = rungs(f, rows), down = f.metric.direction === 'lower';
    var rec = hasRecords(f), word = rec ? 'record' : 'figure', u = unitText(f) ? ' ' + esc(unitText(f)) : '';
    function lg(v) { return Math.log10(v); }
    function at(v) { return (lg(v) - lg(first.v)) / (lg(pow10(rg.next)) - lg(first.v)); }
    /* One notation per ladder: plain numbers while every rung is short enough to read, powers of ten otherwise. */
    var plain = rg.passed.concat([{ e: rg.next }]).every(function (x) { return x.e >= -3 && x.e <= 4; });
    var ticks = rg.passed.map(function (x) { return { at: at(x.p) }; }), nextLabel = pow10Label(rg.next, plain) + suffix(f);
    var table = rg.passed.length ? '<div class="tbl"><table class="ladder"><thead><tr><th scope="col">Power of ten</th><th scope="col">First ' + (down ? 'at or below' : 'reached') + '</th>' +
      (rec ? '<th scope="col">By</th>' : '') + '<th scope="col">The ' + word + ' that did it</th></tr></thead><tbody>' +
      '<tr class="next"><td class="v dim">' + nextLabel + '</td><td class="date">Not yet</td>' + (rec ? '<td></td>' : '') + '<td></td></tr>' +
      rg.passed.slice().reverse().map(function (x) {
        return '<tr class="' + (x.r === top ? 'now' : '') + '"><td class="v">' + pow10Label(x.e, plain) + suffix(f) + '</td><td class="date">' + esc(fmtDate(x.r.d)) + '</td>' +
          (rec ? '<td>' + esc(x.r.who) + '</td>' : '') + '<td class="g">' + val(f, x.r.v) + '</td></tr>';
      }).join('') + '</tbody></table></div>' : '';
    return '<div class="wrap block"><h2>The ladder of powers of ten</h2>' +
      scaleBar(at(top.v), 'A bar on a log scale from the first ' + word + ' in this series, ' + val(f, first.v) + ', to the next power of ten, ' + nextLabel + '. The filled part is the ' +
        (rec ? 'current record' : 'latest figure') + ', ' + val(f, top.v) + ', from ' + fmtDate(top.d) + '. ' + rg.passed.length + (rg.passed.length === 1 ? ' power' : ' powers') + ' of ten passed on the way.', ticks, creditLine(f)) +
      '<dl class="split">' + cell('now', (rec ? 'Current record · ' : 'Latest figure · ') + esc(fmtDate(top.d)), val(f, top.v)) +
        cell('', 'Powers of ten passed', fmt(rg.passed.length)) +
        cell('', 'First ' + word + ' here · ' + esc(fmtDate(first.d)), val(f, first.v)) +
        cell('', 'Next power of ten', nextLabel) + '</dl>' +
      '<p class="small">' + (u ? 'Figures are in' + u + '. ' : '') + 'The bar is a log scale, so equal lengths are equal multiples. It runs from the first ' + word + ' in this series to the next power of ten ' +
        (down ? 'below' : 'above') + ' the ' + (rec ? 'current record' : 'latest figure') + '; the dark part is how far the series has got' +
        (ticks.length ? ' and each black tick is a power of ten it passed on the way' : '') + '. The powers of ten are the gridlines of the scale, not targets set by anyone, ' +
        'and the count of them is worked out here from the ' + word + 's on this page.' + (seriesIds(f, block(f)).length > 1 ? ' This is the selected series only.' : '') + '</p>' + table + '</div>';
  }
  function obsSections(f, sid) {
    var pm = pointsMode(f), meta = seriesMeta(f, sid), rows, head, body, cov = coverageMode(f), zero = zeroMode(f, sid), cost = costMode(f, sid);
    var log = (zero ? zeroScale(f.observations[sid]) : f.metric.scale) === 'log';
    var note = pm ? 'Each point is one entry, placed at its date. Hover a point for its name.'
      : cov ? 'The shaded area under the line is the share reached, on an axis that runs from nothing to the whole. The dashed blue line is the whole.'
      : zero ? 'The blue line at the bottom is zero. The dotted orange line is the distance still to go from the latest figure.'
      : 'The shaded band, where shown, is the range the source gives around its central figure.';
    if (!pm && seriesIds(f, 'observations').length > 1) note += ' Thin lines are the other series, where they fit on the same axis.';
    if (zero && log) note += ' The vertical axis is a log scale: each gridline is ten times the one below it. A log scale has no zero, so zero is drawn as a line of its own under the break in the axis.';
    else if (log && hasShape(f, 'cost-curve') && f.metric.direction === 'lower') note += ' The vertical axis is a log scale: each gridline is a tenth of the one above it. On this scale a cost that falls by the same percentage every year is a straight line, and the cheap recent years are not squashed flat against the bottom by the expensive early ones.';
    else if (log) note += ' The vertical axis is a log scale.';
    var out = (cov ? coverageSection(f, sid) : zero ? zeroSection(f, sid) : cost ? costSection(f, sid) : funnelMode(f) ? funnelSection(f) : '') +
      '<div class="wrap block"><h2>' + esc(pm ? f.metric.name : seriesName(meta)) + (cov || zero ? ' over time' : '') + '</h2><div class="card">' + obsChart(f, sid, false) + '</div>' +
      '<p class="small">' + note + '</p></div>';
    if (ladderMode(f, sid)) out += ladderSection(f, sid);
    if (pm) {
      rows = []; seriesIds(f, 'observations').forEach(function (id) { rows.push({ m: seriesMeta(f, id), r: f.observations[id][0] }); });
      rows.sort(function (a, b) { return a.r[0] < b.r[0] ? 1 : -1; });
      head = '<th scope="col">Date</th><th scope="col">Name</th><th scope="col">Value</th><th scope="col">Note</th><th scope="col">Source</th>';
      body = rows.map(function (x) { return '<tr><td class="date">' + esc(fmtDate(x.r[0])) + '</td><td>' + esc(x.m.label) + (x.m.group ? '<div class="sub">' + esc(x.m.group) + '</div>' : '') + '</td><td class="v">' + val(f, x.r[1]) + '</td><td class="cond">' + esc(x.r[5]) + '</td><td>' + sourceLink(f, x.r[4]) + '</td></tr>'; }).join('');
    } else {
      rows = f.observations[sid];
      var ranged = rows.some(function (r) { return r[2] !== null && r[3] !== null; });
      head = '<th scope="col">Date</th><th scope="col">Value</th>' + (ranged ? '<th scope="col">Range</th>' : '') + '<th scope="col">Change</th><th scope="col">Note</th><th scope="col">Source</th>';
      body = rows.map(function (r, i) {
        var ch = i ? r[1] - rows[i - 1][1] : null;
        return '<tr class="' + (i === rows.length - 1 ? 'now' : '') + '"><td class="date">' + esc(fmtDate(r[0])) + '</td><td class="v">' + val(f, r[1]) + '</td>' +
          (ranged ? '<td class="g">' + (r[2] !== null && r[3] !== null ? fmt(r[2]) + ' to ' + fmt(r[3]) : '') + '</td>' : '') +
          '<td class="g">' + (ch === null ? '' : (ch > 0 ? '+' : '') + fmt(ch)) + '</td><td class="cond">' + esc(r[5]) + '</td><td>' + sourceLink(f, r[4]) + '</td></tr>';
      }).reverse().join('');
    }
    return out + '<div class="wrap block"><h2>' + (pm ? 'Every entry' : 'Figures: ' + esc(meta.label)) + '</h2><div class="tbl"><table><thead><tr>' + head + '</tr></thead><tbody>' + body + '</tbody></table></div></div>';
  }
  function stagesSection(f) {
    if (!f.candidates.length) return '';
    var n = f.stages.length;
    return '<div class="wrap block"><h2>How far each one has got</h2><div class="tbl"><table class="stages"><thead><tr><th scope="col">Name</th><th scope="col">Stage reached</th><th scope="col">Key result</th></tr></thead><tbody>' +
      f.candidates.slice().sort(function (a, b) { return f.stages.indexOf(b.stage) - f.stages.indexOf(a.stage); }).map(function (c) {
        var at = f.stages.indexOf(c.stage);
        var steps = f.stages.map(function (s, i) { return '<i class="' + (i < at ? 'past' : i === at ? 'at' : '') + '" title="' + esc(s) + '"></i>'; }).join('');
        return '<tr><td><strong>' + link(c.url, esc(c.name)) + '</strong><div class="sub">' + esc([c.kind, c.developer].filter(Boolean).join(' · ')) + '</div></td>' +
          '<td class="stagecell"><div class="steps" role="img" aria-label="Stage ' + (at + 1) + ' of ' + n + ': ' + esc(c.stage) + '">' + steps + '</div><div class="stagename">' + esc(c.stage) + (at >= 0 ? ' <span class="soft">' + (at + 1) + ' of ' + n + '</span>' : '') + '</div></td>' +
          '<td class="cond wide">' + esc(c.key) + '</td></tr>';
      }).join('') + '</tbody></table></div><p class="small">Stages, in order: ' + esc(f.stages.join(', ')) + '. Results from different trials or machines are not directly comparable.</p></div>';
  }
  /* Stage timeline: one track per candidate with a numbered mark at the date each stage was reached. */
  function cutName(s) { var t = s.split(' (')[0]; return t.length > 58 ? t.slice(0, 56) + '…' : t; }
  function stageDatesSection(f) {
    if (!stageDatesMode(f)) return '';
    var all = stageDates(f), c = palette(false), W = 880, RH = 78, tN = nowT(), out = '', fg = '', n = f.stages.length;
    var cands = f.candidates.filter(function (x) { return all.some(function (d) { return d.c === x; }); })
      .sort(function (a, b) { return f.stages.indexOf(b.stage) - f.stages.indexOf(a.stage); });
    var none = f.candidates.filter(function (x) { return cands.indexOf(x) < 0; });
    var t0 = Math.floor(Math.min.apply(null, all.map(function (d) { return parseDate(d.h.date).t; }))), t1 = Math.ceil(tN + 0.1), H = cands.length * RH;
    function X(t) { return (t - t0) / (t1 - t0) * W; }
    out += '<path d="M0 ' + H + ' H' + W + '" stroke="' + c.axis + '" stroke-width="1"/>';
    timeTicks(t0, t1).forEach(function (y) {
      out += '<path d="M' + X(y).toFixed(1) + ' 0 V' + (H + 6) + '" stroke="' + c.grid + '" stroke-width="1"/>' +
        '<text x="' + X(y).toFixed(1) + '" y="' + (H + 26) + '" fill="' + c.text + '" font-size="13" text-anchor="middle">' + y + '</text>';
    });
    cands.forEach(function (x, k) {
      var y = k * RH + 40, ds = all.filter(function (d) { return d.c === x; }).sort(function (a, b) { return parseDate(a.h.date).t - parseDate(b.h.date).t; });
      var lastX = null, level = 0, xs = ds.map(function (d) { return X(parseDate(d.h.date).t); });
      out += '<text x="0" y="' + (k * RH + 17) + '" fill="' + c.strong + '" stroke="' + c.bg + '" stroke-width="4" paint-order="stroke" font-size="13" font-weight="500">' + esc(cutName(x.name)) + '</text>';
      fg += '<path d="M' + xs[0].toFixed(1) + ' ' + y + ' H' + X(tN).toFixed(1) + '" stroke="' + c.faint + '" stroke-width="1.5"/>' +
        '<path d="M' + xs[0].toFixed(1) + ' ' + y + ' H' + xs[xs.length - 1].toFixed(1) + '" stroke="' + c.line + '" stroke-width="2.5"/>';
      ds.forEach(function (d, j) {
        level = lastX !== null && xs[j] - lastX < 23 ? 1 - level : 0; lastX = xs[j];
        var on = d.h.stage === x.stage, cy = y + level * 21;
        fg += '<g><title>' + esc(x.name + ': ' + d.h.stage + ', ' + fmtDate(d.h.date)) + '</title>' +
          '<circle cx="' + xs[j].toFixed(1) + '" cy="' + cy + '" r="10" fill="' + (on ? '#E4531A' : c.line) + '" stroke="' + c.bg + '" stroke-width="1.5"/>' +
          '<text x="' + xs[j].toFixed(1) + '" y="' + (cy + 4.5) + '" fill="' + (on ? '#0F1317' : '#F4F5F1') + '" font-size="12" font-weight="500" text-anchor="middle">' + (d.i >= 0 ? d.i + 1 : '?') + '</text></g>';
      });
    });
    var rows = all.slice().sort(function (a, b) { return parseDate(b.h.date).t - parseDate(a.h.date).t; }).map(function (d) {
      var on = d.h.stage === d.c.stage;
      return '<tr class="' + (on ? 'now' : '') + '"><td class="date">' + esc(fmtDate(d.h.date)) + '</td><td><strong>' + esc(d.c.name) + '</strong></td>' +
        '<td>' + (d.i >= 0 ? '<span class="snum' + (on ? ' at' : '') + '">' + (d.i + 1) + '</span>' : '') + esc(d.h.stage) + '</td><td class="cond wide">' + esc(d.h.note) + '</td>' +
        '<td>' + (d.h.url ? link(d.h.url, 'Source') : sourceLink(f, d.h.source)) + '</td></tr>';
    }).join('');
    return '<div class="wrap block"><h2>When each stage was reached</h2><div class="card">' +
      frame(out + FG + fg, W, H, 'One track per candidate from ' + t0 + ' to now, with a numbered mark at the date each stage was reached. ' +
        cands.map(function (x) { return x.name + ': now at ' + x.stage + '.'; }).join(' '), creditLine(f), [t0, t1], '-24 -8 ' + (W + 48) + ' ' + (H + 44)) + '</div>' +
      '<ol class="stagekey">' + f.stages.map(function (s, i) { return '<li><span class="snum">' + (i + 1) + '</span>' + esc(s) + '</li>'; }).join('') + '</ol>' +
      '<p class="small">Each numbered mark is the date a candidate reached that stage, for the stages the data has a date for. The orange mark is the stage it is at now. ' +
        'A stage with no mark has no date in the data, which is not the same as a stage that was skipped. Marks that would overlap are set one below the other.' +
        (none.length ? ' No dated stages yet for: ' + esc(none.map(function (x) { return x.name; }).join('; ')) + '.' : '') + '</p>' +
      '<div class="tbl"><table class="stagedates"><thead><tr><th scope="col">Date</th><th scope="col">Name</th><th scope="col">Stage reached</th><th scope="col">Note</th><th scope="col">Source</th></tr></thead><tbody>' + rows + '</tbody></table></div></div>';
  }
  /* Countdown grid: the whole list at once, one cell per entry, drawn by status. Short lists get a labelled card per entry. */
  function tallyText(list) { return itemCounts(list).map(function (x) { return x.n + ' ' + (ITEM_STATUS[x.s] || x.s).toLowerCase(); }).join(' · '); }
  function gridSection(f) {
    if (!gridMode(f)) return '';
    var claim = claimMode(f), cards = claim || f.items.length <= 24, newest = newestItem(f), counts = itemCounts(f.items), groups = [], by = {};
    f.items.forEach(function (i) { var g = claim ? '' : i[2] || ''; if (!by[g]) { by[g] = []; groups.push(g); } by[g].push(i); });
    var mixed = counts.length > 1, split = '';
    if (mixed || counts[0].s !== 'done') counts.forEach(function (x) { split += cell('', esc(ITEM_STATUS[x.s] || x.s), fmt(x.n)); });
    split += cell('', 'On the list', fmt(f.items.length));
    if (newest) split += cell('now words', 'Most recent · ' + esc(fmtDate(newest[5])), esc(newest[1]));
    function when(i) { return (i[3] !== 'done' ? esc(ITEM_STATUS[i[3]] || i[3]) + (i[5] ? ' · ' : '') : '') + esc(fmtDate(i[5])); }
    function one(i) {
      var on = i === newest;
      if (!cards) return '<li class="gc ' + esc(i[3]) + (on ? ' new' : '') + '" title="' + esc(i[1] + (i[4] ? ' · ' + i[4] : '') + (i[5] ? ' · ' + fmtDate(i[5]) : '')) + '"><span class="vh">' + esc(i[1] + ': ' + (ITEM_STATUS[i[3]] || i[3])) + '</span></li>';
      return '<li class="gcard' + (on ? ' new' : '') + '"><span class="gtop">' + itemMark(i[3], on ? '#E4531A' : '#0F1317', 14) + '<span>' + when(i) + (claim && i[2] ? ' · ' + esc(i[2]) : '') + '</span></span>' +
        '<strong>' + link(i[6], esc(i[1])) + '</strong>' + (i[4] ? '<span class="sub">' + esc(i[4]) + '</span>' : '') +
        (i[8] ? '<span class="sub by">' + esc(i[8]) + '</span>' : '') + (claim && i[9] ? '<span class="gnote">' + esc(i[9]) + '</span>' : '') + '</li>';
    }
    var body = groups.map(function (g) {
      return '<section class="gg">' + (g ? '<h3><span>' + esc(g || 'Not grouped') + '</span><span class="eyebrow">' + esc(tallyText(by[g])) + '</span></h3>' : '') +
        '<ul class="' + (cards ? 'gcards' + (claim ? ' claims' : '') : 'gcells') + '">' + by[g].map(one).join('') + '</ul></section>';
    }).join('');
    var key = counts.map(function (x) { return '<span class="status">' + itemMark(x.s, '#0F1317') + esc(ITEM_STATUS[x.s] || x.s) + '</span>'; }).join('');
    return '<div class="wrap block"><h2>' + (claim ? 'The claims and where they stand' : 'The list at a glance') + '</h2>' +
      '<dl class="split">' + split + '</dl><div class="ggs">' + body + '</div>' +
      '<p class="small gkey">' + key + (newest ? '<span class="status">' + itemMark(newest[3], '#E4531A') + 'Most recent</span>' : '') + '</p>' +
      '<p class="small">' + (cards ? 'One card per entry, in the order the data lists them' : 'One square per entry, in the order the data lists them; hover a square for its name') +
        (groups.length > 1 ? ', grouped as the data groups them' : '') + '. The counts are counts of the entries listed here, worked out on the page and not a figure from a source' +
        (f.dataStatus === 'draft' ? '; this is draft data, so the list may not be complete' : '') + '. The wording under each ' + (cards ? 'name' : 'entry in the full list below') + ' is the source’s own.</p></div>';
  }
  /* The dated entries of a list on a time axis: one mark per entry, stacked where dates fall close together. */
  function itemTimeSection(f) {
    if (!itemTimeMode(f)) return '';
    var c = palette(false), W = 880, tN = nowT(), newest = newestItem(f), out = '', fg = '', stack = {}, peak = 1;
    var list = datedItems(f).slice().sort(function (a, b) { return parseDate(a[5]).t - parseDate(b[5]).t; });
    var t0 = Math.floor(parseDate(list[0][5]).t), t1 = Math.ceil(tN + 0.1), P = 13;
    function X(t) { return (t - t0) / (t1 - t0) * W; }
    var spots = list.map(function (i) { var b = Math.round(X(parseDate(i[5]).t) / P); stack[b] = (stack[b] || 0) + 1; peak = Math.max(peak, stack[b]); return { i: i, x: b * P, k: stack[b] - 1 }; });
    var H = Math.max(56, peak * P + 14);
    out += '<path d="M0 ' + H + ' H' + W + '" stroke="' + c.axis + '" stroke-width="1"/>';
    timeTicks(t0, t1).forEach(function (y) {
      out += '<path d="M' + X(y).toFixed(1) + ' ' + H + ' V' + (H + 6) + '" stroke="' + c.axis + '" stroke-width="1"/>' +
        '<text x="' + X(y).toFixed(1) + '" y="' + (H + 26) + '" fill="' + c.text + '" font-size="13" text-anchor="middle">' + y + '</text>';
    });
    spots.forEach(function (s) {
      var on = s.i === newest, col = on ? '#E4531A' : c.line, cy = H - 9 - s.k * P, st = s.i[3], x = s.x.toFixed(1);
      fg += '<g><title>' + esc(s.i[1] + ' · ' + fmtDate(s.i[5])) + '</title>' +
        (st === 'done' ? '<circle cx="' + x + '" cy="' + cy + '" r="5" fill="' + col + '"/>'
          : '<circle cx="' + x + '" cy="' + cy + '" r="4.25" fill="' + c.bg + '" stroke="' + col + '" stroke-width="1.5"/>' +
            (st === 'partial' ? '<path d="M' + x + ' ' + (cy - 4.25) + ' a4.25 4.25 0 0 1 0 8.5 Z" fill="' + col + '"/>' : '') +
            (st === 'disputed' ? '<path d="M' + (s.x - 3.5) + ' ' + (cy + 3.5) + ' l7 -7" stroke="' + col + '" stroke-width="1.5"/>' : '')) + '</g>';
    });
    var first = list[0], last = list[list.length - 1], undated = f.items.length - list.length;
    return '<div class="wrap block"><h2>The list over time</h2><div class="card">' +
      frame(out + FG + fg, W, H, 'One mark for each of the ' + list.length + ' dated entries on the list, placed by date from ' + parseDate(first[5]).y + ' to ' + parseDate(last[5]).y + '. Earliest: ' + first[1] + ', ' + fmtDate(first[5]) + '. Latest: ' + last[1] + ', ' + fmtDate(last[5]) + '.',
        creditLine(f), [t0, t1], '-24 -8 ' + (W + 48) + ' ' + (H + 44)) + '</div>' +
      '<p class="small">Each mark is one entry on the list, placed at the date the data gives for it' + (newest ? '; the orange mark is the most recent' : '') + '. Marks stack where dates fall close together. ' +
        'An entry dated only to a year sits in the middle of that year.' + (undated ? ' ' + undated + ' of the ' + f.items.length + ' entries have no date in the data and are not drawn.' : '') + '</p></div>';
  }
  function itemsState(f) { return itemState[f.id] || (itemState[f.id] = { q: '', status: 'all', group: 'all', shown: 120 }); }
  function itemsList(f) {
    var st = itemsState(f), q = st.q.trim().toLowerCase();
    var rows = f.items.filter(function (i) {
      return (st.status === 'all' || i[3] === st.status) && (st.group === 'all' || i[2] === st.group) &&
        (!q || (i[1] + ' ' + i[2] + ' ' + i[4]).toLowerCase().indexOf(q) >= 0);
    });
    var hasAi = f.items.some(function (i) { return i[7] && i[7] !== 'unknown'; });
    var html = rows.slice(0, st.shown).map(function (i) {
      return '<li class="it ' + esc(i[3]) + '"><span class="dot" aria-hidden="true"></span><span class="il">' + link(i[6], esc(i[1])) + (i[2] ? '<span class="sub">' + esc(i[2]) + '</span>' : '') + '</span>' +
        '<span class="is">' + esc(i[4] || ITEM_STATUS[i[3]] || i[3]) + (i[5] ? ' · ' + esc(fmtDate(i[5])) : '') + '</span>' +
        (hasAi ? '<span class="ia">' + (i[7] && i[7] !== 'unknown' && i[7] !== 'none' ? 'AI ' + esc(i[7]) : '') + '</span>' : '') + '</li>';
    }).join('');
    return '<p class="small" aria-live="polite">Showing ' + Math.min(st.shown, rows.length) + ' of ' + fmt(rows.length) + (rows.length !== f.items.length ? ' matching (' + fmt(f.items.length) + ' in all)' : '') + '.</p>' +
      '<ul class="items">' + html + '</ul>' + (rows.length > st.shown ? '<button type="button" class="more" id="more-items">Show ' + Math.min(500, rows.length - st.shown) + ' more</button>' : '');
  }
  function itemsSection(f) {
    if (!f.items.length) return '';
    var st = itemsState(f), groups = [], statuses = [], counts = {};
    f.items.forEach(function (i) { if (i[2] && groups.indexOf(i[2]) < 0) groups.push(i[2]); if (statuses.indexOf(i[3]) < 0) statuses.push(i[3]); counts[i[3]] = (counts[i[3]] || 0) + 1; });
    groups.sort();
    var isList = f.shape === 'problem-list';
    var tally = isList ? '' : '<p class="tally">' + statuses.map(function (s) { return '<strong>' + fmt(counts[s]) + '</strong> ' + esc((ITEM_STATUS[s] || s).toLowerCase()); }).join(' · ') + '</p>';
    return '<div class="wrap block" id="items"><h2>' + (isList ? 'The list' : 'The full list') + '</h2>' + tally +
      '<div class="filters"><div><label for="item-q">Search</label><input id="item-q" type="search" value="' + esc(st.q) + '" placeholder="Name or topic"></div>' +
      (statuses.length > 1 ? '<div><label for="item-status">Status</label><select id="item-status"><option value="all">All</option>' + statuses.map(function (s) { return '<option value="' + esc(s) + '"' + (st.status === s ? ' selected' : '') + '>' + esc(ITEM_STATUS[s] || s) + '</option>'; }).join('') + '</select></div>' : '') +
      (groups.length > 1 ? '<div><label for="item-group">Group</label><select id="item-group"><option value="all">All</option>' + groups.map(function (g) { return '<option value="' + esc(g) + '"' + (st.group === g ? ' selected' : '') + '>' + esc(g) + '</option>'; }).join('') + '</select></div>' : '') +
      '</div><div id="items-list">' + itemsList(f) + '</div></div>';
  }
  function referenceSections(f) {
    var events = f.events.slice().sort(function (a, b) { return a.date < b.date ? 1 : -1; }).map(function (e) {
      return '<li><span class="n">' + esc(fmtDate(e.date)) + (e.kind ? '<em class="kind ' + esc(e.kind) + '">' + esc(e.kind) + '</em>' : '') + '</span><span>' + link(e.url, '<strong>' + esc(e.title) + '</strong>') + '<span>' + esc(e.why) + '</span></span></li>';
    }).join('');
    var reading = f.reading.map(function (r, i) {
      return '<li><span class="n">0' + (i + 1) + '</span><span>' + link(r.url, '<strong>' + esc(r.title) + '</strong>') + '<span>' + esc([r.author, r.note].filter(Boolean).join(' · ')) + '</span></span></li>';
    }).join('');
    var sources = f.sources.map(function (x) { return '<li><span class="n">' + esc(x.kind || '') + '</span><span>' + link(x.url, '<strong>' + esc(x.name) + '</strong>') + '</span></li>'; }).join('');
    var notices = f.credits.filter(function (c) { return c.line || c.notice; }).map(function (c) {
      return (c.line ? '<p>' + (c.sourceName ? '<strong>' + esc(c.sourceName) + '.</strong> ' : '') + esc(c.line) +
          (c.proposed ? ' <em>This wording was proposed when the data was added; it is not the source’s own.</em>' : '') + '</p>' : '') +
        (c.notice ? '<p>' + esc(c.notice) + '</p>' : '');
    }).join('');
    return '<div class="wrap block"><div class="two"><div class="l">' +
        (f.explainer ? '<h2>How to read it</h2><p class="prose">' + esc(f.explainer) + '</p>' : '') +
        (events ? '<h2 class="gap">What happened</h2><ul class="read">' + events + '</ul>' : '') + '</div>' +
      '<aside class="r">' + (reading ? '<h2>Start here</h2><ul class="read">' + reading + '</ul>' : '') +
        '<h2' + (reading ? ' class="gap"' : '') + '>Sources</h2><ul class="read">' + sources + '</ul>' +
        (f.lastChecked ? '<p class="small">Data last checked ' + esc(fmtDate(f.lastChecked)) + '.</p>' : '') + '</aside></div></div>' +
      (notices ? '<div class="wrap block"><details class="notice"><summary>Data credits and terms</summary>' + notices + '</details></div>' : '');
  }
  function aboutSection(f) {
    if (!f.about || (!f.about.what && !f.about.why)) return '';
    return '<div class="wrap block"><div class="about">' +
      (f.about.what ? '<div><h2>What this is</h2><p>' + esc(f.about.what) + '</p></div>' : '') +
      (f.about.why ? '<div><h2>Why it matters</h2><p>' + esc(f.about.why) + '</p></div>' : '') + '</div></div>';
  }
  function frontier(f) {
    var b = block(f), sid = selectedId(f), h = headline(f, sid), facts = '';
    if (h) {
      var change = h.gain === null || h.gain === undefined ? '' : '<div><dt>' + (b === 'records' ? 'Gain on previous record' : 'Change on previous figure') + '</dt><dd>' + (h.gain > 0 ? '+' : '') + fmt(h.gain) + (isPct(f) ? ' points' : '') + (h.prev ? ' <span class="soft">from ' + esc(fmtDate(h.prev[0])) + '</span>' : '') + '</dd></div>';
      facts = '<dl class="facts">' + (h.who ? '<div><dt>' + (b === 'records' ? 'Holder' : 'Which') + '</dt><dd>' + esc(h.who) + '</dd></div>' : '') +
        '<div><dt>' + (b === 'records' ? 'Set' : 'As of') + '</dt><dd>' + esc(fmtDate(h.date)) + (ago(h.date) ? ' · ' + ago(h.date) : '') + '</dd></div>' + change +
        (h.low !== null && h.low !== undefined && h.high !== null && h.high !== undefined ? '<div><dt>Range given by the source</dt><dd>' + fmt(h.low) + ' to ' + fmt(h.high) + '</dd></div>' : '') +
        (h.status ? '<div><dt>Status</dt><dd>' + statusHtml(h.status, '#0F1317') + '</dd></div>' : '') +
        '<div><dt>Measure</dt><dd class="soft2">' + esc(f.metric.name) + '</dd></div></dl>';
    }
    var all = ordered(), at = all.indexOf(f), prev = all[(at - 1 + all.length) % all.length], next = all[(at + 1) % all.length];
    var mates = all.filter(function (x) { return x.domain === f.domain && x.id !== f.id; });
    var around = '<div class="wrap block"><nav class="around" aria-label="Other frontiers">' +
      (mates.length ? '<div class="mates"><span class="eyebrow">More in ' + esc(f.domain) + '</span>' + mates.map(function (x) { return '<a href="#' + esc(x.id) + '">' + esc(x.title) + '</a>'; }).join('') + '</div>' : '') +
      (all.length > 1 ? '<div class="pn"><a class="pv" href="#' + esc(prev.id) + '"><span class="eyebrow">Previous</span><strong>' + esc(prev.title) + '</strong></a>' +
        '<a class="nx" href="#' + esc(next.id) + '"><span class="eyebrow">Next</span><strong>' + esc(next.title) + '</strong></a></div>' : '') + '</nav></div>';
    return '<header class="nav-plain"><div class="wrap nav">' + nav('#0F1317', f.id) + '</div></header>' +
      '<div class="wrap fr-head"><nav class="crumb eyebrow" aria-label="Breadcrumb"><a href="#home">Front page</a><span aria-hidden="true">/</span><a href="#domains">' + esc(f.domain) + '</a><span aria-hidden="true">/</span><span>' + esc(f.subfield) + '</span>' +
        (f.dataStatus === 'draft' ? '<span class="draft">Draft data, still being checked</span>' : '') + '</nav>' +
        '<div class="fr-title"><div class="l"><h1>' + esc(f.title) + '</h1><p>' + esc(f.summary) + '</p>' + (b && !(b === 'observations' && pointsMode(f)) ? picker(f, b, sid) : '') + '</div>' +
          (h ? '<div class="hl"><div class="eyebrow">' + esc(h.kind) + (h.label && h.label !== f.title ? ' · ' + esc(h.label) : '') + '</div>' + bigNumber(f, h) + '</div>' : '') + '</div>' + facts + '</div>' +
      aboutSection(f) + (b === 'records' ? recordsSections(f, sid) : b === 'observations' ? obsSections(f, sid) : '') +
      stagesSection(f) + stageDatesSection(f) + gridSection(f) + itemTimeSection(f) + itemsSection(f) + referenceSections(f) + around + siteFooter(f.id);
  }

  var Site = {
    home: home, frontier: frontier, itemsList: itemsList, tilesList: tilesList, tile: tile, creditLine: creditLine, esc: esc,
    filterHome: function (q, domain, shape) { homeState = { q: q || '', domain: domain || 'all', shape: shape || 'all' }; }, anchors: HOME_ANCHORS, seriesIds: seriesIds, block: block, gaugeMode: gaugeMode, reignMode: reignMode,
    costMode: costMode, ladderMode: ladderMode, paceMode: paceMode, downMode: downMode, lineupMode: lineupMode, discMode: discMode, recordCount: function (f, sid) { return progression(f, f.records[sid]).length; }, recClaimMode: recClaimMode, funnelMode: funnelMode, headline: headline, gridMode: gridMode, claimMode: claimMode, itemTimeMode: itemTimeMode, stageDatesMode: stageDatesMode,
    select: function (fid, sid) { chosen[fid] = sid; }, data: function () { return D; }
  };
  if (typeof module !== 'undefined' && module.exports) module.exports = Site;
  if (typeof document === 'undefined' || !document.getElementById) return;

  /* ---------- browser wiring ---------- */
  var app = document.getElementById('app'), bar = document.getElementById('progress'), current = null;
  function find(h) { return D.frontiers.filter(function (x) { return x.id === h; })[0]; }
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  function setSweep(svg, p) {
    var W = +svg.getAttribute('data-w'), rect = svg.querySelector('.sw-rect'), cur = svg.querySelector('.sw-cursor');
    if (!rect) return;
    rect.setAttribute('width', (14 + W * p + (p >= 1 ? 14 : 0)).toFixed(1));
    if (!cur) return;
    if (p <= 0 || p >= 1) { cur.setAttribute('visibility', 'hidden'); return; }
    cur.setAttribute('visibility', 'visible');
    cur.setAttribute('transform', 'translate(' + (W * p).toFixed(1) + ' 0)');
    var t0 = svg.getAttribute('data-t0'), label = cur.querySelector('text');
    label.textContent = t0 === null ? '' : Math.min(new Date().getFullYear(), Math.floor(+t0 + p * (+svg.getAttribute('data-t1') - +t0)));
  }
  /* Charts in view when a page opens draw themselves once. Charts further down draw as they are scrolled into view. */
  function startSweeps() {
    if (reduce) return;
    var vh = window.innerHeight;
    [].forEach.call(app.querySelectorAll('svg[data-sweep]'), function (svg) {
      var top = svg.getBoundingClientRect().top;
      if (top < vh * 0.85) {
        var start = null;
        svg.setAttribute('data-done', '1'); setSweep(svg, 0);
        window.requestAnimationFrame(function tick(now) {
          if (start === null) start = now;
          var k = Math.min(1, (now - start) / 1400);
          setSweep(svg, 1 - Math.pow(1 - k, 3));
          if (k < 1) window.requestAnimationFrame(tick);
        });
      } else { svg._p = 0; setSweep(svg, 0); }
    });
  }
  function scrollSweeps() {
    if (reduce) return;
    var vh = window.innerHeight;
    [].forEach.call(app.querySelectorAll('svg[data-sweep]:not([data-done])'), function (svg) {
      var r = svg.getBoundingClientRect();
      var p = Math.max(svg._p || 0, Math.min(1, (vh * 0.92 - r.top) / (vh * 0.3 + r.height * 0.6)));
      svg._p = p; setSweep(svg, p);
      if (p >= 1) svg.setAttribute('data-done', '1');
    });
  }
  function render(f, animate) { app.innerHTML = f ? frontier(f) : home(); if (animate) startSweeps(); }
  function route() {
    var h = (location.hash || '#home').slice(1), f = find(h), view = f ? f.id : 'home';
    var open = document.querySelector('details.menu[open]'); if (open) open.removeAttribute('open');
    if (view !== current) { render(f, true); document.title = f ? f.title + ' · ' + D.site.name : D.site.name; current = view; window.scrollTo(0, 0); }
    if (!f && HOME_ANCHORS[h] && h !== 'home') { var el = document.getElementById(h); if (el) el.scrollIntoView(); }
    else if (!f && h === 'home') window.scrollTo(0, 0);
    onScroll();
  }
  /* Choosing another series redraws the page with every chart complete: nothing is left half-drawn waiting for a scroll. */
  function rerender(keepScroll) {
    var f = find(current), y = window.scrollY; if (!f) return;
    render(f); [].forEach.call(app.querySelectorAll('svg[data-sweep]'), function (svg) { svg.setAttribute('data-done', '1'); });
    window.scrollTo(0, keepScroll ? y : 0);
  }
  function refreshTiles() { var el = document.getElementById('tiles-list'); if (el) el.innerHTML = tilesList(); }
  function refreshItems() { var f = find(current), el = document.getElementById('items-list'); if (f && el) el.innerHTML = itemsList(f); }
  app.addEventListener('change', function (e) {
    var f = find(current), t = e.target; if (!t) return;
    if (t.id === 'home-domain') { homeState.domain = t.value; refreshTiles(); }
    if (t.id === 'home-shape') { homeState.shape = t.value; refreshTiles(); }
    if (!f) return;
    if (t.id === 'series') { chosen[f.id] = t.value; rerender(true); var s = document.getElementById('series'); if (s) s.focus(); }
    if (t.id === 'item-status') { itemsState(f).status = t.value; itemsState(f).shown = 120; refreshItems(); }
    if (t.id === 'item-group') { itemsState(f).group = t.value; itemsState(f).shown = 120; refreshItems(); }
  });
  app.addEventListener('input', function (e) {
    if (e.target && e.target.id === 'home-q') { homeState.q = e.target.value; refreshTiles(); return; }
    var f = find(current); if (f && e.target && e.target.id === 'item-q') { itemsState(f).q = e.target.value; itemsState(f).shown = 120; refreshItems(); }
  });
  app.addEventListener('click', function (e) {
    var f = find(current), t = e.target; if (!t || !t.closest) return;
    if (t.closest('#home-clear')) {
      homeState = { q: '', domain: 'all', shape: 'all' };
      ['home-q', 'home-domain', 'home-shape'].forEach(function (id) { var el = document.getElementById(id); if (el) el.value = id === 'home-q' ? '' : 'all'; });
      refreshTiles(); var q = document.getElementById('home-q'); if (q) q.focus(); return;
    }
    if (!f) return;
    var b = t.closest('button.pick');
    if (b) { chosen[f.id] = b.getAttribute('data-series'); rerender(false); return; }
    if (t.closest('#more-items')) { itemsState(f).shown += 500; refreshItems(); }
  });
  function onScroll() {
    var el = document.scrollingElement || document.documentElement, max = el.scrollHeight - window.innerHeight;
    bar.style.transform = 'scaleX(' + (max > 0 ? Math.min(1, Math.max(0, el.scrollTop / max)) : 0) + ')';
    scrollSweeps();
  }
  document.addEventListener('click', function (e) {
    var open = document.querySelector('details.menu[open]');
    if (open && e.target && e.target.closest && (!e.target.closest('details.menu') || e.target.closest('.menu-panel a'))) open.removeAttribute('open');
  });
  window.addEventListener('scroll', onScroll, { passive: true });
  window.addEventListener('hashchange', route);
  route();
})();
