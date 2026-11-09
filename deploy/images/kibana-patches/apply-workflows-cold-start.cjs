'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { createHash } = require('node:crypto');
// Official v9.5.5 source intentionally skips absent streams after getMapping.
// Explicit names require ignore_unavailable as well as allow_no_indices.
const file = '/usr/share/kibana/node_modules/@kbn/workflows-execution-engine/server/lib/data_streams/roll_data_stream_if_required.js';
const original = fs.readFileSync(file);
assert.equal(createHash('sha256').update(original).digest('hex'),
  'b315a7dce4898c61c6f2dd2840da1ef3b453f82f04da58bd09f800a66f6389be');
const before = '    allow_no_indices: true\n';
const text = original.toString('utf8');
assert.equal(text.split(before).length, 2, 'exact upstream getMapping preimage');
fs.writeFileSync(file, text.replace(before,
  '    allow_no_indices: true,\n    ignore_unavailable: true\n'));
