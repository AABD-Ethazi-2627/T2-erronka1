"""Independent WCAG sRGB checks of the generated palette and rendered SVG paint.

Run unittest discovery, then this file with --render-dir and --report to inspect
the SVG matrix from test_lab_dashboard_render.cjs. No Vega scale colors are read
by the SVG verifier: it checks the actual inherited SVG fill/stroke and opacity.
"""

import argparse
import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "kibana/cg19-review-source.ndjson"


def rgb(color):
    color = color.removeprefix("#")
    if len(color) == 3:
        color = "".join(c * 2 for c in color)
    if len(color) != 6:
        raise AssertionError(f"Unsupported SVG paint: {color}")
    return tuple(int(color[i : i + 2], 16) / 255 for i in (0, 2, 4))


def luminance(channels):
    # https://www.w3.org/TR/WCAG22/#dfn-relative-luminance
    linear = [
        c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels
    ]
    return sum(c * w for c, w in zip(linear, (0.2126, 0.7152, 0.0722), strict=True))


def contrast(foreground, background=(1, 1, 1), alpha=1):
    effective = tuple(
        f * alpha + b * (1 - alpha) for f, b in zip(foreground, background, strict=True)
    )
    a, b = sorted((luminance(effective), luminance(background)))
    return (b + 0.05) / (a + 0.05)


def temperature_spec():
    objects = [
        json.loads(line) for line in SOURCE.read_text(encoding="utf-8").splitlines()
    ]
    obj = next(o for o in objects if o["id"] == "cnc-cg19-temperature-v2")
    return json.loads(json.loads(obj["attributes"]["visState"])["params"]["spec"])


def inspect_svg(file):
    root = ET.parse(file).getroot()
    # The actual SVG must paint its entire viewport white, not rely on resvg's
    # PNG background option or a transparent canvas behind the chart.
    background = root[0]
    assert background.tag.endswith("}rect"), f"Missing viewport background: {file}"
    assert rgb(background.get("fill", "")) == (1, 1, 1), file
    assert float(background.get("opacity", "1")) == 1, file
    assert background.get("width") == root.get("width"), file
    assert background.get("height") == root.get("height"), file
    paints = []

    def walk(element, inherited, group_opacity=1, role=None):
        assert "style" not in element.attrib, "CSS style needs explicit resolution"
        props = {**inherited}
        for name in ("fill", "stroke", "fill-opacity", "stroke-opacity"):
            if name in element.attrib:
                props[name] = element.attrib[name]
        opacity = group_opacity * float(element.get("opacity", "1"))
        classes = element.get("class", "").split()
        if "mark-line" in classes and "role-mark" in classes:
            role = "line"
        elif "mark-symbol" in classes and "role-mark" in classes:
            role = "symbol"
        elif "role-legend-symbol" in classes:
            role = "legend"
        if "background" in classes:
            assert props.get("fill", "black") == "none", "Unexpected plot backdrop"
        if role and element.tag.endswith("}path"):
            channel = "stroke" if role == "line" else "fill"
            paint = props.get(channel, "black" if channel == "fill" else "none")
            alpha = opacity * float(props.get(f"{channel}-opacity", "1"))
            assert 0 < alpha <= 1, f"Invisible essential mark: {file}"
            ratio = contrast(rgb(paint), alpha=alpha)
            assert ratio >= 3, f"{file}: {role} {paint}, opacity {alpha}: {ratio}:1 < 3"
            paints.append(
                {"role": role, "paint": paint, "alpha": alpha, "ratio": ratio}
            )
        for child in element:
            walk(child, props, opacity, role)

    walk(root, {"fill": "black", "stroke": "none"})
    return paints


class ContrastTests(unittest.TestCase):
    def test_svg_verifier_rejects_orange_and_inherited_transparency(self):
        template = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="600" height="400">'
            '<rect width="600" height="400" fill="#ffffff"/>'
            '<g class="mark-line role-mark" stroke="{color}" opacity="{opacity}">'
            '<path d="M0,0L10,10"/></g></svg>'
        )
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "sample.svg"
            file.write_text(template.format(color="#1f77b4", opacity=1))
            self.assertEqual(inspect_svg(file)[0]["paint"], "#1f77b4")
            for color, opacity in [("#ff7f0e", 1), ("#1f77b4", 0.2)]:
                file.write_text(template.format(color=color, opacity=opacity))
                with self.assertRaisesRegex(AssertionError, "< 3"):
                    inspect_svg(file)

    def test_independent_wcag_reference_and_negative_control(self):
        self.assertEqual(contrast(rgb("#000000")), 21)
        self.assertEqual(contrast(rgb("#ffffff")), 1)
        self.assertAlmostEqual(contrast(rgb("#ff7f0e")), 2.5319233344748815)
        self.assertLess(contrast(rgb("#ff7f0e")), 3)
        self.assertAlmostEqual(luminance((0.04045,) * 3), 0.04045 / 12.92)

    def test_exported_temperature_palette_on_explicit_white(self):
        spec = temperature_spec()
        self.assertEqual(rgb(spec["background"]), (1, 1, 1))
        palette = next(s for s in spec["scales"] if s["name"] == "color")["range"]
        self.assertIsInstance(palette, list)
        self.assertEqual(len(palette), 5)
        self.assertEqual(len(set(palette)), 5)
        for color in palette:
            with self.subTest(color=color):
                self.assertGreaterEqual(contrast(rgb(color)), 3)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--render-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    files = sorted(args.render_dir.glob("temperature-*.svg"))
    assert files, "No temperature SVG renders found"
    reports = []
    colors = {}
    for file in files:
        paints = inspect_svg(file)
        roles = {p["role"] for p in paints}
        if "temperature-0-" not in file.name:
            assert roles == {"line", "symbol", "legend"}, file
        else:
            assert not paints, file
        for paint in paints:
            colors[paint["paint"]] = paint["ratio"]
        reports.append({"svg": file.name, "essential_paints": len(paints)})
    assert len(colors) == 5, f"Expected five effective SVG colors: {colors}"
    report = {
        "method": "WCAG 2.2 sRGB luminance; effective SVG paint/opacity over explicit white",
        "reference": "https://www.w3.org/TR/WCAG22/#dfn-relative-luminance",
        "threshold": 3,
        "background": "#ffffff",
        "colors": colors,
        "minimum_ratio": min(colors.values()),
        "files": reports,
    }
    args.report.write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps({k: v for k, v in report.items() if k != "files"}, indent=2))
    print(f"Verified effective paint of {len(files)} SVGs")
