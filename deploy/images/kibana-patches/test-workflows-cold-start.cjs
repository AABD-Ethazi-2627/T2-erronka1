'use strict';
const assert = require('node:assert/strict');
const { rollDataStreamIfRequired } = require('/usr/share/kibana/node_modules/@kbn/workflows-execution-engine/server/lib/data_streams/roll_data_stream_if_required.js');
const { MANAGED_INDEX_MAPPINGS_VERSION_META_FIELD: field } = require('/usr/share/kibana/node_modules/@kbn/workflows-execution-engine/server/lib/data_streams/constants.js');
const logger = { debug() {}, info() {}, warn() {} };
async function run(mapping, transportError) {
  const rollovers = [];
  const esClient = { indices: {
    async getMapping(options) {
      if (transportError) throw transportError;
      // Model the actual ES response for an explicit absent stream: wildcard
      // allow_no_indices does not make an explicit missing name optional.
      if (mapping === null && !options.ignore_unavailable) {
        throw new Error('index_not_found_exception');
      }
      assert.equal(options.index, '.workflows-test');
      assert.equal(options.allow_no_indices, true);
      return mapping || {};
    },
    async rollover(options) { rollovers.push(options); },
  } };
  const value = await rollDataStreamIfRequired({ logger, esClient,
    dataStreamName: '.workflows-test', targetManagedIndexMappingsVersion: 2 });
  return { value, rollovers };
}
async function main() {
  assert.deepEqual(await run(null), { value: false, rollovers: [] });
  for (const version of [2, 3]) {
    assert.deepEqual(await run({ backing: { mappings: { _meta: { [field]: version } } } }),
      { value: false, rollovers: [] });
  }
  assert.deepEqual(await run({ backing: { mappings: { _meta: { [field]: 1 } } } }),
    { value: true, rollovers: [{ alias: '.workflows-test', lazy: true }] });
  for (const message of ['security_exception: forbidden', 'connection refused']) {
    const error = new Error(message);
    await assert.rejects(() => run(null, error), candidate => candidate === error);
  }
  console.log('Workflows absent/current/newer/older streams and transport error controls passed');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
