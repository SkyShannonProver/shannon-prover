/* Read-only case studies, isolated from the managed proof-node run browser. */
(function (global) {
  'use strict';
  const esc = value => String(value == null ? '' : value).replace(/[&<>"']/g,
    c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
  const catalog = global.SHANNON_CASE_STUDIES || {schema_version: 1, cases: []};
  const cases = catalog.schema_version === 1 ? catalog.cases : [];
  const loaded = new Map();
  let generation = 0;
  const tabs = ['browser', 'process', 'verification'];

  function routeHash(caseId, fileId, lemmaId, tab = 'browser', page = null) {
    return '#case/' + [caseId, fileId, page == null ? (lemmaId || 'source') : 'source-' + page, tab]
      .map(x => encodeURIComponent(x || '')).join('/');
  }
  function parseRoute(hash) {
    try {
      const parts = hash.replace(/^#case\//, '').split('/').map(decodeURIComponent);
      const page = /^source-\d+$/.test(parts[2] || '') ? Number(parts[2].slice(7)) : 0;
      return {caseId: parts[0], fileId: parts[1], lemmaId: parts[2],
        tab: tabs.includes(parts[3]) ? parts[3] : 'browser', page};
    } catch (_) { return null; }
  }
  function sourceReferences(file, lemma) {
    if (!lemma || !lemma.proof) return [];
    const words = new Set(lemma.proof.match(/[A-Za-z_][A-Za-z0-9_']*/g) || []);
    const counts = new Map();
    file.lemmas.forEach(l => counts.set(l.name, (counts.get(l.name) || 0) + 1));
    return file.lemmas.filter(l => l.start < lemma.start && counts.get(l.name) === 1 && words.has(l.name));
  }
  function processView(c, data) {
    const story = c.processStory;
    if (!story) return '<h2>The agent’s proof-building process</h2><ol>' +
      (c.process || []).map(e => '<li><h3>' + esc(e[0]) + '</h3><p>' + esc(e[1]) + '</p></li>').join('') + '</ol>';
    function lemmaLink(ref) {
      const matches = data[ref.file]?.lemmas.filter(l => l.name === ref.lemma) || [];
      if (matches.length !== 1) return '<span class="sb-muted">' + esc(ref.lemma) + ' (source link unavailable)</span>';
      return '<a href="' + routeHash(c.id, ref.file, matches[0].id) + '">' + esc(ref.lemma) + ' →</a>';
    }
    function evidence(items) {
      return '<details class="sb-trace"><summary>Read ' + items.length + ' trace excerpts</summary>' + items.map(e =>
        '<figure><figcaption><span class="pill ' + (e.kind === 'agent_message' ? 'p-purp' : 'p-info') + '">' +
        esc(e.kind === 'agent_message' ? 'Outer agent · public message' :
          e.kind === 'agent_action' ? 'Outer agent · command / handoff excerpt' : 'Recorded check · selected result fields') +
        '</span><span>JSONL L' + esc(e.line) + ' · ' + esc(e.item) + '</span></figcaption>' +
        (e.kind === 'agent_message' ? '<blockquote>' + esc(e.text) + '</blockquote>' : '<pre>' + esc(e.text) + '</pre>') +
        '</figure>').join('') + '</details>';
    }
    function outcome(result) {
      const parts = String(result || '').split(' · '), head = parts.shift() || '';
      const cls = /^merged/i.test(head) ? 'p-ok' : /^not accepted/i.test(head) ? 'p-bad' : /^incomplete/i.test(head) ? 'p-warn' : 'p-mut';
      return '<span class="pill ' + cls + '">' + esc(head) + '</span>' + (parts.length ? '<small>' + esc(parts.join(' · ')) + '</small>' : '');
    }
    const jobRows = jobs => jobs.map(j => '<tr><td>' + lemmaLink({file:c.defaultFile, lemma:j.lemma}) +
      '<small>' + esc(j.id) + '</small></td><td class="sb-jobtime">' + esc(j.duration) + '</td><td>' + outcome(j.result) + '</td></tr>').join('');
    const jobTable = jobs => '<div class="sb-table-scroll" role="region" aria-label="Inner job records" tabindex="0"><table class="sb-job-table"><thead><tr><th scope="col">Local obligation / job</th><th scope="col">Job wall time</th><th scope="col">Recorded outcome</th></tr></thead><tbody>' + jobRows(jobs) + '</tbody></table></div>';
    return '<h2>' + esc(story.title) + '</h2><p class="sb-story-deck">' + esc(story.deck) + '</p>' +
      '<div class="sb-process-stats">' + story.stats.map(s => '<div><strong>' + esc(s.value) + '</strong><span>' + esc(s.label) + '</span></div>').join('') + '</div>' +
      '<details class="sb-trace sb-provenance"><summary>What this account is based on</summary><p>' + esc(story.provenance.note) + '</p>' +
      '<dl><div><dt>Frozen archive</dt><dd>' + esc(story.provenance.commit) + '</dd></div><div><dt>Trace</dt><dd>' + esc(story.provenance.tracePath) + '</dd></div>' +
      '<div><dt>Git blob</dt><dd>' + esc(story.provenance.blob) + '</dd></div></dl></details>' +
      '<p class="sb-story-order">' + esc(story.orderNote) + '</p><ol class="sb-story-stages" role="list">' + story.stages.map((s, i) =>
        '<li><div class="sb-stage-heading"><span aria-hidden="true">' + String(i + 1).padStart(2, '0') + '</span><h3>' + esc(s.title) + '</h3></div>' +
        s.paragraphs.map(p => '<p>' + esc(p) + '</p>').join('') +
        '<p class="sb-work-split"><span>Outer / inner</span> ' + esc(s.work) + '</p>' +
        '<div class="sb-process-links" aria-label="Related final proofs">' + s.references.map(lemmaLink).join('') + '</div>' + evidence(s.evidence) + '</li>').join('') + '</ol>' +
      '<section class="sb-inner-record"><h2>What the inner agents actually delivered</h2><p>' + esc(story.jobs.note) + '</p>' + jobTable(story.jobs.merged) +
      '<details class="sb-trace"><summary>The other ' + story.jobs.other.length + ' jobs — incomplete, rejected or cancelled</summary>' + jobTable(story.jobs.other) + '</details>' +
      '<p class="sb-footnote">' + esc(story.jobs.sourceNote) + '</p></section>';
  }
  function cards() {
    if (!cases.length) return '';
    return '<section class="proof-cases" aria-label="End-to-end proof cases"><h3>End-to-end case studies</h3>' +
      '<div class="proof-case-grid">' + cases.map(c =>
        '<article class="proof-case-card"><div class="case-head"><span class="case-icon" aria-hidden="true">' +
        esc(String(c.title).replace(/[^A-Za-z0-9]/g, '').slice(0, 2).toUpperCase()) + '</span>' +
        '<span class="pill p-ok">✓ Verified</span><span class="pill p-mut">' + esc(c.protocol) + '</span></div>' +
        '<h4>' + esc(c.title) + '</h4><p>' + esc(c.scope) + '</p>' +
        '<div class="case-models"><span class="k">outer</span>' + esc(c.outer) + '<span class="k">inner</span>' + esc(c.inner) + '</div>' +
        (c.caveat ? '<div class="case-caveat">' + esc(c.caveat) + '</div>' : '') +
        '<div class="case-time">' + esc(c.time) + '<span class="case-meta">' + esc(c.timeLabel) + '</span></div>' +
        '<div class="case-actions"><a class="case-btn" href="#case/' + encodeURIComponent(c.id) + '">Browse proofs →</a>' +
        '<a class="case-btn alt" href="' + routeHash(c.id, c.defaultFile, '', 'process') + '">Agent process</a></div></article>'
      ).join('') + '</div><p class="case-note">These cases concern the supplied formal models and their declared assumptions. ' +
      'Run-specific models and clocks are shown; these are not controlled speed comparisons.</p></section>';
  }
  const shell = `<div class="proof-library"><main class="sb-page">
    <a class="sb-back" href="#bench">← All benchmark cases</a>
    <div class="sb-head" style="margin-top:18px"><div><div class="sb-eyebrow">End-to-end case study</div><h1 id="sb-title"></h1></div>
    <label class="sb-label">Case study <select id="sb-case" aria-label="Case study"></select></label></div>
    <p class="sb-subhead"><span class="sb-status">✓ Archived verification passed</span><span id="sb-case-meta"></span></p>
    <nav class="sb-tabs" aria-label="Case study sections"></nav>
    <section id="sb-browser" class="sb-browser" aria-label="Files, lemmas and proof source">
      <aside class="sb-files" aria-label="Proof files"><div class="sb-colhead"><span>Files</span><span id="sb-filecount"></span></div><div id="sb-files" class="sb-files-list"></div><p class="sb-file-note" id="sb-file-note"></p></aside>
      <aside class="sb-outline" aria-label="Lemma outline"><div class="sb-colhead"><span>Lemmas</span><span id="sb-lemmacount"></span></div><div id="sb-outline"></div></aside>
      <article class="sb-reader" id="sb-reader" aria-live="polite"><div class="sb-breadcrumb"><button id="sb-back" type="button" class="sb-back">← Back</button><span id="sb-breadcrumb"></span></div><h2 id="sb-symbol"></h2><p class="sb-origin" id="sb-origin"></p>
      <div class="sb-readerbar"><button type="button" class="sb-switch" data-mode="lemma">Lemma & proof</button><button type="button" class="sb-switch" data-mode="file">File source</button><a class="sb-download" id="sb-download" download>Download file ↓</a></div><div id="sb-source"></div></article>
    </section><section id="sb-process" class="sb-summary" hidden></section><section id="sb-verification" class="sb-summary" hidden></section>
    <footer class="sb-footer"><span>Original source lines · statements and complete proofs</span><span>Historical configuration shown for each case</span></footer>
  </main></div>`;

  async function mount(host, hash) {
    const serial = ++generation;
    const route = parseRoute(hash);
    const c = route && cases.find(c => c.id === route.caseId);
    if (!c) { host.innerHTML = '<div class="empty">Case not available in this build. <a href="#bench">Return to benchmark</a></div>'; return; }
    host.innerHTML = '<div class="empty" role="status">Loading proof files…</div>';
    let data;
    try {
      if (!loaded.has(c.id)) loaded.set(c.id, fetch('./case_studies/' + encodeURIComponent(c.id) + '/source.json')
        .then(response => { if (!response.ok) throw new Error('HTTP ' + response.status); return response.json(); })
        .catch(error => { loaded.delete(c.id); throw error; }));
      data = await loaded.get(c.id);
    } catch (error) {
      if (serial === generation && location.hash === hash) host.innerHTML = '<div class="empty" role="alert">Could not load this proof library: ' + esc(error.message) + '. <a href="#bench">Return to benchmark</a></div>';
      return;
    }
    if (serial !== generation || location.hash !== hash) return;
    const fileId = route.fileId || c.defaultFile, f = data[fileId];
    if (!f) { host.innerHTML = '<div class="empty">Unknown source file. <a href="#case/' + esc(c.id) + '">Open this case</a></div>'; return; }
    let l = route.lemmaId && f.lemmas.find(l => l.id === route.lemmaId);
    const fileMode = /^source(?:-\d+)?$/.test(route.lemmaId || '') || !f.lemmas.length;
    if (route.lemmaId && !fileMode && !l) { host.innerHTML = '<div class="empty">Unknown lemma. <a href="' + routeHash(c.id, fileId, '') + '">Open this file</a></div>'; return; }
    if (!l && !fileMode) l = f.lemmas.find(l => l.name === c.defaultLemma) || f.lemmas.find(l => l.name === 'conclusion') || f.lemmas[0];
    const mode = fileMode ? 'file' : 'lemma';
    const page = Math.min(Math.max(0, route.page), Math.max(0, Math.ceil(f.lines.length / 100) - 1));
    host.innerHTML = shell;
    const root = host.querySelector('.proof-library'), q = selector => root.querySelector(selector);
    q('#sb-title').textContent = c.title;
    q('#sb-case-meta').textContent = c.meta;
    q('#sb-case').innerHTML = cases.map(item => '<option value="' + esc(item.id) + '">' + esc(item.title) + '</option>').join('');
    q('#sb-case').value = c.id;
    q('#sb-filecount').textContent = c.files.length;
    q('#sb-file-note').textContent = c.note;
    q('#sb-files').innerHTML = c.files.map(item => '<button type="button" data-file="' + esc(item.id) + '" aria-current="' + (fileId === item.id) + '"><span class="sb-filename">' + esc(item.path).replace(/\//g, '/<wbr>') + '</span><span class="sb-filerole pill ' + (/target/i.test(item.role) ? 'p-ok' : 'p-mut') + '">' + esc(item.role) + '</span><span class="sb-filemeta">' + data[item.id].lines.length.toLocaleString() + ' file lines</span></button>').join('');
    q('#sb-lemmacount').textContent = f.lemmas.length;
    const groups = []; for (let i = 0; i < f.lemmas.length; i += 20) groups.push(f.lemmas.slice(i, i + 20));
    q('#sb-outline').innerHTML = groups.length ? groups.map(g => '<details class="sb-group" ' + (g.some(x => l && x.id === l.id) ? 'open' : '') + '><summary>L' + g[0].start + '–L' + g[g.length - 1].end + ' · ' + g.length + ' lemmas</summary>' + g.map(x => '<button type="button" class="sb-lemma" data-lemma="' + esc(x.id) + '" aria-current="' + Boolean(l && x.id === l.id) + '">' + esc(x.name) + '</button>').join('') + '</details>').join('') : '<p class="sb-muted">No lemma declarations. Browse the definitions in File source.</p>';
    q('#sb-breadcrumb').textContent = f.path + (mode === 'lemma' && l ? ' / ' + l.name : '');
    q('#sb-symbol').textContent = mode === 'lemma' && l ? l.name : f.path;
    q('#sb-origin').textContent = mode === 'lemma' && l ? l.origin + ' · source L' + l.start + '–L' + l.end : f.role + ' · ' + f.lines.length.toLocaleString() + ' lines in this complete file';
    q('#sb-download').href = './case_studies/' + f.download.split('/').map(encodeURIComponent).join('/');
    q('#sb-download').download = f.path.split('/').pop();
    root.querySelectorAll('[data-mode]').forEach(b => { b.setAttribute('aria-pressed', b.dataset.mode === mode); b.disabled = b.dataset.mode === 'lemma' && !f.lemmas.length; });
    const references = sourceReferences(f, l), byName = new Map(references.map(x => [x.name, x]));
    function code(lines, start, link = false) {
      return '<div class="sb-code">' + lines.map((line, i) => '<div class="sb-line"><span class="sb-line-number">' + (start + i) + '</span><span class="sb-line-text">' + line.split(/([A-Za-z_][A-Za-z0-9_']*)/).map(t => link && byName.has(t) ? '<button type="button" class="sb-ref" data-lemma="' + esc(byName.get(t).id) + '">' + esc(t) + '</button>' : /^(lemma|proof|qed|have|by|apply|rewrite|move|exact|smt|module|type|op|require|import)$/.test(t) ? '<span class="sb-keyword">' + esc(t) + '</span>' : esc(t)).join('') + '</span></div>').join('') + '</div>';
    }
    if (mode === 'file') {
      const start = page * 100, end = Math.min(f.lines.length, start + 100);
      q('#sb-source').innerHTML = '<div class="sb-pager"><button data-page="' + (page - 1) + '" ' + (!page ? 'disabled' : '') + '>← Previous</button><span>Source L' + (start + 1) + '–L' + end + '</span><button data-page="' + (page + 1) + '" ' + (end === f.lines.length ? 'disabled' : '') + '>Next →</button></div>' + code(f.lines.slice(start, end), start + 1) + '<p class="sb-footnote">Original file source, including model definitions, modules and non-lemma declarations. Download includes the complete file.</p>';
    } else if (!l.proofStart) {
      q('#sb-source').innerHTML = '<p class="sb-footnote">This declaration does not have a separately indexed proof block. Open File source to read its original context.</p>' + code(f.lines.slice(l.start - 1, l.start), l.start);
    } else {
      const statement = code(l.statement.split('\n'), l.start);
      q('#sb-source').innerHTML = (l.statement.split('\n').length > 20 ? '<details class="sb-details"><summary>Statement · ' + l.statement.split('\n').length + ' source lines</summary>' + statement + '</details>' : '<div class="sb-section-title">Statement</div>' + statement) +
        '<div class="sb-section-title">Proof <span>' + l.bodyLines + ' body lines · complete block below</span></div>' + code(l.proof.split('\n'), l.proofStart, true) +
        (references.length ? '<div class="sb-section-title">Referenced lemmas in this file</div><div class="sb-used">' + references.map(x => '<button type="button" data-lemma="' + esc(x.id) + '">' + esc(x.name) + ' →</button>').join('') + '</div><p class="sb-footnote">Name-based source links for browsing, not an exhaustive or semantically resolved dependency graph.</p>' : '');
    }
    q('.sb-tabs').innerHTML = tabs.map((tab, i) => '<button type="button" data-tab="' + tab + '" aria-pressed="' + (route.tab === tab) + '">' + ['Proof browser', 'Agent process', 'Verification'][i] + '</button>').join('');
    q('#sb-process').innerHTML = processView(c, data);
    q('#sb-verification').innerHTML = '<h2>Artifact verification and scope</h2><dl>' + c.evidence.map(e => '<div class="sb-evidence-row"><dt>' + esc(e[0]) + '</dt><dd>' + esc(e[1]) + '</dd></div>').join('') + '</dl><p class="sb-footnote">The website displays archived verification records; opening a file does not rerun EasyCrypt.</p>';
    tabs.forEach(tab => { q('#sb-' + tab).hidden = tab !== route.tab; });
    root.addEventListener('click', event => {
      const b = event.target.closest('button'); if (!b || b.disabled || !root.contains(b)) return;
      if (b.dataset.file) location.hash = routeHash(c.id, b.dataset.file, '');
      else if (b.dataset.lemma) location.hash = routeHash(c.id, fileId, b.dataset.lemma);
      else if (b.dataset.tab) location.hash = routeHash(c.id, fileId, mode === 'file' ? 'source-' + page : l.id, b.dataset.tab);
      else if (b.dataset.mode) location.hash = routeHash(c.id, fileId, b.dataset.mode === 'file' ? 'source-' + Math.floor((((l && l.start) || 1) - 1) / 100) : '');
      else if (b.hasAttribute('data-page')) location.hash = routeHash(c.id, fileId, '', 'browser', Number(b.dataset.page));
      else if (b.id === 'sb-back') { if (history.length > 1) history.back(); else location.hash = '#bench'; }
    });
    q('#sb-case').addEventListener('change', event => { location.hash = '#case/' + encodeURIComponent(event.target.value); });
  }
  global.ShannonCases = {cards, mount, hasCases: () => cases.length > 0, cancel: () => { generation++; }};
  if (typeof module !== 'undefined' && module.exports) module.exports = {esc, parseRoute, routeHash, sourceReferences, processView};
})(typeof window === 'undefined' ? globalThis : window);
