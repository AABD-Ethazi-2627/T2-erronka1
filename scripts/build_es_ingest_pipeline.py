"""Export the non-mutating ES prediction guard from the current CG03 schema."""

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIPELINE_ID = "cnc-prediction-v1"
EXPORT = ROOT / "elasticsearch/ingest-pipeline.json"
SOURCE = """for (def section : params.sections) {
  def obj = section.path == '' ? ctx : ctx[section.path];
  if (!(obj instanceof Map)) {
    throw new IllegalArgumentException('CG18 object required: ' + section.path);
  }
  for (def name : section.required) {
    if (!obj.containsKey(name) || obj[name] == null) {
      throw new IllegalArgumentException('CG18 required: ' + name);
    }
  }
  for (def name : obj.keySet()) {
    if (!section.rules.containsKey(name)) {
      if (section.path == '' && params.metadata.contains(name)) { continue; }
      throw new IllegalArgumentException('CG18 unknown field: ' + name);
    }
    def rule = section.rules[name];
    def value = obj[name];
    boolean valid = rule.type == 'object' ? value instanceof Map :
      rule.type == 'string' ? value instanceof String :
      rule.type == 'boolean' ? value instanceof Boolean : value instanceof Number;
    if (!valid) { throw new IllegalArgumentException('CG18 type: ' + name); }
    if (rule.containsKey('const') && !rule['const'].equals(value)) {
      throw new IllegalArgumentException('CG18 const: ' + name);
    }
    if (rule.containsKey('enum') && !rule['enum'].contains(value)) {
      throw new IllegalArgumentException('CG18 enum: ' + name);
    }
    if (rule.containsKey('minLength') && value.length() < rule.minLength) {
      throw new IllegalArgumentException('CG18 empty string: ' + name);
    }
    if (rule.type == 'number') {
      double n = value.doubleValue();
      if (!Double.isFinite(n) ||
          (rule.containsKey('minimum') && n < rule.minimum) ||
          (rule.containsKey('maximum') && n > rule.maximum) ||
          (rule.containsKey('exclusiveMinimum') && n <= rule.exclusiveMinimum)) {
        throw new IllegalArgumentException('CG18 range: ' + name);
      }
    }
  }
}
"""


def build():
    common_path = ROOT / "contracts/common.schema.json"
    prediction_path = ROOT / "contracts/prediction.schema.json"
    common = json.loads(common_path.read_text())
    prediction = json.loads(prediction_path.read_text())

    def resolve(definition):
        if "$ref" in definition:
            return common["$defs"][definition["$ref"].rsplit("/", 1)[1]]
        return definition

    def section(path, schema):
        rules = {}
        for name, definition in schema["properties"].items():
            definition = resolve(definition)
            rule = {
                key: value
                for key, value in definition.items()
                if key
                in {
                    "type",
                    "const",
                    "enum",
                    "minimum",
                    "maximum",
                    "exclusiveMinimum",
                    "minLength",
                }
            }
            if "type" not in rule:
                rule["type"] = (
                    "boolean" if isinstance(rule.get("const"), bool) else "string"
                )
            rules[name] = rule
        return {"path": path, "required": schema["required"], "rules": rules}

    return {
        "description": "CG18 prediction shape/current-state guard; "
        "preserves canonical _source. "
        "API owns full JSON Schema validation; strict mapping owns storage types.",
        "version": 1,
        "_meta": {
            "pipeline_id": PIPELINE_ID,
            "contract_sha256": {
                path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in (common_path, prediction_path)
            },
            "mutates_source": False,
        },
        "processors": [
            {
                "script": {
                    "tag": "prediction-contract-guard-v1",
                    "lang": "painless",
                    "source": SOURCE,
                    "params": {
                        "metadata": [
                            "_index",
                            "_id",
                            "_routing",
                            "_version",
                            "_version_type",
                            "_dynamic_templates",
                            "_ingest",
                        ],
                        "sections": [
                            section("", prediction),
                            section("source", common["$defs"]["source"]),
                        ],
                    },
                }
            }
        ],
    }


def render():
    return json.dumps(build(), indent=2, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = render()
    if args.check:
        if EXPORT.read_text(encoding="utf-8") != expected:
            raise SystemExit(
                "Stale ES ingest export; run scripts.build_es_ingest_pipeline"
            )
        print("PASS: ES ingest export matches schema and generator")
    else:
        EXPORT.write_text(expected, encoding="utf-8", newline="\n")
