# -*- coding: utf-8 -*-
"""
PLATEAU CityGML zip から、土地利用(luse)とコード辞書(codelists)だけを抜き出す
=============================================================================
巨大な建物データ等を展開せず、zip の中から
  - udx/luse/  （土地利用モデルの .gml）
  - codelists/ （コードをラベルに変換する .xml）
だけを取り出して 00_parking 配下に展開する。

使い方:
  1. ZIP_PATH を、ダウンロードした CityGML zip の場所に合わせる
  2. python extract_luse.py
取り出し先（DEST）を、このあと plateau_luse_inspect.py の PLATEAU_DIR に指定する。
"""

import os
import zipfile

# ダウンロードした CityGML zip（展開せずそのまま指す）
ZIP_PATH = r"C:\Users\rd006\Downloads\33100_okayama-shi_city_2024_citygml_1_op.zip"

# 抜き出し先（小さいので 00_parking に置く）
DEST = r"C:\Users\rd006\Documents\projectGIS_2026\00_parking\plateau_luse"

# zip 内のどこにあっても、この区切り以降の構造を保って取り出す
WANT = ["codelists/", "udx/luse/"]


def main():
    if not os.path.exists(ZIP_PATH):
        print(f"zip が見つかりません: {ZIP_PATH}")
        print("ZIP_PATH をダウンロードした zip の場所に合わせてください。")
        return

    os.makedirs(DEST, exist_ok=True)
    count = {"codelists/": 0, "udx/luse/": 0}

    with zipfile.ZipFile(ZIP_PATH) as z:
        for info in z.infolist():
            if info.is_dir():
                continue
            name = info.filename.replace("\\", "/")
            for w in WANT:
                idx = name.find(w)
                if idx == -1:
                    continue
                rel = name[idx:]  # 例: udx/luse/xxx.gml / codelists/yyy.xml
                out_path = os.path.join(DEST, *rel.split("/"))
                os.makedirs(os.path.dirname(out_path), exist_ok=True)
                with z.open(info) as src, open(out_path, "wb") as dst:
                    dst.write(src.read())
                count[w] += 1
                break

    print(f"取り出し先: {DEST}")
    print(f"  codelists/ : {count['codelists/']} ファイル")
    print(f"  udx/luse/  : {count['udx/luse/']} ファイル")
    if count["udx/luse/"] == 0:
        print("※ udx/luse/ が0件でした。zip内に土地利用モデルが無いか、")
        print("  パスの区切りが想定と違う可能性があります。中身を確認してください。")


if __name__ == "__main__":
    main()
