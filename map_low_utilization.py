# -*- coding: utf-8 -*-
"""
低未利用地（PLATEAU luse code=224）の可視化マップ
====================================================
build_combined_map.py が保存した parking_plateau_candidates.geojson から
224（低未利用地）のポリゴンだけを取り出して、単体のfoliumマップに描く。
新たにPLATEAUのGMLを読み直す必要はない。

データ出典: 国土交通省 都市局 Project PLATEAU 岡山市（2024年度）土地利用モデル
"""

import os
import json
import folium

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
PLATEAU_GEOJSON = os.path.join(OUT_DIR, "parking_plateau_candidates.geojson")
OUT_HTML = os.path.join(OUT_DIR, "low_utilization_map.html")

FILL_COLOR = "#e08a1e"  # オレンジ系


def main():
    if not os.path.exists(PLATEAU_GEOJSON):
        print(f"見つかりません: {PLATEAU_GEOJSON}")
        print("先に build_combined_map.py を実行してください。")
        return

    with open(PLATEAU_GEOJSON, encoding="utf-8") as f:
        features = json.load(f)["features"]

    polys_224 = [f for f in features if f["properties"]["luse_class_code"] == "224"]
    print(f"低未利用地(224)ポリゴン: {len(polys_224)} 件")

    if not polys_224:
        print("224のポリゴンが見つかりませんでした。")
        return

    # 中心座標の計算
    all_lats, all_lons = [], []
    for feat in polys_224:
        for lon, lat in feat["geometry"]["coordinates"][0]:
            all_lats.append(lat)
            all_lons.append(lon)
    center = [sum(all_lats) / len(all_lats), sum(all_lons) / len(all_lons)]

    m = folium.Map(location=center, zoom_start=14, tiles="OpenStreetMap")
    folium.TileLayer(
        tiles=("https://server.arcgisonline.com/ArcGIS/rest/services/"
               "World_Imagery/MapServer/tile/{z}/{y}/{x}"),
        attr="Esri World Imagery", name="航空写真（実態確認用）",
        overlay=False, show=False,
    ).add_to(m)

    fg = folium.FeatureGroup(name="低未利用地（PLATEAU 224）")
    for feat in polys_224:
        ring = feat["geometry"]["coordinates"][0]
        locs = [(lat, lon) for lon, lat in ring]
        folium.Polygon(
            locations=locs, color=FILL_COLOR, weight=1.5,
            fill=True, fill_color=FILL_COLOR, fill_opacity=0.35,
            popup="低未利用地（空地・空家・空き店舗等）",
        ).add_to(fg)
    fg.add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)

    legend = f"""
    <div style="position:fixed; bottom:24px; left:24px; z-index:9999;
         background:white; padding:10px 12px; border:1px solid #ccc;
         border-radius:6px; font-size:13px; font-family:sans-serif;
         box-shadow:0 1px 4px rgba(0,0,0,0.2);">
      <div style="font-weight:bold; margin-bottom:6px;">低未利用地</div>
      <div>件数: {len(polys_224)}（まちなか周辺）</div>
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
