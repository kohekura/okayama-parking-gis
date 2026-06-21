# -*- coding: utf-8 -*-
"""
統合マップ: OSM駐車場 × PLATEAU土地利用（222: 平面駐車場 / 224: 低未利用地）
================================================================================
OSMの各駐車場地物に、PLATEAU土地利用上の重なり状況をタグ付けして可視化する。

タグの意味:
  overlap_222    : PLATEAU上でも「平面駐車場」と明示的に認定されている
                    （公式データでも駐車場と確認できる、最も確からしい一致）
  overlap_224    : PLATEAU上は「低未利用地（空地・空家・空き店舗等）」に分類
                    （駐車場経営をしているが、調査上は土地利用が定まっていない
                      = スポンジ化の進行を示す可能性が高い）
  no_overlap     : PLATEAU上はどちらにも該当しない
                    （商業用地・住宅用地等、他の主用途に紐づく付帯駐車場の可能性、
                      または調査時点とのズレ）

出力:
  parking_plateau_candidates.geojson : PLATEAU 222+224 ポリゴン（重ね合わせ用）
  parking_osm_flagged.geojson        : OSM駐車場 + overlap_status 付き
  combined_map.html                  : 統合可視化マップ
"""

import os
import json
import glob
import xml.etree.ElementTree as ET
import folium
from collections import Counter

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
LUSE_DIR = os.path.join(OUT_DIR, "plateau_luse", "udx", "luse")
OSM_GEOJSON = os.path.join(OUT_DIR, "parking.geojson")

OUT_PLATEAU_GEOJSON = os.path.join(OUT_DIR, "parking_plateau_candidates.geojson")
OUT_OSM_FLAGGED = os.path.join(OUT_DIR, "parking_osm_flagged.geojson")
OUT_HTML = os.path.join(OUT_DIR, "combined_map.html")

# まちなかBBOX（parking_map.py と同じ。少し余裕を持たせてある）
BBOX = (34.640, 133.900, 34.690, 133.955)  # south, west, north, east

TARGET_CODES = {
    "222": "平面駐車場",
    "224": "低未利用地",
}

CODE_COLOR = {
    "222": "#3b7dd8",  # 青系: 公式に駐車場と認定
    "224": "#cc0000",  # 赤: 低未利用地（ハッチングで強調）
}

OVERLAP_COLOR = {
    "overlap_222": "#1f5fae",  # 濃い青: 確からしい一致
    "overlap_224": "#cc0000",  # 赤: 低未利用地と重なる（PLATEAU 224と同じ赤に統一）
    "no_overlap":  "#888888",  # グレー: どちらでもない
}

# 低未利用地（224）を示す赤ハッチングのSVGパターン定義。
# foliumのfill_colorだけでは斜線が出せないため、地図にパターンを差し込み、
# 該当ポリゴンの fill には通常色の代わりにこのパターンIDを使う。
HATCH_PATTERN_ID = "lowUtilHatch"
HATCH_DEFS_HTML = f"""
<svg width="0" height="0" style="position:absolute">
  <defs>
    <pattern id="{HATCH_PATTERN_ID}" patternUnits="userSpaceOnUse"
             width="8" height="8" patternTransform="rotate(45)">
      <rect width="8" height="8" fill="#cc0000" fill-opacity="0.12"></rect>
      <line x1="0" y1="0" x2="0" y2="8" stroke="#cc0000" stroke-width="3"></line>
    </pattern>
  </defs>
</svg>
"""

OVERLAP_LABEL = {
    "overlap_222": "PLATEAU上も平面駐車場と一致",
    "overlap_224": "PLATEAU上は低未利用地（スポンジ化の疑い）",
    "no_overlap":  "PLATEAU上はどちらにも該当せず",
}


def lname(tag):
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def parse_pos_list(text):
    nums = [float(x) for x in text.split()]
    return [(nums[i], nums[i + 1]) for i in range(0, len(nums) - 2, 3)]


def bbox_of(pts):
    lats = [p[0] for p in pts]
    lons = [p[1] for p in pts]
    return min(lats), max(lats), min(lons), max(lons)


def bbox_intersects(b1, b2):
    s1, w1, n1, e1 = b1
    s2, w2, n2, e2 = b2
    return not (n1 < s2 or n2 < s1 or e1 < w2 or e2 < w1)


def point_in_polygon(lat, lon, poly):
    n = len(poly)
    inside = False
    x, y = lon, lat
    x1, y1 = poly[0][1], poly[0][0]
    xinters = None
    for i in range(1, n + 1):
        x2, y2 = poly[i % n][1], poly[i % n][0]
        if y > min(y1, y2) and y <= max(y1, y2) and x <= max(x1, x2):
            if y1 != y2:
                xinters = (y - y1) * (x2 - x1) / (y2 - y1) + x1
            if x1 == x2 or x <= xinters:
                inside = not inside
        x1, y1 = x2, y2
    return inside


def extract_polygons(el):
    polys = []
    for ms in el.iter():
        if lname(ms.tag) != "MultiSurface":
            continue
        for poly in ms.iter():
            if lname(poly.tag) != "Polygon":
                continue
            for ext in poly:
                if lname(ext.tag) != "exterior":
                    continue
                for ring in ext.iter():
                    if lname(ring.tag) != "LinearRing":
                        continue
                    for pos in ring:
                        if lname(pos.tag) == "posList" and pos.text:
                            pts = parse_pos_list(pos.text)
                            if len(pts) >= 4:
                                polys.append(pts)
    return polys


def load_plateau_candidates():
    """222・224 のポリゴンを、まちなかBBOX周辺に絞って読み込む。
    戻り値: [(code, pts), ...]
    """
    gml_files = sorted(glob.glob(os.path.join(LUSE_DIR, "*.gml")))
    if not gml_files:
        print(f"luse GMLが見つかりません: {LUSE_DIR}")
        return []

    results = []
    counts_total = Counter()
    counts_near = Counter()

    for gml_path in gml_files:
        try:
            root = ET.parse(gml_path).getroot()
        except ET.ParseError:
            continue
        for el in root.iter():
            if lname(el.tag) != "LandUse":
                continue
            code = None
            for child in el:
                if lname(child.tag) == "class":
                    code = (child.text or "").strip()
                    break
            if code not in TARGET_CODES:
                continue
            counts_total[code] += 1
            for pts in extract_polygons(el):
                if bbox_intersects(bbox_of(pts), BBOX):
                    results.append((code, pts))
                    counts_near[code] += 1

    for code, label in TARGET_CODES.items():
        print(f"  {label}(code={code}): 全市 {counts_total[code]} 件 / "
              f"まちなか付近 {counts_near[code]} 件")
    return results


def load_osm_features():
    with open(OSM_GEOJSON, encoding="utf-8") as f:
        data = json.load(f)
    return data["features"]


def representative_point(feat):
    geom = feat["geometry"]
    if geom["type"] == "Point":
        lon, lat = geom["coordinates"]
    else:
        ring = geom["coordinates"][0]
        lon = sum(p[0] for p in ring) / len(ring)
        lat = sum(p[1] for p in ring) / len(ring)
    return lat, lon


def main():
    if not os.path.exists(OSM_GEOJSON):
        print(f"OSMデータが見つかりません: {OSM_GEOJSON}")
        print("先に parking_map.py を実行してください。")
        return

    print("PLATEAU候補ポリゴン(222+224)を読み込み中...")
    candidates = load_plateau_candidates()
    if not candidates:
        return

    print("OSM駐車場を読み込み中...")
    osm_features = load_osm_features()
    print(f"OSM駐車場 地物数: {len(osm_features)}")

    # ---- OSM各地物に重なり判定でタグ付け ----
    status_counter = Counter()
    for feat in osm_features:
        lat, lon = representative_point(feat)
        status = "no_overlap"
        for code, pts in candidates:
            if point_in_polygon(lat, lon, pts):
                status = f"overlap_{code}"
                if code == "222":
                    break  # 222が見つかれば最優先で確定
        feat["properties"]["overlap_status"] = status
        feat["properties"]["rep_lat"] = lat
        feat["properties"]["rep_lon"] = lon
        status_counter[status] += 1

    print("\n=== 重なり判定の結果 ===")
    total = len(osm_features)
    for key in ("overlap_222", "overlap_224", "no_overlap"):
        c = status_counter.get(key, 0)
        pct = 100 * c / total if total else 0
        print(f"  {OVERLAP_LABEL[key]}: {c} 件 ({pct:.1f}%)")

    # ---- 出力1: OSM側（フラグ付き） ----
    with open(OUT_OSM_FLAGGED, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": osm_features},
                  f, ensure_ascii=False)
    print(f"\n保存: {OUT_OSM_FLAGGED}")

    # ---- 出力2: PLATEAU候補ポリゴン ----
    plateau_features = []
    for code, pts in candidates:
        ring = [[lon, lat] for (lat, lon) in pts]
        if ring[0] != ring[-1]:
            ring.append(ring[0])
        plateau_features.append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [ring]},
            "properties": {"luse_class_code": code,
                           "luse_class_label": TARGET_CODES[code]},
        })
    with open(OUT_PLATEAU_GEOJSON, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": plateau_features},
                  f, ensure_ascii=False)
    print(f"保存: {OUT_PLATEAU_GEOJSON}")

    # ---- folium 統合マップ ----
    s, w, n, e = BBOX
    m = folium.Map(location=[(s + n) / 2, (w + e) / 2], zoom_start=14,
                   tiles="OpenStreetMap")
    folium.TileLayer(
        tiles=("https://server.arcgisonline.com/ArcGIS/rest/services/"
               "World_Imagery/MapServer/tile/{z}/{y}/{x}"),
        attr="Esri World Imagery", name="航空写真（実態確認用）",
        overlay=False, show=False,
    ).add_to(m)

    # PLATEAU ポリゴン（224・222とも同じ赤で統一。222を上に重ねる）
    PLATEAU_COLOR = "#cc0000"
    for code in ("224", "222"):
        fg = folium.FeatureGroup(name=f"PLATEAU {TARGET_CODES[code]}")
        for c, pts in candidates:
            if c != code:
                continue
            folium.Polygon(
                locations=pts, color=PLATEAU_COLOR, weight=1,
                fill=True, fill_color=PLATEAU_COLOR, fill_opacity=0.3,
            ).add_to(fg)
        fg.add_to(m)

    # OSM駐車場（種別を問わず全部同じ赤で表示。実際のジオメトリのまま描画）
    OSM_COLOR = "#cc0000"
    fg = folium.FeatureGroup(name="OSM駐車場")
    for feat in osm_features:
        name = feat["properties"].get("name") or "（名称なし）"
        status_label = OVERLAP_LABEL.get(feat["properties"]["overlap_status"], "")
        popup = folium.Popup(f"<b>{name}</b><br>{status_label}", max_width=240)
        geom = feat["geometry"]
        if geom["type"] == "Polygon":
            ring = geom["coordinates"][0]
            locs = [(lat, lon) for lon, lat in ring]
            folium.Polygon(
                locations=locs, color=OSM_COLOR, weight=2,
                fill=True, fill_color=OSM_COLOR, fill_opacity=0.45,
                popup=popup,
            ).add_to(fg)
        else:
            lon, lat = geom["coordinates"]
            folium.CircleMarker(
                location=(lat, lon), radius=4, color=OSM_COLOR,
                fill=True, fill_color=OSM_COLOR, fill_opacity=0.9,
                popup=popup,
            ).add_to(fg)
    fg.add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)

    legend_rows = (
        f"<div style='margin:2px 0'>"
        f"<span style='display:inline-block;width:12px;height:12px;"
        f"background:#cc0000;margin-right:6px;border:1px solid #999'></span>"
        f"OSM駐車場: {len(osm_features)}</div>"
        f"<div style='margin:2px 0'>"
        f"<span style='display:inline-block;width:12px;height:12px;"
        f"background:#cc0000;opacity:0.3;margin-right:6px;border:1px solid #999'></span>"
        f"PLATEAU 低未利用地・平面駐車場: {len(candidates)}</div>"
    )
    legend = f"""
    <div style="position:fixed; bottom:24px; left:24px; z-index:9999;
         background:white; padding:10px 12px; border:1px solid #ccc;
         border-radius:6px; font-size:13px; font-family:sans-serif;
         box-shadow:0 1px 4px rgba(0,0,0,0.2); max-width:280px;">
      <div style="font-weight:bold; margin-bottom:6px;">
        OSM駐車場 × PLATEAU土地利用 重なり状況
      </div>
      {legend_rows}
      <div style="margin-top:8px; color:#888; font-size:11px;">
        データ出典: © OpenStreetMap contributors /<br>
        国土交通省 都市局 Project PLATEAU（岡山市2024年度）
      </div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend))
    m.save(OUT_HTML)
    print(f"保存: {OUT_HTML}")


if __name__ == "__main__":
    main()
