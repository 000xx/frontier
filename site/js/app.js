/*
  Frontier in Numbers: draws every page from window.FRONTIER_DATA (site/js/data.js).

  A frontier page is assembled from the blocks its data file holds:
    records               -> record chart, ranking of series, history table (and a two-axis chart when metric.axes exist)
    observations          -> line chart with ranges and a table (or a points chart when each series is a single point)
    stages + candidates   -> stage table
    items                 -> filterable list
    events, reading, sources, credits -> the reference sections
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
  function nav(color) {
    return '<a class="brand" href="#home">' + LOGO(color) + '<span>' + esc(D.site.name) + '</span></a>' +
      '<nav aria-label="Main"><a href="#frontiers">Frontiers</a><a href="#method">Method</a><a href="#domains">Domains</a></nav>';
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
  function progression(f, rows) {
    var best = null, out = [];
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
    seriesIds(f, b).forEach(function (id) { f[b][id].forEach(function (r) { if (v === null || better(f, r[1], v)) { v = r[1]; best = id; } }); });
    return best;
  }
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
  function frame(o, W, H, aria, credit) {
    return '<div class="chart-box"><svg role="img" aria-label="' + esc(aria) + '" viewBox="-96 -22 ' + (W + 114) + ' ' + (H + 58) + '">' + o + '</svg></div>' +
      (credit ? '<p class="credit">' + esc(credit) + '</p>' : '');
  }
  function creditLine(f) { return f.credits.map(function (c) { return c.line; }).filter(Boolean).join(' '); }

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
    var ax = valueAxis(vs, f.metric.scale, H, suffix(f));
    function X(t) { return (t - t0) / (t1 - t0) * W; }
    ax.ticks.forEach(function (k) {
      out += '<path d="M0 ' + ax.Y(k.v).toFixed(1) + ' H' + W + '" stroke="' + c.grid + '" stroke-width="1"/>' +
        '<text x="-12" y="' + (ax.Y(k.v) + 4.5).toFixed(1) + '" fill="' + c.text + '" font-size="13" text-anchor="end">' + esc(k.label) + '</text>';
    });
    out += '<path d="M0 ' + H + ' H' + W + '" stroke="' + c.axis + '" stroke-width="1"/>';
    timeTicks(t0, t1).forEach(function (y) {
      out += '<path d="M' + X(y).toFixed(1) + ' ' + H + ' V' + (H + 6) + '" stroke="' + c.axis + '" stroke-width="1"/>' +
        '<text x="' + X(y).toFixed(1) + '" y="' + (H + 26) + '" fill="' + c.text + '" font-size="13" text-anchor="middle">' + y + '</text>';
    });
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
      out += '<path d="' + path(l) + '" fill="none" stroke="' + c.line + '" stroke-width="2.5"/>';
      var dots = '';
      l.pts.forEach(function (p) { dots += '<circle cx="' + X(p[0]).toFixed(1) + '" cy="' + ax.Y(p[1]).toFixed(1) + '" r="3"/>'; });
      if (l.pts.length <= 80) out += '<g fill="' + c.bg + '" stroke="' + c.line + '" stroke-width="1.5">' + dots + '</g>';
    });
    (o.dots || []).forEach(function (d) {
      out += '<circle cx="' + X(d[0]).toFixed(1) + '" cy="' + ax.Y(d[1]).toFixed(1) + '" r="' + (d[2] ? 4 : 3.5) + '" fill="' + (d[2] ? c.line : c.bg) + '" stroke="' + c.line + '" stroke-width="1.5"><title>' + esc(d[3] || '') + '</title></circle>';
    });
    if (o.label) {
      var lx = X(o.label.t), ly = ax.Y(o.label.v), end = lx > W * 0.35, below = ly < 34;
      out += '<circle cx="' + lx.toFixed(1) + '" cy="' + ly.toFixed(1) + '" r="11" fill="#E4531A" fill-opacity="0.22"/>' +
        '<circle cx="' + lx.toFixed(1) + '" cy="' + ly.toFixed(1) + '" r="5.5" fill="' + c.hot + '"/>' +
        '<text x="' + (lx + (end ? -14 : 14)).toFixed(1) + '" y="' + (ly + (below ? 26 : -14)).toFixed(1) + '" fill="' + c.strong + '" stroke="' + c.bg + '" stroke-width="5" paint-order="stroke" font-size="14" font-weight="500" text-anchor="' + (end ? 'end' : 'start') + '">' + esc(o.label.text) + '</text>';
    }
    return frame(out, W, H, o.aria, creditLine(f));
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
    return timeChart(f, {
      lines: lines, marks: marks,
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
    if (pts.length < 2) return '<svg class="spark" aria-hidden="true" viewBox="0 0 240 56"></svg>';
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
    return '<svg class="spark" aria-hidden="true" viewBox="0 0 240 56">' + body + '</svg>';
  }

  /* ---------- front page ---------- */
  function bigNumber(f, h) {
    return '<div class="big' + (fmt(h.value).length > 6 ? ' long' : '') + '">' + fmt(h.value) + (suffix(f) ? '<span class="unit">' + suffix(f) + '</span>' : '') + '</div>' +
      (unitText(f) ? '<div class="unitline">' + esc(unitText(f)) + '</div>' : '');
  }
  function tile(f) {
    var h = headline(f), draft = f.dataStatus === 'draft';
    return '<a class="tile" href="#' + esc(f.id) + '"><span class="trow eyebrow"><span>' + esc(f.domain) + '</span><span>' + esc(shapeLabel(f)) + '</span></span>' +
      (h ? '<span class="tnum">' + fmt(h.value) + (suffix(f) ? '<i>' + suffix(f) + '</i>' : '') + '</span>' + (unitText(f) ? '<span class="tunit">' + esc(unitText(f)) + '</span>' : '')
        : '<span class="tnum words">' + (f.items.length ? fmt(f.items.length) + ' listed' : esc(shapeLabel(f))) + '</span>') +
      '<span class="ttitle">' + esc(f.title) + '</span>' + spark(f) +
      '<span class="trow tfoot"><span>' + (h ? esc((h.who ? h.who + ' · ' : '') + fmtDate(h.date)) : 'Updated ' + esc(fmtDate(f.lastChecked))) + '</span>' +
      (draft ? '<span class="draft">Draft data</span>' : h && h.status ? statusHtml(h.status, '#0F1317') : '') + '</span></a>';
  }
  function home() {
    var lead = D.frontiers.filter(function (x) { return x.id === D.site.lead && hasRecords(x); })[0] || D.frontiers.filter(hasRecords)[0];
    var liveDomains = {}; D.frontiers.forEach(function (x) { liveDomains[x.domain] = (liveDomains[x.domain] || 0) + 1; });
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
      var n = liveDomains[name];
      return '<li class="' + (n ? 'on' : '') + '"><span class="n">' + (i < 9 ? '0' : '') + (i + 1) + '</span><span>' + esc(name) + '</span>' +
        (n ? '<span class="live"><i></i>' + n + ' live</span>' : '') + '</li>';
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
        '<div class="tiles">' + D.frontiers.map(tile).join('') + '</div>' + queue + '</div></section>' +

      '<section class="band" id="method"><div class="wrap"><div class="head"><h2>Every record carries a status</h2>' +
        '<p>A number is only as good as the checking behind it, so the mark travels with the number.</p></div>' +
        '<div class="marks">' +
          '<div class="mark">' + mark('claimed', '#0F1317', 22) + '<div><strong>Claimed</strong><span>Announced by the team that did the work.</span></div></div>' +
          '<div class="mark">' + mark('peer_reviewed', '#0F1317', 22) + '<div><strong>Peer reviewed</strong><span>Published after review by other researchers.</span></div></div>' +
          '<div class="mark">' + mark('confirmed', '#0F1317', 22) + '<div><strong>Independently confirmed</strong><span>Measured or reproduced by a separate group.</span></div></div>' +
          '<div class="mark">' + mark('retracted', '#0F1317', 22) + '<div><strong>Retracted</strong><span>Withdrawn or shown not to hold.</span></div></div>' +
        '</div></div></section>' +

      '<section class="section-dark dark" id="domains"><div class="wrap"><div class="head"><h2>' + D.domains.length + ' domains</h2>' +
        '<p>The full map of what the site will cover, in order from the sciences to technology.</p></div>' +
        '<ol class="domains">' + doms + '</ol><p class="foot-note">Photograph: NASA.</p></div></section>';
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
      '<p class="small">The dark line is the record for the selected series.' + (ids.length > 1 ? ' Thin lines are the other series.' : '') + (top.r[3] ? ' Current record: ' + esc(top.r[3]) + '.' : '') + '</p></div>';
    if (f.metric.axes.length) out += scatterChart(f, sid);
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
          '<td class="g">' + (p ? (p.gain === null ? 'First' : (p.gain > 0 ? '+' : '') + fmt(p.gain)) : 'Not a record') + '</td><td>' + esc(r[2]) + '</td><td class="cond">' + esc(r[3]) + '</td>' +
          '<td>' + statusHtml(r[4], '#0F1317') + '</td><td>' + sourceLink(f, r[5]) + '</td></tr>';
      }).reverse().join('') + '</tbody></table></div></div>';
    return out;
  }
  function obsSections(f, sid) {
    var pm = pointsMode(f), meta = seriesMeta(f, sid), rows, head, body;
    var out = '<div class="wrap block"><h2>' + esc(pm ? f.metric.name : seriesName(meta)) + '</h2><div class="card">' + obsChart(f, sid, false) + '</div>' +
      '<p class="small">' + (pm ? 'Each point is one entry, placed at its date. Hover a point for its name.' : 'The shaded band, where shown, is the range the source gives around its central figure.') +
      (f.metric.scale === 'log' ? ' The vertical axis is a log scale.' : '') + '</p></div>';
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
    var notices = f.credits.filter(function (c) { return c.line || c.notice; }).map(function (c) { return (c.line ? '<p>' + esc(c.line) + '</p>' : '') + (c.notice ? '<p>' + esc(c.notice) + '</p>' : ''); }).join('');
    return '<div class="wrap block"><div class="two"><div class="l">' +
        (f.explainer ? '<h2>How to read it</h2><p class="prose">' + esc(f.explainer) + '</p>' : '') +
        (events ? '<h2 class="gap">What happened</h2><ul class="read">' + events + '</ul>' : '') + '</div>' +
      '<aside class="r">' + (reading ? '<h2>Start here</h2><ul class="read">' + reading + '</ul>' : '') +
        '<h2' + (reading ? ' class="gap"' : '') + '>Sources</h2><ul class="read">' + sources + '</ul>' +
        (f.lastChecked ? '<p class="small">Data last checked ' + esc(fmtDate(f.lastChecked)) + '.</p>' : '') + '</aside></div></div>' +
      (notices ? '<div class="wrap block"><details class="notice"><summary>Data credits and terms</summary>' + notices + '</details></div>' : '');
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
    return '<header class="nav-plain"><div class="wrap nav">' + nav('#0F1317') + '</div></header>' +
      '<div class="wrap fr-head"><nav class="crumb eyebrow" aria-label="Breadcrumb"><a href="#domains">' + esc(f.domain) + '</a><span aria-hidden="true">/</span><span>' + esc(f.subfield) + '</span>' +
        (f.dataStatus === 'draft' ? '<span class="draft">Draft data, still being checked</span>' : '') + '</nav>' +
        '<div class="fr-title"><div class="l"><h1>' + esc(f.title) + '</h1><p>' + esc(f.summary) + '</p>' + (b && !(b === 'observations' && pointsMode(f)) ? picker(f, b, sid) : '') + '</div>' +
          (h ? '<div class="hl"><div class="eyebrow">' + esc(h.kind) + (h.label && h.label !== f.title ? ' · ' + esc(h.label) : '') + '</div>' + bigNumber(f, h) + '</div>' : '') + '</div>' + facts + '</div>' +
      (b === 'records' ? recordsSections(f, sid) : b === 'observations' ? obsSections(f, sid) : '') +
      stagesSection(f) + itemsSection(f) + referenceSections(f) +
      '<footer class="footer dark"><div class="wrap"><p class="l">Every number links to its source. Every record carries a status.</p>' +
        '<a class="pill pill-ghost" href="#home">Back to the front page</a></div></footer>';
  }

  var Site = {
    home: home, frontier: frontier, itemsList: itemsList, seriesIds: seriesIds, block: block,
    select: function (fid, sid) { chosen[fid] = sid; }, data: function () { return D; }
  };
  if (typeof module !== 'undefined' && module.exports) module.exports = Site;
  if (typeof document === 'undefined' || !document.getElementById) return;

  /* ---------- browser wiring ---------- */
  var app = document.getElementById('app'), bar = document.getElementById('progress'), current = null;
  function find(h) { return D.frontiers.filter(function (x) { return x.id === h; })[0]; }
  function render(f) { app.innerHTML = f ? frontier(f) : home(); }
  function route() {
    var h = (location.hash || '#home').slice(1), f = find(h), view = f ? f.id : 'home';
    if (view !== current) { render(f); document.title = f ? f.title + ' · ' + D.site.name : D.site.name; current = view; window.scrollTo(0, 0); }
    if (!f && HOME_ANCHORS[h] && h !== 'home') { var el = document.getElementById(h); if (el) el.scrollIntoView(); }
    else if (!f && h === 'home') window.scrollTo(0, 0);
    onScroll();
  }
  function rerender(keepScroll) { var f = find(current), y = window.scrollY; if (!f) return; render(f); window.scrollTo(0, keepScroll ? y : 0); }
  function refreshItems() { var f = find(current), el = document.getElementById('items-list'); if (f && el) el.innerHTML = itemsList(f); }
  app.addEventListener('change', function (e) {
    var f = find(current), t = e.target; if (!f || !t) return;
    if (t.id === 'series') { chosen[f.id] = t.value; rerender(true); var s = document.getElementById('series'); if (s) s.focus(); }
    if (t.id === 'item-status') { itemsState(f).status = t.value; itemsState(f).shown = 120; refreshItems(); }
    if (t.id === 'item-group') { itemsState(f).group = t.value; itemsState(f).shown = 120; refreshItems(); }
  });
  app.addEventListener('input', function (e) {
    var f = find(current); if (f && e.target && e.target.id === 'item-q') { itemsState(f).q = e.target.value; itemsState(f).shown = 120; refreshItems(); }
  });
  app.addEventListener('click', function (e) {
    var f = find(current), t = e.target; if (!f || !t || !t.closest) return;
    var b = t.closest('button.pick');
    if (b) { chosen[f.id] = b.getAttribute('data-series'); rerender(false); return; }
    if (t.closest('#more-items')) { itemsState(f).shown += 500; refreshItems(); }
  });
  function onScroll() {
    var el = document.scrollingElement || document.documentElement, max = el.scrollHeight - window.innerHeight;
    bar.style.transform = 'scaleX(' + (max > 0 ? Math.min(1, Math.max(0, el.scrollTop / max)) : 0) + ')';
  }
  window.addEventListener('scroll', onScroll, { passive: true });
  window.addEventListener('hashchange', route);
  route();
})();
