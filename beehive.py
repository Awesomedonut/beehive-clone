#!/usr/bin/env python3
"""Static honeycomb blog styled after the Beehive Tumblr theme.

Posts live in data/posts.json and are managed from the command line;
`build` renders everything into dist/.
"""
from __future__ import annotations

import argparse
import html
import json
import random
import shutil
import sys
import time
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
POSTS_FILE = DATA / "posts.json"
SITE_FILE = DATA / "site.json"
STATIC = ROOT / "static"
DIST = ROOT / "dist"

DEFAULT_SITE = {
    "title": "lorem ipsum",
    "description": "Dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor.",
    "description_link": {"text": "@loremipsum", "url": "#"},
    "avatar": "https://picsum.photos/seed/beehive-avatar/200/200",
    "banner": "https://picsum.photos/seed/beehive-banner/400/200",
    "accent": "#e7748d",
    "per_page": 12,
    "ask_url": "#",
    "pages": [
        {"title": "Lorem page", "url": "#"},
        {"title": "about", "url": "#"},
        {"title": "Single Column Layout", "url": "#"},
    ],
    "credit": {"text": "Beehive theme by egg.design", "url": "https://egg.design/"},
}

LOREM = (
    "lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor "
    "incididunt ut labore et dolore magna aliqua ut enim ad minim veniam quis nostrud "
    "exercitation ullamco laboris nisi aliquip ex ea commodo consequat duis aute irure "
    "in reprehenderit voluptate velit esse cillum fugiat nulla pariatur excepteur sint "
    "occaecat cupidatat non proident sunt culpa qui officia deserunt mollit anim id est laborum"
).split()


# ---------------------------------------------------------------- storage

def load_json(path: Path, default):
    if not path.exists():
        return json.loads(json.dumps(default))
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_site() -> dict:
    site = dict(DEFAULT_SITE)
    site.update(load_json(SITE_FILE, {}))
    return site


def load_posts() -> list[dict]:
    return load_json(POSTS_FILE, [])


def save_posts(posts: list[dict]) -> None:
    save_json(POSTS_FILE, posts)


def next_id(posts: list[dict]) -> int:
    return max((p["id"] for p in posts), default=0) + 1


def parse_date(value: str | None) -> int:
    if not value:
        return int(time.time())
    if value.isdigit():
        return int(value)
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


# ---------------------------------------------------------------- lorem

def lorem_words(rng: random.Random, n: int) -> str:
    return " ".join(rng.choice(LOREM) for _ in range(n))


def lorem_sentence(rng: random.Random, lo: int = 6, hi: int = 14) -> str:
    s = lorem_words(rng, rng.randint(lo, hi))
    return s[0].upper() + s[1:] + "."


def lorem_user(rng: random.Random) -> str:
    a, b = rng.choice(LOREM), rng.choice(LOREM)
    return rng.choice([f"{a}-{b}", f"{a}{b}", f"{a}{rng.randint(1, 99)}", a + "s"])


def fake_notes(rng: random.Random, n: int, op: str) -> list[dict]:
    notes = []
    for _ in range(min(n, 30)):
        if rng.random() < 0.55:
            notes.append({"user": lorem_user(rng), "action": "liked"})
        else:
            notes.append({"user": lorem_user(rng), "action": "reblogged", "from": rng.choice([op, lorem_user(rng)])})
    notes.append({"user": op, "action": "posted"})
    return notes


def seed_posts(count: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    now = int(time.time())
    posts = []
    for i in range(count):
        kind = rng.choices(["photo", "text", "quote"], weights=[7, 2, 1])[0]
        ts = now - rng.randint(1, 6 * 365) * 86400 - i
        op = lorem_user(rng)
        post = {
            "type": kind,
            "date": ts,
            "tags": [rng.choice(LOREM) for _ in range(rng.randint(0, 3))],
            "notes": rng.randint(3, 400),
            "source": op if rng.random() < 0.6 else None,
        }
        if kind == "photo":
            n_imgs = 1 if rng.random() < 0.8 else rng.randint(2, 3)
            post["images"] = [f"https://picsum.photos/seed/bee{seed}-{i}-{k}/720/560" for k in range(n_imgs)]
            post["caption"] = lorem_sentence(rng) if rng.random() < 0.5 else ""
        elif kind == "text":
            post["title"] = lorem_words(rng, 3).title() if rng.random() < 0.3 else ""
            post["body"] = "\n\n".join(lorem_sentence(rng, 5, 12) for _ in range(rng.randint(1, 3)))
        else:
            post["text"] = lorem_sentence(rng, 6, 12)
            post["attribution"] = lorem_words(rng, 2).title()
        post["note_list"] = fake_notes(rng, post["notes"], op)
        posts.append(post)
    return posts


# ---------------------------------------------------------------- rendering

esc = partial(html.escape, quote=True)


def rich(text: str, raw: bool) -> str:
    """Plain text -> escaped paragraphs; raw HTML passes through."""
    if raw:
        return text
    paras = [p.strip() for p in text.replace("\r", "").split("\n\n") if p.strip()]
    return "".join(f"<p>{esc(p).replace(chr(10), '<br>')}</p>" for p in paras)


def fmt_date(ts: int) -> str:
    d = datetime.fromtimestamp(ts, tz=timezone.utc)
    return f"{d:%B} {d.day}, {d.year}"


def rel_date(ts: int) -> str:
    secs = int(time.time()) - ts
    for name, size in (("year", 31536000), ("month", 2592000), ("week", 604800), ("day", 86400), ("hour", 3600), ("minute", 60)):
        n = secs // size
        if n >= 1:
            return f"{n} {name}{'s' if n > 1 else ''} ago"
    return "just now"


def hex_tile(post: dict, root: str) -> str:
    kind = post["type"]
    raw = post.get("html", False)
    if kind == "photo" and post.get("images"):
        inner = f'<img class="cover" src="{esc(post["images"][0])}" alt="" loading="lazy">'
    elif kind == "quote":
        inner = (f'<div class="caption"><div><q>{esc(post.get("text", ""))}</q>'
                 f'<small>{esc(post.get("attribution", ""))}</small></div></div>')
    else:
        body = post.get("title") and f"<p><b>{esc(post['title'])}</b></p>" or ""
        body += rich(post.get("body") or post.get("caption", ""), raw)
        inner = f'<div class="caption"><div>{body}</div></div>'
    return (
        f'<article class="entry {kind}_post">'
        f'<a class="quick" href="{root}post/{post["id"]}/">'
        f'<div data-ts="{post["date"]}">{rel_date(post["date"])}</div>'
        f'<i class="far fa-eye"></i></a>{inner}</article>'
    )


def note_line(note: dict) -> str:
    who = f'<a href="#">{esc(note["user"])}</a>'
    action = note.get("action", "liked")
    if action == "reblogged":
        frm = note.get("from")
        tail = f' from <a href="#">{esc(frm)}</a>' if frm else ""
        return f"<li>{who} reblogged this{tail}</li>"
    if action == "posted":
        return f"<li>{who} posted this</li>"
    if action == "replied":
        return f'<li>{who} said: {esc(note.get("text", ""))}</li>'
    return f"<li>{who} {esc(action)} this</li>"


def permalink_body(post: dict, prev_post: dict | None, next_post: dict | None, root: str) -> str:
    kind = post["type"]
    raw = post.get("html", False)
    if kind == "photo":
        imgs = "".join(f'<img src="{esc(u)}" alt="">' for u in post.get("images", []))
        cap = post.get("caption")
        body = imgs + (f'<div class="photo-caption">{rich(cap, raw)}</div>' if cap else "")
    elif kind == "quote":
        body = (f'<blockquote>&ldquo;{esc(post.get("text", ""))}&rdquo;</blockquote>'
                f'<div class="quote-src">&mdash; {esc(post.get("attribution", ""))}</div>')
    else:
        title = f"<h2>{esc(post['title'])}</h2>" if post.get("title") else ""
        body = f'{title}<div class="body">{rich(post.get("body", ""), raw)}</div>'
    tags = ""
    if post.get("tags"):
        tags = '<div class="tags">' + "".join(f'<a href="#">#{esc(t)}</a>' for t in post["tags"]) + "</div>"
    src = post.get("source")
    src_tag = f'<a class="src-tag" href="#">{esc(src)}</a>' if src else ""
    box_pad = "" if src else ' style="padding-top:20px"'

    n = post.get("notes", 0)
    prev_link = f'<a href="{root}post/{prev_post["id"]}/">Previous Post</a>' if prev_post else "<span>Previous Post</span>"
    next_link = f'<a href="{root}post/{next_post["id"]}/">Next Post</a>' if next_post else "<span>Next Post</span>"

    notes = ""
    note_list = post.get("note_list") or []
    if note_list:
        items = "".join(note_line(x) for x in note_list)
        quote = ""
        if kind == "photo" and post.get("caption"):
            quote = f'<div class="note-quote">{esc(post["caption"])}</div>'
        notes = f'<section class="notes"><ol>{items}</ol>{quote}<div class="count">{n} notes</div></section>'

    return f"""
<div class="perma">
  <div class="perma-box"{box_pad}>{src_tag}
    <div class="perma-frame">{body}{tags}</div>
  </div>
  <div class="perma-meta">
    <span class="posted">Posted on {fmt_date(post["date"])} with {n} notes</span>
    <span class="actions"><i class="fas fa-sync-alt"></i><i class="fas fa-heart"></i></span>
  </div>
  <nav class="perma-nav">{prev_link}{next_link}</nav>
  {notes}
</div>"""


def pagination(page: int, total: int, root: str) -> str:
    if total <= 1:
        return ""

    def href(n: int) -> str:
        return f"{root}index.html" if n == 1 else f"{root}page/{n}/"

    parts = []
    if page > 1:
        parts.append(f'<a class="word" href="{href(page - 1)}">Prev</a>')
    for n in range(1, total + 1):
        if n == page:
            parts.append(f'<span class="current">{n}</span>')
        else:
            parts.append(f'<a href="{href(n)}">{n}</a>')
    if page < total:
        parts.append(f'<a class="word" href="{href(page + 1)}">Next</a>')
    return f'<div class="pagination">{"".join(parts)}</div>'


def layout(site: dict, root: str, title: str, main: str, extra_head: str = "") -> str:
    desc_link = site.get("description_link") or {}
    link_html = (f'<br><a href="{esc(desc_link["url"])}">{esc(desc_link["text"])}</a>'
                 if desc_link.get("text") else "")
    pages = "".join(f'<li><a href="{esc(p["url"])}">{esc(p["title"])}</a></li>' for p in site.get("pages", []))
    credit = site.get("credit") or {}
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;700&display=swap">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css">
<link rel="stylesheet" href="{root}static/style.css">
<style>:root{{--accent:{esc(site.get("accent", "#e7748d"))}}}</style>
{extra_head}
</head>
<body>
<div class="layout">
  <aside class="aside">
    <div class="card">
      <div class="card-banner" style="background-image:url('{esc(site["banner"])}')"></div>
      <img class="card-avatar" src="{esc(site["avatar"])}" alt="">
      <div class="card-text">
        <b class="card-title">{esc(site["title"])}</b>
        <div class="card-desc">{esc(site["description"])}{link_html}</div>
      </div>
      <div class="nav">
        <button class="nav-btn" type="button" aria-label="Open navigation">
          <span class="plus">+</span>
          <span class="icons">
            <a href="{root}index.html" title="Home"><i class="fas fa-redo-alt"></i></a>
            <a href="{esc(site.get("ask_url", "#"))}" title="Ask"><i class="fas fa-inbox"></i></a>
            <a href="#" data-open-menu title="Menu"><i class="fas fa-bars"></i></a>
            <a href="{root}archive.html" title="Archive"><i class="fas fa-calendar"></i></a>
            <a href="{esc(credit.get("url", "#"))}" title="Theme"><i class="fas fa-egg"></i></a>
          </span>
        </button>
      </div>
    </div>
    <div class="menu">
      <div class="close-menu">Close Menu</div>
      <ul>{pages}</ul>
    </div>
  </aside>
  <main class="content">
    <section class="search-bar">
      <form data-root="{root}"><input name="q" type="text" placeholder="Search"></form>
    </section>
    {main}
    <p class="credit"><a href="{esc(credit.get("url", "#"))}">{esc(credit.get("text", ""))}</a></p>
  </main>
</div>
<script src="{root}static/app.js"></script>
</body>
</html>
"""


SEARCH_JS = """
<script>
(function(){
  var q = new URLSearchParams(location.search).get('q') || '';
  document.querySelector('.search-bar input').value = q;
  var tiles = window.__TILES__, needle = q.toLowerCase(), out = [];
  tiles.forEach(function(t){ if (t.text.indexOf(needle) !== -1) out.push(t.html); });
  document.querySelector('.hive').innerHTML = out.join('') ||
    '<p style="grid-column:1/-1;text-align:center;color:var(--accent)">No posts found for "' +
    q.replace(/[<>&"]/g, '') + '"</p>';
})();
</script>"""


def search_text(post: dict) -> str:
    fields = [post.get(k) or "" for k in ("title", "body", "caption", "text", "attribution", "source")]
    return " ".join(fields + post.get("tags", [])).lower()


def build(out: Path = DIST) -> int:
    site = load_site()
    posts = sorted(load_posts(), key=lambda p: p["date"], reverse=True)
    per = max(1, int(site.get("per_page", 12)))
    pages = [posts[i:i + per] for i in range(0, len(posts), per)] or [[]]

    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(STATIC, out / "static")

    for i, chunk in enumerate(pages, start=1):
        root = "" if i == 1 else "../../"
        tiles = "".join(hex_tile(p, root) for p in chunk)
        main = f'<section class="hive">{tiles}</section>{pagination(i, len(pages), root)}'
        path = out / "index.html" if i == 1 else out / "page" / str(i) / "index.html"
        path.parent.mkdir(parents=True, exist_ok=True)
        title = site["title"] if i == 1 else f'{site["title"]} - page {i}'
        path.write_text(layout(site, root, title, main), encoding="utf-8")

    for idx, post in enumerate(posts):
        root = "../../"
        newer = posts[idx - 1] if idx > 0 else None
        older = posts[idx + 1] if idx + 1 < len(posts) else None
        main = permalink_body(post, newer, older, root)
        path = out / "post" / str(post["id"]) / "index.html"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(layout(site, root, site["title"], main), encoding="utf-8")

    archive = f'<section class="hive">{"".join(hex_tile(p, "") for p in posts)}</section>'
    (out / "archive.html").write_text(layout(site, "", f'{site["title"]} - archive', archive), encoding="utf-8")

    index = [{"text": search_text(p), "html": hex_tile(p, "")} for p in posts]
    data = "<script>window.__TILES__=" + json.dumps(index).replace("</", "<\\/") + ";</script>"
    search_main = '<section class="hive"></section>' + data + SEARCH_JS
    (out / "search.html").write_text(layout(site, "", f'{site["title"]} - search', search_main), encoding="utf-8")
    return len(posts)


# ---------------------------------------------------------------- CLI

def read_arg(value: str | None) -> str | None:
    """`-` reads the value from stdin, `@file` reads it from a file."""
    if value == "-":
        return sys.stdin.read()
    if value and value.startswith("@"):
        return Path(value[1:]).expanduser().read_text(encoding="utf-8")
    return value


def cmd_add(args: argparse.Namespace) -> None:
    posts = load_posts()
    post: dict = {
        "id": next_id(posts),
        "type": args.type,
        "date": parse_date(args.date),
        "tags": [t.strip() for t in (args.tags or "").split(",") if t.strip()],
        "notes": args.notes,
        "source": args.source,
        "html": args.html,
    }
    if args.type == "photo":
        if not args.image:
            sys.exit("photo posts need at least one --image")
        post["images"] = args.image
        post["caption"] = read_arg(args.caption) or ""
    elif args.type == "text":
        body = read_arg(args.body)
        if not body:
            sys.exit("text posts need --body (use - for stdin or @file)")
        post["title"] = args.title or ""
        post["body"] = body
    else:
        text = read_arg(args.text)
        if not text:
            sys.exit("quote posts need --text")
        post["text"] = text
        post["attribution"] = args.attribution or ""
    posts.append(post)
    save_posts(posts)
    print(f"added {args.type} post #{post['id']}")
    if not args.no_build:
        build()


def cmd_import(args: argparse.Namespace) -> None:
    incoming = json.loads(read_arg(args.file if args.file == "-" else "@" + args.file))
    if isinstance(incoming, dict):
        incoming = [incoming]
    posts = [] if args.replace else load_posts()
    for item in incoming:
        item = dict(item)
        item["id"] = next_id(posts)
        item["date"] = parse_date(str(item["date"])) if item.get("date") else int(time.time())
        item.setdefault("type", "photo" if item.get("images") else "text")
        item.setdefault("tags", [])
        item.setdefault("notes", 0)
        posts.append(item)
    save_posts(posts)
    print(f"imported {len(incoming)} post(s), {len(posts)} total")
    if not args.no_build:
        build()


def cmd_seed(args: argparse.Namespace) -> None:
    posts = [] if args.replace else load_posts()
    for p in seed_posts(args.count, args.seed):
        p["id"] = next_id(posts)
        posts.append(p)
    save_posts(posts)
    print(f"seeded {args.count} lorem posts, {len(posts)} total")
    if not args.no_build:
        build()


def cmd_list(args: argparse.Namespace) -> None:
    for p in sorted(load_posts(), key=lambda p: p["date"], reverse=True):
        label = p.get("title") or p.get("caption") or p.get("body") or p.get("text") or (p.get("images") or [""])[0]
        label = " ".join(str(label).split())[:60]
        print(f"#{p['id']:<4} {p['type']:<6} {fmt_date(p['date']):<20} {label}")


def cmd_rm(args: argparse.Namespace) -> None:
    posts = load_posts()
    keep = [p for p in posts if p["id"] not in args.ids]
    removed = len(posts) - len(keep)
    save_posts(keep)
    print(f"removed {removed} post(s)")
    if not args.no_build:
        build()


def cmd_clear(args: argparse.Namespace) -> None:
    save_posts([])
    print("cleared all posts")
    if not args.no_build:
        build()


def cmd_config(args: argparse.Namespace) -> None:
    site = load_json(SITE_FILE, {})
    if not args.pairs:
        print(json.dumps(load_site(), indent=2, ensure_ascii=False))
        return
    for pair in args.pairs:
        key, _, value = pair.partition("=")
        try:
            site[key] = json.loads(value)
        except json.JSONDecodeError:
            site[key] = value
    save_json(SITE_FILE, site)
    print("saved site config")
    if not args.no_build:
        build()


def cmd_build(args: argparse.Namespace) -> None:
    n = build()
    print(f"built {n} post(s) into {DIST}")


def cmd_serve(args: argparse.Namespace) -> None:
    build()
    handler = partial(SimpleHTTPRequestHandler, directory=str(DIST))
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    print(f"serving http://127.0.0.1:{args.port}/  (ctrl+c to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


def main() -> None:
    ap = argparse.ArgumentParser(prog="beehive", description="Honeycomb blog generator")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def with_build_flag(p: argparse.ArgumentParser) -> argparse.ArgumentParser:
        p.add_argument("--no-build", action="store_true", help="skip rebuilding dist/")
        return p

    add = with_build_flag(sub.add_parser("add", help="add a post"))
    add.add_argument("type", choices=["photo", "text", "quote"])
    add.add_argument("--image", action="append", help="image URL or path (repeat for photosets)")
    add.add_argument("--caption", help="photo caption (- for stdin, @file)")
    add.add_argument("--title")
    add.add_argument("--body", help="text body (- for stdin, @file); blank lines split paragraphs")
    add.add_argument("--text", help="quote text")
    add.add_argument("--attribution", help="quote source")
    add.add_argument("--date", help="ISO date or unix timestamp (default now)")
    add.add_argument("--tags", help="comma separated")
    add.add_argument("--notes", type=int, default=0, help="note count to display")
    add.add_argument("--source", help="reblog source name shown as a tag on the permalink")
    add.add_argument("--html", action="store_true", help="treat body/caption as raw HTML")
    add.set_defaults(func=cmd_add)

    imp = with_build_flag(sub.add_parser("import", help="import posts from a JSON file (or - for stdin)"))
    imp.add_argument("file")
    imp.add_argument("--replace", action="store_true", help="drop existing posts first")
    imp.set_defaults(func=cmd_import)

    seed = with_build_flag(sub.add_parser("seed", help="add lorem ipsum posts"))
    seed.add_argument("-n", "--count", type=int, default=24)
    seed.add_argument("--seed", type=int, default=7)
    seed.add_argument("--replace", action="store_true")
    seed.set_defaults(func=cmd_seed)

    sub.add_parser("list", help="list posts").set_defaults(func=cmd_list)

    rm = with_build_flag(sub.add_parser("rm", help="remove posts by id"))
    rm.add_argument("ids", type=int, nargs="+")
    rm.set_defaults(func=cmd_rm)

    with_build_flag(sub.add_parser("clear", help="remove all posts")).set_defaults(func=cmd_clear)

    cfg = with_build_flag(sub.add_parser("config", help="show or set site settings: key=value (JSON values ok)"))
    cfg.add_argument("pairs", nargs="*")
    cfg.set_defaults(func=cmd_config)

    sub.add_parser("build", help="render dist/").set_defaults(func=cmd_build)

    srv = sub.add_parser("serve", help="build and serve dist/ locally")
    srv.add_argument("--port", type=int, default=8740)
    srv.set_defaults(func=cmd_serve)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
