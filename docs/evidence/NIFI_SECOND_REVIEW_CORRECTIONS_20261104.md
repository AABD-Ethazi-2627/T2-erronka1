# NiFi second-review corrections and Hadoop candidate

Status: **local preparation; final immutable-source verification pending**.
The implementation and focused checks below do not approve a runtime plan,
image, exception, merge, SMB or human acceptance.

The archived independent reviews refer to immutable historical heads:
[writer/Maven/RabbitMQ `f4e32bf`](CLAUDE_NIFI_OCCURRENCE_TRANSPORT_RECHECK_20261104.md)
and [Jackson `cd811e3`](CLAUDE_NIFI_JACKSON_REVIEW_20261104.md).
Neither review covers later fixes. Both find no Critical/High issues, but identify
medium defects in future Maven semantics and Jackson source/coverage/test guards.

Implemented corrections:

- Exclusions apply below their declaring dependency. Managed optionality does
  not hide a required artifact. Unmodelled interpolated BOM values, inherited
  management overrides and combined managed/local exclusions fail closed.
  Against cached real Maven 3.9.11, all 30 reviewer fixtures either agree
  (15) or are rejected (15); none returns a divergent successful closure.
- The writer checks all sibling contents, ordering, comments and preserved
  metadata before publication, including zero external attributes. It rejects
  blocked ancestry/replacements, no-ops, retained selected old hashes, directory
  payloads, preambles, ambiguous names and local/central header contradictions.
- Jackson verifies every source root, rejects symlinks/extra/missing/drifted
  files, records class-based relocated carriers and pairs core/databind atomically
  per namespace/version/context. ABI and unknown-consumer blocks remain.
- Java subprocesses use allowlisted environments. Version reporting uses the
  same bounded launcher; malformed AMQP peers require the actual protocol cause.
  Jackson explicitly pins JDK21, derives annotations from its closure, checks
  loaded module versions and revalidates cached inputs afterward. Historical
  Jackson evidence used JDK27; the new proof must not relabel that execution.

The class inventory now explicitly lists **four AWS and three Azure relocated
Jackson occurrences** outside the Maven scanner's mapped objects. The independent
review found AWS 2.21.4 and an unbounded DataInput token error. Azure's subset
version is unknown. Neither finding establishes runtime reachability or absence
of other renamed/obfuscated copies. A zero metadata-scan count cannot close these
unassessed carriers. Hazelcast/Parquet still account for 41 of the 44 Jackson
tuples in the last completed nested scan; they remain wrapper-rebuild work.

Hadoop child `5df3ca8`, incorporated as `7b6f3b6`, prepares an explicit local
3.5.0 consumer correction. The parent reproduces its candidate SHA-256
`599a61b22f6cde7c12dce8a1240217d2285f57e619c1ebc051e0a3414aa52fdb`,
20 Java commands and 70 cases on each old/fixed Snappy, both half-fix negatives
and the fixed Snappy output-space guards. It changes capacity and buffer
lifecycle; official Snappy bytes, symbolic Hadoop ABI/class major and unrelated
JAR contents/attributes remain unchanged. All 215 originals remain unchanged.
This is a standalone candidate, not an Apache release, rooted archive patch,
classloader acceptance or permission to lift the nine-Snappy blocked group.

Focused tests pass on the working source; final repeat, inventory/overlay checks,
source bindings and exact counts will be recorded after freezing this commit.
Current metadata-scan, wrapper/SDK, classloader, image, CI/GitHub review,
CG32-resource, NiFi/SMB and human gates remain open. No new exception is added.
