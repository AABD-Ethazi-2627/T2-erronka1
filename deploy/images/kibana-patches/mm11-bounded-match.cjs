'use strict';
// Integration adapter only. Official Minimatch bytes are never modified.
const official = require('minimatch');
const BRACE_EXPAND_MAX = 1024;

class BoundedMinimatch extends official.Minimatch {
  constructor(pattern, options = {}) {
    const bounded = { ...options, braceExpandMax: BRACE_EXPAND_MAX };
    // Detect overflow before compiling, rather than silently truncating a
    // negated allowlist into a broader match. This array is never cached.
    if (official.braceExpand(pattern, { ...bounded, braceExpandMax: BRACE_EXPAND_MAX + 1 }).length > BRACE_EXPAND_MAX) {
      throw new RangeError('CNC Guard matcher expansion budget exceeded (1024)');
    }
    super(pattern, bounded);
  }
}

const minimatch = (name, pattern, options) => new BoundedMinimatch(pattern, options).match(name);
minimatch.Minimatch = BoundedMinimatch;
exports.minimatch = minimatch;
exports.Minimatch = BoundedMinimatch;
exports.BRACE_EXPAND_MAX = BRACE_EXPAND_MAX;
