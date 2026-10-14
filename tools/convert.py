"""Build-time SB3 analysis and Python source translation. Never imported by the game."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import pprint
import re
import shutil
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def convert(source=None):
    if source:
        with zipfile.ZipFile(source) as archive:
            for item in archive.infolist():
                # SB3 assets must be flat filenames; reject traversal.
                if Path(item.filename).name != item.filename:
                    raise ValueError(f"Unexpected archive path: {item.filename}")
                archive.extract(item, ROOT / "reference")
    project = json.loads((ROOT / "reference/project.json").read_text(encoding="utf-8"))
    ir = {"metadata": project["meta"], "extensions": project["extensions"],
          "targets": [], "dependencies": [], "monitors": project["monitors"]}
    for target in project["targets"]:
        blocks = target["blocks"]
        scripts = []
        for bid, block in blocks.items():
            if block.get("topLevel"):
                seen = set()

                def visit(current):
                    if current is None or current in seen:
                        return
                    seen.add(current)
                    node = blocks[current]
                    for key, value in node["inputs"].items():
                        if isinstance(value[1], str) and value[1] in blocks:
                            visit(value[1])
                        elif isinstance(value[1], list) and value[1][0] == 12:
                            ir["dependencies"].append({"script": bid, "target": target["name"],
                                                       "variable": value[1][1], "access": "read"})
                    if "VARIABLE" in node["fields"]:
                        ir["dependencies"].append({"script": bid, "target": target["name"],
                                                   "variable": node["fields"]["VARIABLE"][0],
                                                   "access": "write"})
                    if node["opcode"] == "sensing_touchingobjectmenu":
                        ir["dependencies"].append({"script": bid, "target": target["name"],
                                                   "touches": node["fields"]["TOUCHINGOBJECTMENU"][0]})
                    if node["opcode"] == "control_create_clone_of_menu":
                        ir["dependencies"].append({"script": bid, "target": target["name"],
                                                   "clones": node["fields"]["CLONE_OPTION"][0]})
                    visit(node["next"])

                visit(bid)
                scripts.append({"hat": bid, "event": block["opcode"], "blocks": sorted(seen)})
        reachable = {b for s in scripts for b in s["blocks"]}
        ir["targets"].append({"name": target["name"], "scripts": scripts,
                              "unreachable": sorted(set(blocks) - reachable),
                              "blocks": blocks, "variables": target["variables"],
                              "lists": target["lists"], "broadcasts": target["broadcasts"],
                              "comments": target["comments"], "costumes": target["costumes"],
                              "sounds": target["sounds"]})
    # Complete representation and dependency graph exist before emitting executable code.
    (ROOT / "reference/analysis.json").write_text(json.dumps(ir, indent=2), encoding="utf-8")
    if any(t["unreachable"] for t in ir["targets"]):
        raise ValueError("Unreachable blocks require explicit analysis")

    import resvg_py
    from PIL import Image
    assets = ROOT / "assets"
    assets.mkdir(exist_ok=True)
    converted = {}
    for target in project["targets"]:
        for costume in target["costumes"]:
            filename = costume["md5ext"]
            if filename in converted:
                continue
            original = ROOT / "reference" / filename
            if costume["dataFormat"] == "svg":
                svg = ET.fromstring(original.read_text(encoding="utf-8"))
                width, height = float(svg.attrib["width"]), float(svg.attrib["height"])
                out = assets / (original.stem + ".png")
                if width == 0 or height == 0:
                    Image.new("RGBA", (1, 1)).save(out)
                else:
                    out.write_bytes(resvg_py.svg_to_bytes(svg_path=str(original), zoom=2.0))
                converted[filename] = {"file": out.name, "width": width, "height": height,
                                       "raster_scale": 2, "empty": width == 0 or height == 0}
            else:
                shutil.copy2(original, assets / filename)
                with Image.open(original) as image:
                    width, height = image.size
                converted[filename] = {"file": filename, "width": width, "height": height,
                                       "raster_scale": 1, "empty": False}
        for sound in target["sounds"]:
            shutil.copy2(ROOT / "reference" / sound["md5ext"], assets / sound["md5ext"])

    specs = []
    collision_path = ROOT / "reference/collision_metadata.json"
    collision_metadata = json.loads(collision_path.read_text()) if collision_path.exists() else {}
    for target in project["targets"]:
        spec = {k: v for k, v in target.items() if k not in ("blocks", "comments", "broadcasts")}
        for index, costume in enumerate(spec["costumes"]):
            costume["render"] = dict(converted[costume["md5ext"]])
            key = f"{target['name']}:{index}"
            if key in collision_metadata:
                costume["render"]["collision"] = collision_metadata[key]
        specs.append(spec)
    (ROOT / "project_data.py").write_text(
        '"""Original target state and asset metadata; no executable Scratch blocks."""\n'
        + "TARGETS = " + pprint.pformat(specs, width=110, sort_dicts=False)
        + "\nMONITORS = " + pprint.pformat(project["monitors"], width=110, sort_dicts=False) + "\n",
        encoding="utf-8")

    code = ['"""All 23 Scratch scripts translated to ordinary Python generators.',
            'Generated by tools/convert.py; original block IDs annotate the source.',
            'The game never reads project.json or dispatches Scratch opcodes.',
            '"""', 'from semantics import less_than, repeat_count', '']
    registrations = []
    coverage = {}
    for target in project["targets"]:
        blocks = target["blocks"]
        prefix = re.sub(r"\W+", "_", target["name"]).strip("_").lower() or "helper_dot"
        counter = 0
        function = None

        def mark(bid, role):
            coverage[bid] = {"target": target["name"], "opcode": blocks[bid]["opcode"],
                             "function": function, "file": "scripts.py", "line": len(code) + 1,
                             "role": role}

        def expression(value):
            item = value[1]
            if isinstance(item, list):
                if item[0] == 12:
                    return f"sprite.get_var({item[1]!r})"
                return repr(item[1])
            node = blocks[item]
            mark(item, "expression")
            opcode = node["opcode"]
            if node.get("shadow"):
                return repr(next(iter(node["fields"].values()))[0])
            if opcode == "sensing_touchingobject":
                return f"sprite.touching({expression(node['inputs']['TOUCHINGOBJECTMENU'])})"
            if opcode == "operator_lt":
                return f"less_than({expression(node['inputs']['OPERAND1'])}, {expression(node['inputs']['OPERAND2'])})"
            if opcode == "operator_random":
                return f"rt.random({expression(node['inputs']['FROM'])}, {expression(node['inputs']['TO'])})"
            if opcode == "motion_yposition":
                return "sprite.y"
            raise ValueError(f"Untranslated reporter: {opcode}")

        def chain(bid, indent=1):
            while bid:
                node = blocks[bid]
                mark(bid, "statement")
                pad = "    " * indent
                code.append(pad + f"# Scratch {bid}: {node['opcode']}")
                op = node["opcode"]
                inp = lambda key: expression(node["inputs"][key])
                statement = None
                if op == "motion_gotoxy":
                    statement = f"sprite.goto({inp('X')}, {inp('Y')})"
                elif op == "motion_goto":
                    statement = f"sprite.goto_target({inp('TO')})"
                elif op in ("motion_changexby", "motion_changeyby"):
                    axis = "x" if op == "motion_changexby" else "y"
                    statement = f"sprite.change_{axis}({inp('D' + axis.upper())})"
                elif op in ("motion_setx", "motion_sety"):
                    axis = op[-1]
                    statement = f"sprite.set_{axis}({inp(axis.upper())})"
                elif op == "data_setvariableto":
                    statement = f"sprite.set_var({node['fields']['VARIABLE'][0]!r}, {inp('VALUE')})"
                elif op == "data_changevariableby":
                    statement = f"sprite.change_var({node['fields']['VARIABLE'][0]!r}, {inp('VALUE')})"
                elif op == "control_wait":
                    statement = f"yield rt.wait({inp('DURATION')})"
                elif op == "sound_playuntildone":
                    statement = f"yield rt.play_sound(sprite, {inp('SOUND_MENU')})"
                elif op == "control_forever":
                    code.append(pad + "while True:")
                    chain(node["inputs"]["SUBSTACK"][1], indent + 1)
                    code.append(pad + "    yield rt.next_frame()")
                elif op == "control_repeat":
                    code.append(pad + f"for _ in range(repeat_count({inp('TIMES')})):")
                    chain(node["inputs"]["SUBSTACK"][1], indent + 1)
                    code.append(pad + "    yield rt.next_frame()")
                elif op == "control_if":
                    code.append(pad + f"if {inp('CONDITION')}:")
                    chain(node["inputs"]["SUBSTACK"][1], indent + 1)
                elif op in ("looks_show", "looks_hide"):
                    statement = f"sprite.visible = {op == 'looks_show'}"
                elif op == "looks_switchcostumeto":
                    statement = f"sprite.switch_costume({inp('COSTUME')})"
                elif op == "looks_nextcostume":
                    statement = "sprite.next_costume()"
                elif op == "control_create_clone_of":
                    statement = f"rt.create_clone(sprite, {inp('CLONE_OPTION')})"
                elif op == "control_delete_this_clone":
                    statement = "rt.delete_clone(sprite)\n" + pad + "return"
                else:
                    raise ValueError(f"Untranslated statement: {op}")
                if statement:
                    code.extend((pad + statement).splitlines())
                bid = node["next"]

        for bid, node in blocks.items():
            if not node.get("topLevel"):
                continue
            counter += 1
            kind = {"event_whenflagclicked": "green_flag", "event_whenkeypressed": "key",
                    "control_start_as_clone": "clone_start"}[node["opcode"]]
            key = node["fields"].get("KEY_OPTION", [None])[0]
            function = f"{prefix}_{kind}_{key or counter}"
            mark(bid, "event registration")
            code.extend([f"def {function}(rt, sprite):", f"    # Scratch hat {bid}",
                         "    if False:  # Keep immediate scripts as generators.", "        yield"])
            chain(node["next"])
            code.append("")
            registrations.append((target["name"], kind, key, function, bid))
    code.append("def register(rt):")
    for name, kind, key, function, bid in registrations:
        code.append(f"    rt.on({name!r}, {kind!r}, {key!r}, {function}, {bid!r})")
    (ROOT / "scripts.py").write_text("\n".join(code) + "\n", encoding="utf-8")
    total = sum(len(t["blocks"]) for t in project["targets"])
    assert len(coverage) == total
    audit = {"targets": len(specs), "sprites": len(specs) - 1, "scripts": len(registrations),
             "blocks": total, "translated_blocks": len(coverage), "mapping": coverage,
             "assets": converted,
             "collision_assets": collision_metadata,
             "asset_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in (ROOT / "reference").iterdir() if p.suffix in (".svg", ".png", ".wav")}}
    (ROOT / "coverage.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(f"Translated {len(registrations)} scripts and {total} blocks; {len(converted)} distinct images")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", nargs="?")
    convert(parser.parse_args().source)
