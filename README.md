# beehive-clone

Static honeycomb blog styled after the Beehive Tumblr theme by egg.design. No dependencies beyond Python 3.10+.

```sh
python3 beehive.py seed -n 30 --replace      # lorem ipsum posts
python3 beehive.py serve                      # http://127.0.0.1:8740

python3 beehive.py add photo --image https://... --image https://... --caption "hi" --tags a,b --notes 12
python3 beehive.py add text --title "Title" --body @post.txt      # or --body - for stdin
python3 beehive.py add quote --text "..." --attribution "Someone"
python3 beehive.py import posts.json [--replace]
python3 beehive.py list
python3 beehive.py rm 3 7
python3 beehive.py clear
python3 beehive.py config title="my blog" accent="#7fa7e0" per_page=12
python3 beehive.py config pages='[{"title":"about","url":"/about"}]'
```

Every mutating command rebuilds `dist/` (pass `--no-build` to skip). Data lives in `data/posts.json` and `data/site.json`.

Import format (array or single object):

```json
[{"type": "photo", "images": ["https://..."], "caption": "", "date": "2024-05-01T12:00:00",
  "tags": ["x"], "notes": 40, "source": "someblog",
  "note_list": [{"user": "a", "action": "liked"}, {"user": "b", "action": "reblogged", "from": "c"}]}]
```

Text and captions are escaped plain text (blank lines make paragraphs); set `"html": true` or pass `--html` for raw HTML.
