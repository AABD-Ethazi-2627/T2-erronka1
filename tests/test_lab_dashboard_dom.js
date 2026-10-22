// Run in the generated browser.html: await runCG19DomRegression(view, spec, fixture).
// This deliberately keeps one SVG alive and never calls toSVG() on that view.
async function runCG19DomRegression(view, spec, fixture) {
  const root = document.querySelector('#chart svg');
  const failures = [], samples = [], pageCoverage = [], covered = new Set();
  const check = (ok, message) => { if (!ok) failures.push(message); };
  const guides = node => [...node.querySelectorAll('.role-axis,.role-legend,.role-title-text,.role-title-subtitle')]
    .map(e => ({role: e.getAttribute('class'), label: e.getAttribute('aria-label'),
      ariaRole: e.getAttribute('role'), roleDescription: e.getAttribute('aria-roledescription'),
      hidden: e.getAttribute('aria-hidden')}));
  let width = 1100, height = 480;
  async function sample(name) {
    const page = view.signal('page'), size = view.signal('pageSize');
    const response = JSON.parse(JSON.stringify(view.data('response')));
    const expected = response.flatMap(r => r.buckets).map(d => d.key.join(' / ')).sort();
    const ids = view.data('page_groups').map(d => d.group);
    const label = `IDs: ${ids.length}/${expected.length} recuperados · página ${page}/${Math.max(1, Math.ceil(expected.length / size))}`;
    const current = guides(root);
    check(current.length === 5 && current.every(d => d.ariaRole === 'graphics-symbol' &&
      d.roleDescription && d.label && d.hidden !== 'true'), `${name}: guide semantics`);
    check(root === document.querySelector('#chart svg'), `${name}: SVG replaced`);
    check(root.querySelector('.role-title-text').textContent === label, `${name}: visible title`);
    check(current.some(d => d.label === `Title text '${label}'`), `${name}: stale title ARIA`);
    check(JSON.stringify(ids) === JSON.stringify(expected.slice((page - 1) * size, page * size)), `${name}: identities/order`);
    check(!/NaN|Infinity|undefined/.test(root.outerHTML), `${name}: invalid SVG`);
    for (const axis of ['x', 'y']) {
      const domain = view.scale(axis).domain().map(Number);
      check(domain.every(Number.isFinite) && domain[1] > domain[0], `${name}: ${axis} domain`);
    }
    // A fresh DOM is the oracle for Vega's generated domain/legend captions.
    // It must not replace or re-render the incremental DOM under examination.
    const host = document.createElement('div');
    host.hidden = true;
    document.body.append(host);
    const fresh = structuredClone(spec);
    fresh.data[0].values = response;
    delete fresh.data[0].url;
    delete fresh.data[0].format;
    const reference = new vega.View(vega.parse(fresh), {renderer: 'svg'})
      .initialize(host).width(width).height(height);
    try {
      await reference.runAsync();
      await reference.signal('pageSize', size).signal('page', page).runAsync();
      check(JSON.stringify(current) === JSON.stringify(guides(host)), `${name}: stale guide ARIA`);
    } finally { reference.finalize(); host.remove(); }
    const points = [...root.querySelectorAll('.mark-symbol path[aria-label]')];
    check(points.every(p => ids.some(id => p.getAttribute('aria-label').startsWith(id + '; '))), `${name}: stale point ARIA`);
    samples.push({name, page, size, total: expected.length, ids, guides: current,
      xDomain: view.scale('x').domain().map(Number), yDomain: view.scale('y').domain().map(Number)});
  }
  async function response(value) {
    await view.change('response', vega.changeset().remove(() => true).insert([value])).runAsync();
  }
  await view.signal('page', 1).runAsync();
  await sample('100-page1');
  for (let page = 1; page <= 20; page++) {
    await view.signal('page', page).runAsync();
    const ids = view.data('page_groups').map(d => d.group);
    ids.forEach(id => covered.add(id));
    const current = guides(root);
    check(current.some(d => d.label === `Title text 'IDs: 5/100 recuperados · página ${page}/20'`), `page ${page}: title ARIA`);
    const legend = current.find(d => d.role.includes('role-legend')).label;
    check(ids.every(id => legend.includes(id)), `page ${page}: legend ARIA`);
    const points = [...root.querySelectorAll('.mark-symbol path[aria-label]')].map(p => p.getAttribute('aria-label'));
    check(points.length === 40 && points.every(p => ids.some(id => p.startsWith(id + '; '))), `page ${page}: points ARIA`);
    pageCoverage.push({page, ids, pointDescriptions: points.length});
  }
  check(covered.size === 100, '100 identities over 20 pages');
  await sample('100-page20');
  await response(fixture(31));
  check(view.signal('page') === 7, '31: clamp to last page');
  await sample('31-page7-clamp');
  await view.signal('page', 1).runAsync();
  await sample('31-page1');
  await response(fixture(1));
  await sample('1-page1');
  await response(fixture(0));
  await sample('0-page1');
  const reversed = fixture(100);
  reversed.buckets.reverse();
  await response(reversed);
  await sample('100-reverse-page1');
  await view.signal('page', 20).runAsync();
  await sample('100-reverse-page20');
  const shifted = fixture(100);
  shifted.sum_other_doc_count = 42;
  shifted.buckets.forEach(d => d.series.buckets.forEach(b => {
    b.key += 86400000;
    for (const sensor of ['air', 'process']) if (b[sensor].value !== null) b[sensor].value += 100;
  }));
  await response(shifted);
  await sample('100-new-window-and-omissions');
  await view.signal('pageSize', 10).runAsync();
  check(view.signal('page') === 10, 'size: clamp to last page');
  await sample('size10-page10');
  await view.signal('pageSize', 5).signal('page', 1).runAsync();
  await response(fixture(1, true));
  await sample('null-temperatures');
  await response(fixture(1, false, true));
  await sample('single-time-constant-values');
  await response(fixture(100));
  for (const dimensions of [[600, 400], [1100, 480], [1600, 600]]) {
    [width, height] = dimensions;
    await view.width(width).height(height).runAsync();
    await sample(`resize-${width}`);
  }
  await view.signal('page', 20).runAsync();
  await sample('final-page20');
  return {pass: failures.length === 0, failures, sameSVG: root === document.querySelector('#chart svg'),
    vega: vega.version, covered: covered.size, pages: 20, pageCoverage, samples};
}
