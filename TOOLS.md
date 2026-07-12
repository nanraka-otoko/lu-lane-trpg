# 各種ツール

---

# GM向け情報

ダンジョンを作りたいときは、下記のようにダンジョンビルダーを使うと便利です。

```bash
# ダンジョンのトポロジ
# 最初の行に最上階を記載、R=部屋、(-|)=通路、s=階段、h=隠し通路、e=隠し階段
cat > dungeon-tp.txt <<'EOF'
5F
    R
    s
  R-R
  s
R-R-R
  s e
R-R RhR
s   e
R-R-R   R
  s     s
  R-R-R R
  |   | |
  R-R-R-RhR
    s
    R-R
EOF

# トポロジを ASCII Art に変換
python3 tools/dungeon_builder.py dungeon-tp.txt -o dungeon-aa.txt

# ASCII Art をダンジョンマップの画像に変換
python3 tools/dungeon_image_builder.py dungeon-aa.txt -o dungeon-map.png

# ASCII Art のナンバリングを反転
python3 tools/reverse_dungeon_numbering.py dungeon-aa.txt -o dungeon-aa-r.txt

# ダンジョンマップの画像をラベルレスで生成
python3 tools/dungeon_image_builder.py dungeon-aa.txt -o dungeon-map.png --nolabel
```

簡単な表記でダンジョンを構築後、AAのダンジョンマップに変換してシナリオブックに掲載すると、markdown の中で簡潔にシナリオを作成できます。  
ASCII Art からダンジョンマップに変換可能なので、そのまま印刷したり、オンラインセッションツールで使用すると良いでしょう。

ナンバリングを反転することで、下階から上階に登るダンジョンも表現可能です。適宜お使いください。

PLにマップを提示する場合は、ラベルレスで生成すると良いでしょう。

羊皮紙の地図のようにしてPLに手渡したい場合は、下記のように生成 AI などでラベルレスのマップを加工すると便利です。

```
この地図を、下記のように変換してください。
- 羊皮紙にインクで描かれた地図にする
- 赤い部分を破られたようにし、削除する
- 青い部分にインクをこぼし、見えなくする
```
