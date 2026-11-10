(function () {
  var D = window.FRONTIER_DATA;
  var app = document.getElementById('app');
  var MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  var STATUS = { claimed: 'Claimed', reviewed: 'Peer reviewed', 'peer-reviewed': 'Peer reviewed', peer_reviewed: 'Peer reviewed', confirmed: 'Independently confirmed', retracted: 'Retracted' };
  var HOME_ANCHORS = { home: 1, frontiers: 1, method: 1, domains: 1 };
  var chosen = {}; // frontier id -> selected series id

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; });
  }
  function parseDate(s) {
    var p = String(s).split('-').map(Number);
    return { y: p[0], m: p[1] || null, d: p[2] || null, t: p[0] + ((p[1] || 6.5) - 1) / 12 + ((p[2] || 15) - 1) / 365 };
  }
  function fmtDate(s) {
    var p = parseDate(s);
    return (p.d && p.d !== 1 ? p.d + ' ' : '') + (p.m ? MONTHS[p.m - 1] + ' ' : '') + p.y;
  }
  function fmtNum(v) { return String(Math.round(v * 100) / 100); }
  function nowT() { var n = new Date(); return n.getFullYear() + n.getMonth() / 12 + (n.getDate() - 1) / 365; }
  function yearsSince(s) { return nowT() - parseDate(s).t; }
  function ago(s) {
    var y = yearsSince(s);
    if (y < 1 / 12) return 'this month';
    if (y < 1) return Math.round(y * 12) + ' months ago';
    return (Math.round(y * 10) / 10) + ' years ago';
  }
  function mark(status, color, size) {
    var s = size || 12, inner;
    if (status === 'confirmed') inner = '<circle cx="6" cy="6" r="5.25" fill="' + color + '"/>';
    else {
      inner = '<circle cx="6" cy="6" r="4.5" fill="none" stroke="' + color + '" stroke-width="1.5"/>';
      if (status === 'reviewed' || status === 'peer-reviewed' || status === 'peer_reviewed') inner += '<path d="M6 1.5 A4.5 4.5 0 0 1 6 10.5 Z" fill="' + color + '"/>';
      if (status === 'retracted') inner += '<path d="M2.5 9.5 L9.5 2.5" stroke="' + color + '" stroke-width="1.5"/>';
    }
    return '<svg aria-hidden="true" width="' + s + '" height="' + s + '" viewBox="0 0 12 12">' + inner + '</svg>';
  }
  function statusHtml(status, color) { return '<span class="status">' + mark(status, color) + esc(STATUS[status] || status) + '</span>'; }
  function LOGO(c) {
    return '<svg aria-hidden="true" width="28" height="28" viewBox="0 0 28 28"><path d="M2 24 H9 V17 H16 V10 H23 V3" fill="none" stroke="' + c + '" stroke-width="2.5"/><circle cx="23" cy="4" r="3.5" fill="#FF7A40"/></svg>';
  }
  var ARROW = '<svg aria-hidden="true" width="16" height="16" viewBox="0 0 16 16"><path d="M2 8 H13 M9 4 L13 8 L9 12" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>';
  function nav(color) {
    return '<a class="brand" href="#home">' + LOGO(color) + '<span>' + esc(D.site.name) + '</span></a>' +
      '<nav aria-label="Main"><a href="#frontiers">Frontiers</a><a href="#method">Method</a><a href="#domains">Domains</a></nav>';
  }

  /* A series is a list of [date, value, holder, conditions, status, source], oldest first.
     Its record progression is the entries that beat everything before them. */
  function progression(rows) {
    var best = -Infinity, out = [];
    rows.forEach(function (r) { if (r[1] > best) { out.push({ r: r, gain: best === -Infinity ? null : r[1] - best }); best = r[1]; } });
    return out;
  }
  function seriesInfo(f, id) {
    var meta = f.series.filter(function (s) { return s.id === id; })[0];
    var rows = f.records[id] || [], prog = progression(rows);
    return { meta: meta, rows: rows, prog: prog, top: prog[prog.length - 1], name: meta.group === meta.label ? meta.label : meta.group + ': ' + meta.label };
  }
  function hasRows(f, id) { return !!(id && f.records[id] && f.records[id].length); }
  function bestSeries(f) {
    var best = null, v = -Infinity;
    f.series.forEach(function (s) { (f.records[s.id] || []).forEach(function (r) { if (r[1] > v) { v = r[1]; best = s.id; } }); });
    return best;
  }
  function supported(f) { return f.shape === 'Record chart' && !!bestSeries(f); }
  function selectedId(f) { return hasRows(f, chosen[f.id]) ? chosen[f.id] : hasRows(f, f.featured) ? f.featured : bestSeries(f); }

  /* Every series as a faint record line, with the selected one drawn in full. */
  function chart(f, selId, dark) {
    var c = dark
      ? { line: '#FF7A40', text: '#B6BCC3', strong: '#F4F5F1', grid: '#2A3037', axis: '#5B636C', faint: '#4A525B', bg: '#0F1317' }
      : { line: '#0F1317', text: '#4F5760', strong: '#0F1317', grid: '#D3D6CF', axis: '#0F1317', faint: '#B9BDB5', bg: '#FAFAF7' };
    var W = 880, H = 400, tN = nowT(), tMin = Infinity, vMax = 0;
    f.series.forEach(function (s) {
      (f.records[s.id] || []).forEach(function (r) { tMin = Math.min(tMin, parseDate(r[0]).t); vMax = Math.max(vMax, r[1]); });
    });
    var t0 = Math.floor(tMin), t1 = Math.ceil(tN + 0.1), y1 = Math.ceil((vMax + 2) / 5) * 5;
    function X(t) { return (t - t0) / (t1 - t0) * W; }
    function Y(v) { return H - v / y1 * H; }
    var o = '', v, yr;
    var tick = y1 <= 100 ? 10 : y1 / 5;
    for (v = tick; v <= y1 * 1.0001; v += tick) {
      o += '<path d="M0 ' + Y(v).toFixed(1) + ' H' + W + '" stroke="' + c.grid + '" stroke-width="1"/>' +
        '<text x="-12" y="' + (Y(v) + 4.5).toFixed(1) + '" fill="' + c.text + '" font-size="13" text-anchor="end">' + fmtNum(v) + (f.unit === '%' ? '%' : '') + '</text>';
    }
    o += '<path d="M0 ' + H + ' H' + W + '" stroke="' + c.axis + '" stroke-width="1"/>';
    var step = (t1 - t0) > 25 ? 10 : (t1 - t0) > 8 ? 2 : 1;
    for (yr = Math.ceil(t0 / step) * step; yr <= t1; yr += step) {
      o += '<path d="M' + X(yr).toFixed(1) + ' ' + H + ' V' + (H + 6) + '" stroke="' + c.axis + '" stroke-width="1"/>' +
        '<text x="' + X(yr).toFixed(1) + '" y="' + (H + 26) + '" fill="' + c.text + '" font-size="13" text-anchor="middle">' + yr + '</text>';
    }
    function path(prog) {
      var d = '';
      prog.forEach(function (p, i) {
        var x = X(parseDate(p.r[0]).t).toFixed(1), y = Y(p.r[1]).toFixed(1);
        d += i ? ' H' + x + ' V' + y : 'M' + x + ' ' + y;
      });
      return d + ' H' + X(tN).toFixed(1);
    }
    f.series.forEach(function (s) {
      if (s.id === selId) return;
      var prog = progression(f.records[s.id] || []);
      if (prog.length) o += '<path d="' + path(prog) + '" fill="none" stroke="' + c.faint + '" stroke-width="1"/>';
    });
    var sel = seriesInfo(f, selId), dots = '';
    sel.prog.forEach(function (p, i) {
      if (i < sel.prog.length - 1) dots += '<circle cx="' + X(parseDate(p.r[0]).t).toFixed(1) + '" cy="' + Y(p.r[1]).toFixed(1) + '" r="3"/>';
    });
    var top = sel.top.r, lx = X(parseDate(top[0]).t), ly = Y(top[1]);
    var anchorEnd = lx > W * 0.35;
    o += '<path d="' + path(sel.prog) + '" fill="none" stroke="' + c.line + '" stroke-width="2.5"/>' +
      '<g fill="' + c.bg + '" stroke="' + c.line + '" stroke-width="1.5">' + dots + '</g>' +
      '<circle cx="' + lx.toFixed(1) + '" cy="' + ly.toFixed(1) + '" r="11" fill="#E4531A" fill-opacity="0.22"/>' +
      '<circle cx="' + lx.toFixed(1) + '" cy="' + ly.toFixed(1) + '" r="5.5" fill="' + (dark ? '#FFFFFF' : '#E4531A') + '"/>' +
      '<text x="' + (lx + (anchorEnd ? -14 : 14)).toFixed(1) + '" y="' + (ly - 14).toFixed(1) + '" fill="' + c.strong + '" stroke="' + c.bg + '" stroke-width="5" paint-order="stroke" font-size="14" font-weight="500" text-anchor="' + (anchorEnd ? 'end' : 'start') + '">' +
      fmtNum(top[1]) + esc(f.unit) + ' · ' + esc(top[2]) + ' · ' + esc(fmtDate(top[0])) + '</text>';
    var label = 'Record chart for ' + sel.name + ': ' + fmtNum(sel.prog[0].r[1]) + f.unit + ' in ' + parseDate(sel.prog[0].r[0]).y + ' to ' +
      fmtNum(top[1]) + f.unit + ' in ' + parseDate(top[0]).y + '. Thin lines show the other series.';
    return '<div class="chart-box"><svg role="img" aria-label="' + esc(label) + '" viewBox="-58 -22 ' + (W + 76) + ' ' + (H + 58) + '">' + o + '</svg></div>' +
      (f.credit ? '<p class="credit">' + esc(f.credit) + '</p>' : '');
  }

  function home() {
    var live = D.frontiers.filter(supported), f = live[0];
    var sid = f ? selectedId(f) : null, s = f ? seriesInfo(f, sid) : null, top = s ? s.top : null;
    var liveDomains = {}; live.forEach(function (x) { liveDomains[x.domain] = (liveDomains[x.domain] || 0) + 1; });
    var rows = D.frontiers.map(function (x) {
      if (!supported(x)) return '<li><span class="d">' + esc(x.domain) + '</span><span class="t">' + esc(x.title) + '</span>' +
        '<span class="s">' + esc(x.shape) + '</span><span class="w">Data in, chart to come</span></li>';
      return '<li class="live"><span class="d">' + esc(x.domain) + '</span><span class="t"><a href="#' + esc(x.id) + '">' + esc(x.title) + '</a></span>' +
        '<span class="s">' + esc(x.shape) + '</span><span class="w">Live</span></li>';
    }).join('') + D.planned.map(function (x) {
      return '<li><span class="d">' + esc(x.domain) + '</span><span class="t">' + esc(x.title) + '</span>' +
        '<span class="s">' + esc(x.shape) + '</span><span class="w">Next in the queue</span></li>';
    }).join('');
    var doms = D.domains.map(function (name, i) {
      var n = liveDomains[name];
      return '<li class="' + (n ? 'on' : '') + '"><span class="n">' + (i < 9 ? '0' : '') + (i + 1) + '</span><span>' + esc(name) + '</span>' +
        (n ? '<span class="live"><i></i>' + n + ' live</span>' : '') + '</li>';
    }).join('');
    var total = 0; if (f) f.series.forEach(function (x) { total += (f.records[x.id] || []).length; });

    return '<div class="stack">' +
      '<section class="hero dark"><img src="img/moon.jpg" alt="The cratered surface of the Moon seen from orbit, with black sky above the horizon"><div class="fade" aria-hidden="true"></div>' +
        '<div class="wrap inner"><div class="top"><header class="nav">' + nav('#F4F5F1') + '</header>' +
          '<div><div class="eyebrow">Science and technology, by the numbers</div><h1>How far has the frontier moved?</h1></div></div>' +
          '<div class="foot"><p>The current record on the hardest problems in science and technology. Each one is charted, linked to its source and marked with how well it has been checked.</p>' +
          (f ? '<a class="pill pill-ghost" href="#' + esc(f.id) + '">See the first frontier ' + ARROW + '</a>' : '') + '</div></div></section>' +
      (!f ? '' : '<section class="feature dark" id="live"><div class="wrap inner">' +
        '<div class="row eyebrow"><span>Live now · ' + esc(f.domain) + ' · ' + esc(f.subfield) + '</span><span>' + esc(f.shape) + '</span></div>' +
        '<div class="main"><div class="copy">' +
          '<div class="big">' + fmtNum(top.r[1]) + '<span class="unit">' + esc(f.unit) + '</span></div>' +
          '<h2>' + esc(f.title) + ': ' + esc(s.meta.label) + '</h2>' +
          '<p class="lede">One line on a chart of ' + total + ' results across ' + f.series.length + ' series, going back to ' + parseDate(firstDate(f)).y + '.</p>' +
          '<div class="meta"><span>' + esc(top.r[2]) + ' · ' + esc(fmtDate(top.r[0])) + '</span>' + statusHtml(top.r[4], '#F4F5F1') + '</div>' +
          '<div><a class="pill pill-hot" href="#' + esc(f.id) + '">Open the full record ' + ARROW + '</a></div>' +
        '</div><div class="chart">' + chart(f, sid, true) + '</div></div>' +
      '</div></section>') + '</div>' +

      '<section class="band" id="frontiers"><div class="wrap"><div class="head"><h2>Frontiers</h2>' +
        '<p>One goes live at a time, as its records are checked against sources. The rest are in the queue.</p></div>' +
        '<ul class="rows">' + rows + '</ul></div></section>' +

      '<section class="band" id="method"><div class="wrap"><div class="head"><h2>Every record carries a status</h2>' +
        '<p>A number is only as good as the checking behind it, so the mark travels with the number.</p></div>' +
        '<div class="marks">' +
          '<div class="mark">' + mark('claimed', '#0F1317', 22) + '<div><strong>Claimed</strong><span>Announced by the team that did the work.</span></div></div>' +
          '<div class="mark">' + mark('reviewed', '#0F1317', 22) + '<div><strong>Peer reviewed</strong><span>Published after review by other researchers.</span></div></div>' +
          '<div class="mark">' + mark('confirmed', '#0F1317', 22) + '<div><strong>Independently confirmed</strong><span>Measured or reproduced by a separate group.</span></div></div>' +
          '<div class="mark">' + mark('retracted', '#0F1317', 22) + '<div><strong>Retracted</strong><span>Withdrawn or shown not to hold.</span></div></div>' +
        '</div></div></section>' +

      '<section class="section-dark dark" id="domains"><div class="wrap"><div class="head"><h2>' + D.domains.length + ' domains</h2>' +
        '<p>The full map of what the site will cover, in order from the sciences to technology.</p></div>' +
        '<ol class="domains">' + doms + '</ol>' +
        '<p class="foot-note">Photograph: NASA.</p></div></section>';
  }
  function firstDate(f) {
    var m = '9999';
    f.series.forEach(function (s) { var r = (f.records[s.id] || [])[0]; if (r && r[0] < m) m = r[0]; });
    return m;
  }

  function frontier(f) {
    var sid = selectedId(f), s = seriesInfo(f, sid), top = s.top, groups = [], byGroup = {};
    f.series.forEach(function (x) { if (!hasRows(f, x.id)) return; if (!byGroup[x.group]) { byGroup[x.group] = []; groups.push(x.group); } byGroup[x.group].push(x); });
    var options = groups.map(function (g) {
      return '<optgroup label="' + esc(g) + '">' + byGroup[g].map(function (x) {
        return '<option value="' + esc(x.id) + '"' + (x.id === sid ? ' selected' : '') + '>' + esc(x.label) + '</option>';
      }).join('') + '</optgroup>';
    }).join('');
    var board = f.series.filter(function (x) { return hasRows(f, x.id); }).map(function (x) { return seriesInfo(f, x.id); })
      .sort(function (a, b) { return b.top.r[1] - a.top.r[1]; });
    var maxV = board[0].top.r[1];
    var boardRows = board.map(function (x, i) {
      var on = x.meta.id === sid;
      return '<tr class="' + (on ? 'now' : '') + '"><td class="rank">' + (i + 1) + '</td>' +
        '<td><button type="button" class="pick" data-series="' + esc(x.meta.id) + '"' + (on ? ' aria-current="true"' : '') + '>' + esc(x.meta.label) + '</button><div class="sub">' + esc(x.meta.group) + '</div></td>' +
        '<td class="v">' + fmtNum(x.top.r[1]) + esc(f.unit) + '</td>' +
        '<td class="barcell"><div class="bar" aria-hidden="true"><i style="width:' + (x.top.r[1] / maxV * 100).toFixed(1) + '%"></i></div></td>' +
        '<td>' + esc(x.top.r[2]) + '</td><td class="date">' + esc(fmtDate(x.top.r[0])) + '</td></tr>';
    }).join('');
    var srcById = {}; f.sources.forEach(function (x) { srcById[x.id] = x; });
    var isRecord = {}; s.prog.forEach(function (p) { isRecord[s.rows.indexOf(p.r)] = p; });
    var hist = s.rows.map(function (r, i) {
      var p = isRecord[i], src = srcById[r[5]];
      return '<tr class="' + (p && p === s.top ? 'now' : '') + '"><td class="date">' + esc(fmtDate(r[0])) + '</td>' +
        '<td class="v' + (p ? '' : ' dim') + '">' + fmtNum(r[1]) + esc(f.unit) + '</td>' +
        '<td class="g">' + (p ? (p.gain === null ? 'First' : '+' + fmtNum(p.gain)) : 'Not a record') + '</td>' +
        '<td>' + esc(r[2]) + '</td><td class="cond">' + esc(r[3]) + '</td>' +
        '<td>' + statusHtml(r[4], '#0F1317') + '</td>' +
        '<td>' + (src && src.url ? '<a href="' + esc(src.url) + '" target="_blank" rel="noopener">Source</a>' : '<span class="need">Source needed</span>') + '</td></tr>';
    }).reverse().join('');
    var sources = f.sources.map(function (x) {
      return '<li><span class="n">' + esc(x.kind || '') + '</span><span>' + (x.url ? '<a href="' + esc(x.url) + '" target="_blank" rel="noopener"><strong>' + esc(x.name) + '</strong></a>' : '<strong>' + esc(x.name) + '</strong>') + '</span></li>';
    }).join('');
    var events = f.events.slice().reverse().map(function (e) {
      return '<li><span class="n">' + esc(fmtDate(e.date)) + '</span><span>' + (e.url ? '<a href="' + esc(e.url) + '" target="_blank" rel="noopener"><strong>' + esc(e.title) + '</strong></a>' : '<strong>' + esc(e.title) + '</strong>') +
        '<span>' + esc(e.why) + '</span></span></li>';
    }).join('');
    var prev = s.prog.length > 1 ? s.prog[s.prog.length - 2] : null;

    return '<header class="nav-plain"><div class="wrap nav">' + nav('#0F1317') + '</div></header>' +
      '<div class="wrap fr-head"><nav class="crumb eyebrow" aria-label="Breadcrumb"><a href="#domains">' + esc(f.domain) + '</a><span aria-hidden="true">/</span><span>' + esc(f.subfield) + '</span></nav>' +
        '<div class="fr-title"><div class="l"><h1>' + esc(f.title) + '</h1><p>' + esc(f.summary) + '</p>' +
          '<div class="picker"><label for="series">Series</label><select id="series">' + options + '</select></div></div>' +
          '<div><div class="eyebrow">Current record · ' + esc(s.meta.label) + '</div><div class="big">' + fmtNum(top.r[1]) + '<span class="unit">' + esc(f.unit) + '</span></div></div></div>' +
        '<dl class="facts">' +
          '<div><dt>Holder</dt><dd>' + esc(top.r[2]) + '</dd></div>' +
          '<div><dt>Set</dt><dd>' + esc(fmtDate(top.r[0])) + ' · ' + ago(top.r[0]) + '</dd></div>' +
          '<div><dt>Gain on previous record</dt><dd>' + (top.gain === null ? 'First record' : '+' + fmtNum(top.gain) + (f.unit === '%' ? ' points' : ' ' + esc(f.unit))) + (prev ? ' <span class="soft">from ' + esc(fmtDate(prev.r[0])) + '</span>' : '') + '</dd></div>' +
          '<div><dt>Records in this series</dt><dd>' + s.prog.length + ' <span class="soft">of ' + s.rows.length + ' charted results</span></dd></div>' +
          '<div><dt>Status</dt><dd>' + statusHtml(top.r[4], '#0F1317') + '</dd></div>' +
        '</dl></div>' +
      '<div class="wrap block"><h2>' + esc(s.name) + '</h2>' +
        '<div class="card">' + chart(f, sid, false) + '</div>' +
        '<p class="small">The dark line is the record for the selected series. Thin lines are the other series. ' + (top.r[3] ? 'Current record: ' + esc(top.r[3]) + '.' : '') + '</p></div>' +
      '<div class="wrap block"><h2>Where each series stands</h2><div class="tbl"><table class="board"><thead><tr>' +
        '<th scope="col">#</th><th scope="col">Series</th><th scope="col">Record</th><th scope="col"><span class="vh">Relative size</span></th><th scope="col">Holder</th><th scope="col">Set</th>' +
        '</tr></thead><tbody>' + boardRows + '</tbody></table></div></div>' +
      '<div class="wrap block"><h2>History: ' + esc(s.meta.label) + '</h2><div class="tbl"><table><thead><tr>' +
        '<th scope="col">Measured</th><th scope="col">Result</th><th scope="col">Gain</th><th scope="col">Holder</th><th scope="col">Conditions</th><th scope="col">Status</th><th scope="col">Source</th>' +
        '</tr></thead><tbody>' + hist + '</tbody></table></div></div>' +
      '<div class="wrap block"><div class="two"><div class="l"><h2>How to read it</h2><p class="prose">' + esc(f.explainer) + '</p>' +
        (events ? '<h2 class="gap">Updates</h2><ul class="read">' + events + '</ul>' : '') + '</div>' +
        '<aside class="r"><h2>Sources</h2><ul class="read">' + sources + '</ul>' +
        '<p class="small">Data last checked ' + esc(fmtDate(f.lastChecked)) + '.</p></aside></div></div>' +
      (f.notice ? '<div class="wrap block"><details class="notice"><summary>Data notice and terms</summary><p>' + esc(f.credit) + '</p><p>' + esc(f.notice) + '</p></details></div>' : '') +
      '<footer class="footer dark"><div class="wrap"><p class="l">Every number links to its source. Every record carries a status.</p>' +
        '<a class="pill pill-ghost" href="#home">Back to the front page</a></div></footer>';
  }

  var current = null;
  function findFrontier(h) { return D.frontiers.filter(function (x) { return x.id === h && supported(x); })[0]; }
  function render(f) { app.innerHTML = f ? frontier(f) : home(); }
  function route() {
    var h = (location.hash || '#home').slice(1), f = findFrontier(h), view = f ? f.id : 'home';
    if (view !== current) {
      render(f);
      document.title = f ? f.title + ' · ' + D.site.name : D.site.name;
      current = view;
      window.scrollTo(0, 0);
    }
    if (!f && HOME_ANCHORS[h] && h !== 'home') { var el = document.getElementById(h); if (el) el.scrollIntoView(); }
    else if (!f && h === 'home') window.scrollTo(0, 0);
    onScroll();
  }
  function pick(id) {
    var f = findFrontier(current);
    if (!f) return;
    chosen[f.id] = id;
    var y = window.scrollY;
    render(f);
    window.scrollTo(0, y);
  }
  app.addEventListener('change', function (e) { if (e.target && e.target.id === 'series') { pick(e.target.value); var s = document.getElementById('series'); if (s) s.focus(); } });
  app.addEventListener('click', function (e) {
    var b = e.target.closest ? e.target.closest('button.pick') : null;
    if (b) { pick(b.getAttribute('data-series')); window.scrollTo(0, 0); }
  });
  var bar = document.getElementById('progress');
  function onScroll() {
    var el = document.scrollingElement || document.documentElement, max = el.scrollHeight - window.innerHeight;
    bar.style.transform = 'scaleX(' + (max > 0 ? Math.min(1, Math.max(0, el.scrollTop / max)) : 0) + ')';
  }
  window.addEventListener('scroll', onScroll, { passive: true });
  window.addEventListener('hashchange', route);
  route();
})();
