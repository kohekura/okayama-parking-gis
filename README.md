# 岡山市まちなか駐車場分布マップ

岡山市中心市街地における駐車場の分布を、OSM（OpenStreetMap）とPLATEAU（3D都市モデル・土地利用モデル）の2つの公開データソースを使って可視化・検証するプロジェクトです。

## 背景・問い

駐車場、特に平面（青空）駐車場は、自家用交通の発生集中源であると同時に、沿道に「死んだ前面（dead frontage）」を生み、ウォーカブルな都市空間の形成を阻害します。建物が取り壊されて駐車場に転用される現象は、都市の「スポンジ化」（中心市街地の低未利用地化）の代表的な見えるサインでもあります。

本プロジェクトは「まちなかの駐車場はどこにあるか」を出発点に、それを支える公開データの性質と限界を検証することを目的としています。

## データソース・出典

- **OpenStreetMap**：© OpenStreetMap contributors, ODbL (https://www.openstreetmap.org/copyright)
  Overpass API経由で amenity=parking を取得
- **国土交通省 都市局 Project PLATEAU**：岡山市（2024年度）土地利用モデル
  出典：国土交通省 PLATEAUウェブサイト（https://www.mlit.go.jp/plateau/）、CC BY 4.0（https://www.mlit.go.jp/plateau/site-policy/）
  本プロジェクトでは土地利用モデル（luse）からPythonスクリプトで駐車場・低未利用地の区分を抽出・加工して利用しています。

## 構成