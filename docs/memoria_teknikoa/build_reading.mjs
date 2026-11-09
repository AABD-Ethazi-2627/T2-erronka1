// Offline Markdown -> standalone reading HTML. Uses the installed make-pdf renderer dependency.
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
const here = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(path.join(os.homedir(), '.agents/skills/make-pdf/vendor/package.json'));
const { marked } = require('marked');
const headings = [];
const escape = value => value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('"', '&quot;');
const renderer = new marked.Renderer();
let count = 0;
renderer.heading = function(token) {
  const id = `atala-${++count}`;
  headings.push({id, depth: token.depth, text: token.text});
  return `<h${token.depth} id="${id}">${this.parser.parseInline(token.tokens)}</h${token.depth}>`;
};
let body = marked.parse(fs.readFileSync(path.join(here, 'MEMORIA_TEKNIKOA_EU.md'), 'utf8'), {gfm:true, renderer});
body = body.replace(/src="([^"]+\.svg)"/g, (_, name) => `src="data:image/svg+xml;base64,${fs.readFileSync(path.join(here, name)).toString('base64')}"`);
const toc = headings.filter(h => h.depth === 1 || h.text.startsWith('Zereginak!')).map(h => `<a class="depth-${h.depth}" href="#${h.id}">${escape(h.text)}</a>`).join('');
const css = `*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#f0f4f7;color:#182f40;font:17px/1.72 system-ui,sans-serif}nav{position:fixed;inset:0 auto 0 0;width:290px;background:#142e40;padding:28px 20px;overflow:auto;color:white}nav strong{font-size:21px}nav a{display:block;color:#dbe8ef;text-decoration:none;font-size:13px;line-height:1.5;padding:6px 0;border-bottom:1px solid #ffffff18}nav a.depth-2{padding-left:12px;font-size:12px}main{margin:30px 35px 50px 325px;max-width:1000px;background:white;padding:50px 60px;border-radius:8px;box-shadow:0 3px 24px #1432470c}h1{font-size:30px;line-height:1.25;border-top:3px solid #196e83;padding-top:24px;margin-top:55px}h1:first-child{border:0;margin-top:0;font-size:39px}h2{font-size:23px;line-height:1.35;margin-top:38px}h3{font-size:19px}p{margin:12px 0 20px}a{color:#0c667f}code{font:0.84em/1.5 monospace;background:#edf2f5;padding:2px 4px;overflow-wrap:anywhere}pre{background:#edf2f5;padding:18px;white-space:pre-wrap}blockquote{border-left:4px solid #3d8094;margin:20px 0;padding:8px 20px;background:#f3f7fa;font-size:16px}table{border-collapse:collapse;width:100%;font-size:14px;margin:25px 0;table-layout:fixed}th,td{border:1px solid #d2dce3;padding:10px;text-align:left;vertical-align:top;overflow-wrap:anywhere}th{background:#e8f1f5}img{max-width:100%;height:auto}li{margin:8px 0}h1,h2,h3{scroll-margin-top:20px}@media(max-width:1000px){nav{position:relative;width:auto;max-height:260px}main{margin:18px;padding:25px;font-size:16px}}@media print{nav{display:none}main{margin:0;padding:0;box-shadow:none}h1{break-before:page}h1:first-child{break-before:auto}h1,h2,h3{break-after:avoid}tr,img{break-inside:avoid}}`;
fs.writeFileSync(path.join(here, 'MEMORIA_TEKNIKOA_EU.html'), `<!doctype html><html lang="eu"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>CNC Guard · Memoria teknikoa</title><style>${css}</style></head><body><nav aria-label="Aurkibidea"><strong>CNC Guard</strong><p>Memoria teknikoa · 2026-11-05</p>${toc}</nav><main>${body}</main></body></html>`);
console.log('HTML created with embedded figures and Basque navigation.');
