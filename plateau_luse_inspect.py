# -*- coding: utf-8 -*-
"""
PLATEAU luse inspector
"""
import os
import glob
import xml.etree.ElementTree as ET
from collections import Counter

PLATEAU_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plateau_luse")


def lname(tag):
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def read_codelists(codelists_dir):
    tables = {}
    if not os.path.isdir(codelists_dir):
        return tables
    for path in glob.glob(os.path.join(codelists_dir, "*.xml")):
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError:
            continue
        mapping = {}
        for defn in root.iter():
            if lname(defn.tag) != "Definition":
                continue
            code = label = None
            for child in defn.iter():
                ln = lname(child.tag)
                if ln == "name" and child.text:
                    code = child.text.strip()
                elif ln == "description" and child.text:
                    label = child.text.strip()
            if code is not None:
                mapping[code] = label or code
        tables[os.path.basename(path)] = mapping
    return tables


def decode(code, codespace, tables):
    if not code:
        return code
    if codespace:
        fname = os.path.basename(codespace)
        if fname in tables and code in tables[fname]:
            return tables[fname][code]
    for mapping in tables.values():
        if code in mapping:
            return mapping[code]
    return code


def find_luse_dir():
    luse_dir = os.path.join(PLATEAU_DIR, "udx", "luse")
    if os.path.isdir(luse_dir):
        return luse_dir
    cand = glob.glob(os.path.join(PLATEAU_DIR, "**", "luse"), recursive=True)
    return cand[0] if cand else None


def inspect():
    luse_dir = find_luse_dir()
    if not luse_dir:
        print(f"luse folder not found under {PLATEAU_DIR}")
        return

    tables = read_codelists(os.path.join(PLATEAU_DIR, "codelists"))
    print(f"codelist: {len(tables)} files loaded")

    gml_files = glob.glob(os.path.join(luse_dir, "*.gml"))
    print(f"luse GML: {len(gml_files)} files in {luse_dir}\n")

    class_counter = Counter()
    pref_counter = Counter()
    n_features = 0
    first_dump = None

    GEN_TAGS = ("stringAttribute", "intAttribute", "doubleAttribute",
                "measureAttribute", "genericAttribute", "genericAttributeSet")

    for gml_path in gml_files:
        try:
            root = ET.parse(gml_path).getroot()
        except ET.ParseError as e:
            print(f"  parse error: {os.path.basename(gml_path)} ({e})")
            continue

        for el in root.iter():
            if lname(el.tag) != "LandUse":
                continue
            n_features += 1

            if first_dump is None:
                children = [(lname(c.tag), (c.text or "").strip()[:80]) for c in el]
                gens = []
                for ga in el.iter():
                    if lname(ga.tag) in GEN_TAGS:
                        v = ""
                        for vv in ga:
                            if lname(vv.tag) == "value":
                                v = (vv.text or "").strip()
                        gens.append((lname(ga.tag), ga.attrib.get("name", ""), v))
                first_dump = (children, gens)

            for child in el:
                if lname(child.tag) == "class":
                    code = (child.text or "").strip()
                    label = decode(code, child.attrib.get("codeSpace"), tables)
                    class_counter[f"{label} (code={code})"] += 1
                    break

            for ga in el.iter():
                if lname(ga.tag) not in GEN_TAGS:
                    continue
                name = ga.attrib.get("name", "")
                if not any(kw in name for kw in ["class", "Class", "usage", "Usage",
                                                  "function", "Function", "type", "Type",
                                                  "code", "Code", "area", "Area"]):
                    continue
                val = None
                for v in ga:
                    if lname(v.tag) == "value":
                        val = (v.text or "").strip()
                if val:
                    pref_counter[f"{name}: {decode(val, None, tables)} (val={val})"] += 1

    print(f"LandUse features total: {n_features}\n")

    if first_dump:
        children, gens = first_dump
        print("=== First LandUse feature structure ===")
        print("  Child elements:")
        for ln, txt in children:
            print(f"    {ln}: {txt}")
        print("  Generic attributes:")
        if gens:
            for tag, nm, v in gens:
                print(f"    [{tag}] {nm} = {v}")
        else:
            print("    (none)")
        print()

    print("=== luse:class counts ===")
    for k, c in class_counter.most_common():
        print(f"  {c:>6}  {k}")

    print("\n=== Generic attribute counts (land use related) ===")
    if pref_counter:
        for k, c in pref_counter.most_common():
            print(f"  {c:>6}  {k}")
    else:
        print("  (none found - parking type may be in luse:class above)")


if __name__ == "__main__":
    inspect()
