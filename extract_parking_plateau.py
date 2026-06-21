# -*- coding: utf-8 -*-
"""
PLATEAU 土地利用モデルから平面駐車場（code=222）を抽出
======================================================
plateau_luse_inspect.py で特定した luse:class = 222
（その他③：平面駐車場）のポリゴンだけを取り出し、
  - parking_plateau.geojson : 重ね合わせ用の整形済みデータ
  - parking_plateau_map.html : 単体の確認用マップ
を出力する。

座標系について:
  PLATEAU V4 は EPSG:6697 (JGD2011, lat/lon/h の順）。
  foliumは緯度経度をそのまま使うので、変換は不要（lat, lon の順そのまま使う）。

データ出典: 国土交通省 都市局 Project PLATEAU
  3D都市モデル（Project PLATEAU）岡山市（2024年度）
  https://www.geospatial.jp/ckan/dataset/plateau-33100-okayama-shi-2024
  PLATEAU Site Policy に基づき利用（商用利用可）
"""

import os
import json
import glob
import xml.etree.ElementTree as ET
import folium

# extract_luse.py が取り出した土地利用データの場所（このスクリプトと同じフォルダ基準）
PLATEAU_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plateau_luse")
LUSE_DIR = os.path.join(PLATEAU_DIR, "udx", "luse")

# 抽出対象の土地利用区分コード（plateau_luse_inspect.py の出力で確認済み）
TARGET_CODE = "222"  # その他③（平面駐車場）

# 出力先（00_parking 直下。このスクリプト自身と同じ場所）
OUT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_GEOJSON = os.path.join(OUT_DIR, "parking_plateau.geojson")
OUT_HTML = os.path.join(OUT_DIR, "parking_plateau_map.html")

FILL_COLOR = "#e8453c"  # OSM側の「平面（青空）」と揃えた色


def lname(tag):
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def parse_pos_list(text):
    """gml:posList のテキスト "lat lon h lat lon h ..." を
    [(lat, lon), ...] のリストに変換する（高さは捨てる）。
    """
    nums = [float(x) for x in text.split()]
    pts = []
    for i in range(0, len(nums) - 2, 3):
        lat, lon = nums[i], nums[i + 1]
        pts.append((lat, lon))
    return pts


def extract_polygons(el):
    """LandUse 地物から、lod1MultiSurface 内の全ポリゴン（外周のみ）を取り出す。
    1地物が複数ポリゴンを持つ場合は複数返す。
    """
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


def main():
    gml_files = sorted(glob.glob(os.path.join(LUSE_DIR, "*.gml")))
    if not gml_files:
        print(f"luse GML が見つかりません: {LUSE_DIR}")
        print("先に extract_luse.py を実行してください。")
        return
    print(f"luse GML {len(gml_files)} ファイルから code={TARGET_CODE} を抽出します")

    features = []
    all_lats, all_lons = [], []

    for gml_path in gml_files:
        try:
            root = ET.parse(gml_path).getroot()
        except ET.ParseError as e:
            print(f"  パース失敗: {os.path.basename(gml_path)} ({e})")
            continue

        for el in root.iter():
            if lname(el.tag) != "LandUse":
                continue

            code = None
            for child in el:
                if lname(child.tag) == "class":
                    code = (child.text or "").strip()
                    break
            if code != TARGET_CODE:
                continue

            gml_id = el.attrib.get("{http://www.opengis.net/gml}id", "")
            polys = extract_polygons(el)
            for pts in polys:
                ring = [[lon, lat] for (lat, lon) in pts]  # GeoJSONはlon,lat順
                if ring[0] != ring[-1]:
                    ring.append(ring[0])
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "Polygon", "coordinates": [ring]},
                    "properties": {
                        "source": "PLATEAU_luse",
                        "gml_id": gml_id,
                        "luse_class_code": code,
                        "luse_class_label": "その他③（平面駐車場）",
                    },
                })
                for lat, lon in pts:
                    all_lats.append(lat)
                    all_lons.append(lon)

    print(f"抽出した平面駐車場ポリゴン: {len(features)} 件")

    if not features:
        print("該当ポリゴンが0件でした。TARGET_CODE を確認してください。")
        return

    # ---- GeoJSON 出力 ----
    with open(OUT_GEOJSON, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": features},
                  f, ensure_ascii=False)
    print(f"保存: {OUT_GEOJSON}")

    # ---- folium 地図出力 ----
    center = [sum(all_lats) / len(all_lats), sum(all_lons) / len(all_lons)]
    m = folium.Map(location=center, zoom_start=13, tiles="OpenStreetMap")
    folium.TileLayer(
        tiles=("https://server.arcgisonline.com/ArcGIS/rest/services/"
               "World_Imagery/MapServer/tile/{z}/{y}/{x}"),
        attr="Esri World Imagery",
        name="航空写真（実態確認用）",
        overlay=False,
        show=False,
    ).add_to(m)

    fg = folium.FeatureGroup(name="平面駐車場（PLATEAU土地利用）")
    for feat in features:
        ring = feat["geometry"]["coordinates"][0]
        locs = [(lat, lon) for lon, lat in ring]
        folium.Polygon(
            locations=locs, color=FILL_COLOR, weight=2,
            fill=True, fill_color=FILL_COLOR, fill_opacity=0.35,
            popup=f"PLATEAU luse: {feat['properties']['luse_class_label']}",
        ).add_to(fg)
    fg.add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)

    legend = f"""
    <div style="position:fixed; bottom:24px; left:24px; z-index:9999;
         background:white; padding:10px 12px; border:1px solid #ccc;
         border-radius:6px; font-size:13px; font-family:sans-serif;
         box-shadow:0 1px 4px rgba(0,0,0,0.2);">
      <div style="font-weight:bold; margin-bottom:6px;">
        平面駐車場（都市計画基礎調査 土地利用現況）
      </div>
      <div>件数: {len(features)}</div>
      <div style="margin-top:8px; color:#888; font-size:11px;">
        出典: 国土交通省 都市局 Project PLATEAU<br>
        岡山市（2024年度）土地利用モデル
      </div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend))
    m.save(OUT_HTML)
    print(f"保存: {OUT_HTML}")


if __name__ == "__main__":
    main()
