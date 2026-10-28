const assert = require('assert/strict');
const path = require('path');
const root = process.argv[2] || path.join(__dirname, 'node_modules/deepmerge-patched');
for (const file of ['dist/cjs.js', 'dist/umd.js']) {
  const merge = require(path.join(root, file));
  const poisoned = JSON.parse('{"__proto__":{"injected":true},"ok":1}');
  for (const [target, source] of [[poisoned, {}], [Object.create(null), poisoned], [{ nested: poisoned }, {}]]) {
    const result = merge(target, source);
    const checked = result.nested || result;
    assert.equal(Object.getPrototypeOf(checked), Object.prototype, file);
    assert.equal(checked.injected, undefined, file);
    assert.equal({}.injected, undefined, file);
  }
  assert.deepEqual(merge({ a: [1], b: { c: 2 } }, { a: [3], b: { d: 4 } }), { a: [1, 3], b: { c: 2, d: 4 } });
  const symbol = Symbol('own');
  assert.equal(merge({}, { [symbol]: 7 })[symbol], 7);
  assert.deepEqual(merge({ a: 1 }, { a: 2 }, { customMerge: () => () => 9 }), { a: 2 });
}
console.log('deepmerge prototype poisoning regressions and ordinary merge behavior pass');
