'use strict';
// Integration adapter only. Official Minimatch bytes are never modified.
const official = require('minimatch');
const BRACE_EXPAND_MAX = 1024;

class BoundedMinimatch extends official.Minimatch {
  constructor(pattern, options = {}) {
    const bounded = { ...options, braceExpandMax: BRACE_EXPAND_MAX };
    // Preserve official comment handling without expanding ignored input.
    if (typeof pattern === 'string' && !bounded.nocomment && pattern.startsWith('#')) {
      super(pattern, bounded);
      return;
    }
    // The official brace expander silently truncates at several internal
    // budgets. Negating a truncated set can broaden an allowlist. Reject
    // this unsupported input class rather than guessing whether it truncated.
    const negations = typeof pattern === 'string' ? /^!+/.exec(pattern)?.[0].length || 0 : 0;
    if (!bounded.nonegate && !bounded.nobrace && negations % 2 && /[{}]/.test(pattern)) {
      throw new RangeError('CNC Guard negated brace patterns are unsupported');
    }
    // Reject row-count overflow before compilation. Other positive-pattern
    // internal limits retain upstream semantics; this preview is never cached.
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
