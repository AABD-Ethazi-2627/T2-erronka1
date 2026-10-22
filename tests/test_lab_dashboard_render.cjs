// Offline Vega regression. Supply the existing runtime; no network or service writes.
// CG19_VEGA_MODULE=/absolute/path/to/node_modules/vega node tests/test_lab_dashboard_render.cjs
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vega = require(process.env.CG19_VEGA_MODULE || 'vega');
const root = path.resolve(__dirname, '..');
const out = path.resolve(process.env.CG19_RENDER_OUTPUT || path.join(root, 'outputs/cg19-regression'));
const objects = fs.readFileSync(path.join(root, 'kibana/cg19-review-source.ndjson'), 'utf8').trim().split('\n').map(JSON.parse);
const original = JSON.parse(JSON.parse(objects.find(o => o.id === 'cnc-cg19-temperature-v2').attributes.visState).params.spec);

function fixture(count, emptyValues = false, singleTime = false) {
  return {buckets: Array.from({length: count}, (_, i) => ({
    key: [`CNC-${String(i).padStart(3, '0')}`, i % 2 ? 'smb_csv' : 'lab_fixture'],
    doc_count: singleTime ? 1 : 4,
    series: {buckets: (singleTime ? [0] : [0, 1, 2, 3, 4]).map(hour => ({
      key: Date.UTC(2026, 9, 21, hour), doc_count: hour === 2 ? 0 : 1,
      air: {value: emptyValues || hour === 2 ? null : 300 + i / 10 + hour},
      process: {value: emptyValues || hour === 2 ? null : (singleTime ? 300 : 310) + i / 10 + hour},
    }))},
  })), sum_other_doc_count: count === 100 ? 17 : 0};
}

function checkNumbers(item) {
  for (const [key, value] of Object.entries(item)) {
    if (['x', 'y', 'x2', 'y2', 'width', 'height'].includes(key) && typeof value === 'number') {
      assert(Number.isFinite(value), `Non-finite scene ${key}: ${value}`);
    }
  }
  if (item.marktype === 'line' && item.items.length) {
    assert.deepEqual(item.items.map(d => d.defined), [true, true, false, true, true], 'Hourly gap must break the line');
  }
  for (const child of item.items || []) checkNumbers(child);
}

async function run() {
  fs.mkdirSync(out, {recursive: true});
  const reports = [];
  const summary = JSON.parse(JSON.parse(objects.find(o => o.id === 'cnc-cg19-summary-v2').attributes.visState).params.spec);
  for (const width of [250, 600, 1100]) {
    const spec = structuredClone(summary);
    spec.data[0].values = [{doc_count: 100, alerts: {doc_count: 66}, classified: {doc_count: 100},
      machines: {value: 100}, latest: {value: Date.UTC(2026, 9, 22, 8)}, oldest: {value: Date.UTC(2026, 9, 22, 8)}}];
    delete spec.data[0].url;
    delete spec.data[0].format;
    const warnings = [];
    const logger = vega.logger(vega.Warn);
    logger.warn = (...args) => warnings.push(args.join(' '));
    logger.error = (...args) => warnings.push(args.join(' '));
    const view = new vega.View(vega.parse(spec), {renderer: 'none', logger}).width(width).height(280);
    try {
      await view.runAsync();
      const group = view.scenegraph().root.items[0];
      const svg = await view.toSVG();
      fs.writeFileSync(path.join(out, `summary-${width}.svg`), svg);
      const viewport = svg.match(/<svg[^>]* width="([\d.]+)" height="([\d.]+)"/);
      const origin = view.origin().map((value, axis) => value + view.padding()[axis ? 'top' : 'left']);
      assert(Number(viewport[1]) <= width + 0.1, 'Summary must not expand horizontally');
      for (const mark of group.items) {
        assert(mark.bounds.y2 + origin[1] <= Number(viewport[2]) + 0.1, `Summary prose clipped vertically at ${width}`);
        // Node's font fallback estimates differ from browser glyph metrics.
        // Check lossless wrapping here; measure actual text bounds in live Kibana.
        for (const item of mark.items) {
          assert.equal(item.text.join(' ').replace(/\s+/g, ' '), item.description.replace(/\s+/g, ' '));
          if (width === 250) assert(item.text.every(line => line.length < 30));
        }
      }
      assert(svg.includes('aria-label="Observaciones en el filtro: 100"'));
      assert(svg.includes('aria-label="Edad desde timestamp de evento; no latencia de ingestión."'));
      assert.deepEqual(warnings, []);
    } finally { view.finalize(); }
  }
  for (const [width, height] of [[600, 400], [1100, 480], [1600, 600]]) {
    for (const count of [0, 1, 31, 100]) {
      const spec = structuredClone(original);
      spec.data[0].values = [fixture(count)];
      delete spec.data[0].url;
      delete spec.data[0].format;
      const warnings = [];
      const logger = vega.logger(vega.Warn);
      logger.warn = (...args) => warnings.push(args.join(' '));
      logger.error = (...args) => warnings.push(args.join(' '));
      const view = new vega.View(vega.parse(spec), {renderer: 'none', logger}).width(width).height(height);
      try {
        await view.runAsync();
        const covered = new Set();
        const pages = Math.max(1, Math.ceil(count / 5));
        let minPlotHeight = Infinity;
        for (let page = 1; page <= pages; page++) {
          await view.signal('page', page).runAsync();
          const identities = view.data('page_groups').map(d => d.group);
          identities.forEach(id => covered.add(id));
          assert.equal(identities.length, Math.min(5, Math.max(0, count - (page - 1) * 5)));
          assert.equal(new Set(identities.map(id => view.scale('color')(id))).size, identities.length);
          assert.equal(new Set(identities.map(id => view.scale('shape')(id))).size, identities.length);
          assert.equal(view.data('points').length, identities.length * 8);
          assert(view.width() >= 450, `Plot too narrow: ${view.width()}`);
          assert(view.height() >= 120, `Plot too short: ${view.height()}`);
          minPlotHeight = Math.min(minPlotHeight, view.height());
          for (const scale of ['x', 'y']) {
            const domain = view.scale(scale).domain().map(Number);
            assert(domain.every(Number.isFinite));
            assert(domain[1] > domain[0]);
          }
          checkNumbers(view.scenegraph().root);
          const svg = await view.toSVG();
          assert(!/NaN|Infinity|undefined|…/.test(svg), 'Invalid or truncated SVG');
          for (const id of identities) assert(svg.includes(`>${id}</text>`), `Missing visible legend: ${id}`);
          if (count) assert(svg.includes('aria-label="CNC-') && svg.includes('; aire; UTC ') && svg.includes('; proceso; UTC '));
          if (!count) assert(svg.includes('Sin datos en el filtro / ventana'));
          if (count === 100) assert(svg.includes('eventos fuera del top: 17'));
          // Top-level bounds include axes, title, legends and marks. Fit must keep them inside.
          const group = view.scenegraph().root.items[0];
          const origin = view.origin().map((value, axis) => value + view.padding()[axis ? 'top' : 'left']);
          const b = {x1: group.bounds.x1 + origin[0], y1: group.bounds.y1 + origin[1],
            x2: group.bounds.x2 + origin[0], y2: group.bounds.y2 + origin[1]};
          assert(b.x1 >= -0.1 && b.y1 >= -0.1 && b.x2 <= width + 0.1 && b.y2 <= height + 0.1,
            `Clipped scene: ${JSON.stringify(b)} at ${width}x${height}`);
          const name = `temperature-${count}-${width}x${height}-page-${page}`;
          fs.writeFileSync(path.join(out, `${name}.svg`), svg);
          if (process.env.CG19_RESVG_MODULE) {
            const {Resvg} = require(process.env.CG19_RESVG_MODULE);
            const font = process.env.CG19_FONT_FILE ? {loadSystemFonts: false, fontFiles: [process.env.CG19_FONT_FILE], sansSerifFamily: 'Arial', defaultFontFamily: 'Arial'} : undefined;
            fs.writeFileSync(path.join(out, `${name}.png`), new Resvg(svg, {background: 'white', font}).render().asPng());
          }
        }
        assert.equal(covered.size, count, 'Every retrieved identity must be reachable');
        // A filter can reduce the response while the user remains on page 20.
        await view.signal('page', 20).runAsync();
        if (count < 100) assert((await view.toSVG()).includes(count ? 'Página vacía:' : 'Sin datos en el filtro'));
        if (count === 100) {
          await view.change('response', vega.changeset().remove(() => true).insert([fixture(1)])).runAsync();
          assert((await view.toSVG()).includes('Página vacía:'));
          await view.signal('page', 1).runAsync();
          assert.equal(view.data('page_groups').length, 1);
          await view.change('response', vega.changeset().remove(() => true).insert([fixture(0)])).runAsync();
          assert((await view.toSVG()).includes('Sin datos en el filtro / ventana'));
          assert(!/NaN|Infinity/.test(await view.toSVG()));
        }
        assert.deepEqual(warnings, []);
        reports.push({count, width, height, pages, covered: covered.size, minPlotHeight, warnings});
      } finally { view.finalize(); }
    }
  }
  // Nonempty groups with no sensor values, and one timestamp with constant values.
  for (const [emptyValues, singleTime] of [[true, false], [false, true]]) {
    const spec = structuredClone(original);
    spec.data[0].values = [fixture(1, emptyValues, singleTime)];
    delete spec.data[0].url;
    delete spec.data[0].format;
    const warnings = [];
    const logger = vega.logger(vega.Warn);
    logger.warn = (...args) => warnings.push(args.join(' '));
    const view = new vega.View(vega.parse(spec), {renderer: 'none', logger}).width(1100).height(480);
    try {
      await view.runAsync();
      const svg = await view.toSVG();
      assert(!/NaN|Infinity/.test(svg));
      assert.deepEqual(warnings, []);
      if (emptyValues) assert(svg.includes('Sin temperaturas en esta página / ventana'));
      for (const scale of ['x', 'y']) {
        const domain = view.scale(scale).domain().map(Number);
        assert(domain.every(Number.isFinite));
        assert(domain[1] > domain[0]);
      }
    } finally { view.finalize(); }
  }
  fs.writeFileSync(path.join(out, 'report.json'), JSON.stringify({vega: vega.version, reports}, null, 2) + '\n');
  // Self-contained local browser fixture: the only substituted part is ES transport.
  const browserSpec = structuredClone(original);
  browserSpec.data[0].values = [fixture(100)];
  delete browserSpec.data[0].url;
  delete browserSpec.data[0].format;
  const runtime = fs.readFileSync(path.join(path.dirname(require.resolve(process.env.CG19_VEGA_MODULE || 'vega')), 'vega.min.js'), 'utf8');
  fs.writeFileSync(path.join(out, 'browser.html'), `<!doctype html><html lang="es"><meta charset="utf-8"><title>CG19 · regresión local</title>
<style>body{font:14px Arial;margin:0}p{line-height:1.5}select{font:inherit}select:focus-visible{outline:3px solid #155db1;outline-offset:3px}#chart{max-width:1100px}svg{display:block;background:white}</style>
<p>Fixture sintética de regresión: 100 ID/fuente. Vega ${vega.version}. Render local; importación y filtros Kibana pendientes.</p>
<div id="chart"></div><script>${runtime}</script><script>
window.spec=${JSON.stringify(browserSpec)};
window.view=new vega.View(vega.parse(spec),{renderer:'svg'}).initialize('#chart').width(Math.min(1100,innerWidth)).height(480);
window.ready=view.runAsync().then(()=>console.log('CG19 ready',view.data('groups').length));
</script></html>`);
  console.log(JSON.stringify({vega: vega.version, cases: reports.length, pages: reports.reduce((n, r) => n + r.pages, 0), reports}, null, 2));
}
run().catch(error => {console.error(error); process.exitCode = 1;});
