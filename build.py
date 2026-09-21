#!/usr/bin/env python3
"""把 posts/*.md 构建成一个静态博客站点。

    python3 build.py                # 本地预览，产物在 _site/
    python3 build.py --base /blog   # GitHub Pages 项目站（CI 用）

新增文章：在 posts/ 下放一个 .md，开头写 frontmatter（title / date / slug /
summary / tags）。图放 posts/figures/，正文里用 ![图 N](figures/xxx.svg)
引用。推到 main 后 GitHub Actions 会自动构建发布。
"""
from __future__ import annotations
import argparse, html, re, shutil, sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BLOG, FIGS, OUT = ROOT / "posts", ROOT / "posts" / "figures", ROOT / "_site"

SITE = {
    "title": "推理工程笔记",
    "tagline": "把模型放进生产系统时，那些真正决定成败的细节。",
    "author": "Albert",
    "url": "https://aflowx.github.io/blog",
    "repo": "https://github.com/aflowx/blog",
}

# ---------------------------------------------------------------- frontmatter
def split_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    _, fm, body = text.split("---", 2)
    meta: dict = {}
    for line in fm.strip().split("\n"):
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        v = v.strip()
        if v.startswith("[") and v.endswith("]"):
            meta[k.strip()] = [x.strip() for x in v[1:-1].split(",") if x.strip()]
        else:
            meta[k.strip()] = v.strip('"').strip("'")
    return meta, body.lstrip("\n")

# ---------------------------------------------------------------- markdown
def inline(t: str) -> str:
    t = html.escape(t)
    t = re.sub(r"`([^`]+)`", lambda m: f"<code>{m.group(1)}</code>", t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', t)
    return t

def render(md: str, base: str) -> str:
    out: list[str] = []
    lines = md.split("\n")
    i, in_table = 0, False
    while i < len(lines):
        ln = lines[i]

        if ln.startswith("```"):
            lang = ln[3:].strip() or "text"
            body: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                body.append(lines[i]); i += 1
            code = html.escape("\n".join(body))
            out.append(f'<figure class="code"><figcaption>{lang}</figcaption>'
                       f"<pre><code>{code}</code></pre></figure>")
            i += 1; continue

        if ln.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip("|").split("|")]
                if not set("".join(cells)) <= set("-: "):
                    rows.append(cells)
                i += 1
            if rows:
                head = "".join(f"<th>{inline(c)}</th>" for c in rows[0])
                body = "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>"
                               for r in rows[1:])
                out.append(f"<div class='tablewrap'><table><thead><tr>{head}</tr></thead>"
                           f"<tbody>{body}</tbody></table></div>")
            continue

        if m := re.match(r"^!\[(.*?)\]\((.*?)\)$", ln):
            src = m.group(2)
            if src.startswith("figures/"):
                src = f"{base}/{src}"
            cap = ""
            if i + 1 < len(lines) and lines[i + 1].startswith("*图 "):
                cap = f"<figcaption>{inline(lines[i+1].strip().strip('*'))}</figcaption>"
                i += 1
            out.append(f'<figure class="fig"><img src="{src}" alt="{html.escape(m.group(1))}" loading="lazy">{cap}</figure>')
            i += 1; continue

        if ln.startswith("### "): out.append(f"<h3>{inline(ln[4:])}</h3>")
        elif ln.startswith("## "):
            t = inline(ln[3:]); anchor = re.sub(r"[^\w一-鿿]+", "-", ln[3:]).strip("-")
            out.append(f'<h2 id="{anchor}">{t}</h2>')
        elif ln.startswith("> "): out.append(f"<blockquote>{inline(ln[2:])}</blockquote>")
        elif ln.strip() == "---": out.append("<hr>")
        elif ln.strip().startswith("*") and ln.strip().endswith("*") and len(ln) > 30:
            out.append(f'<p class="note">{inline(ln.strip().strip("*"))}</p>')
        elif ln.strip(): out.append(f"<p>{inline(ln)}</p>")
        i += 1
    return "\n".join(out)

# ---------------------------------------------------------------- templates
def shell(base: str, title: str, desc: str, body: str, is_post: bool) -> str:
    home = base or "/"
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(desc)}">
<meta property="og:title" content="{html.escape(title)}">
<meta property="og:description" content="{html.escape(desc)}">
<meta property="og:type" content="{'article' if is_post else 'website'}">
<link rel="alternate" type="application/rss+xml" title="{SITE['title']}" href="{base}/feed.xml">
<link rel="stylesheet" href="{base}/style.css">
</head><body>
<header class="site">
  <a class="brand" href="{home}">{SITE['title']}</a>
  <nav><a href="{SITE['repo']}">GitHub</a><a href="{base}/feed.xml">RSS</a></nav>
</header>
<main>{body}</main>
<footer class="site">
  <p>{SITE['tagline']}</p>
  <p class="dim">© {date.today().year} {SITE['author']} · 内容与代码在 <a href="{SITE['repo']}">GitHub</a></p>
</footer>
</body></html>"""

STYLE = """
:root{
  --bg:#fffdf8; --fg:#24304a; --dim:#66728b; --rule:#eceef4;
  --accent:#2f8f74; --card:#ffffff; --code-bg:#1e293b; --code-fg:#e2e8f0;
  --measure:46rem;
}
@media (prefers-color-scheme:dark){
  :root{ --bg:#14161c; --fg:#e6e8ee; --dim:#98a0b3; --rule:#252a35;
         --accent:#6fc9aa; --card:#1b1e26; --code-bg:#11141a; --code-fg:#dbe2ee; }
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);
  font:17px/1.85 -apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Noto Sans SC",sans-serif;
  letter-spacing:.01em}
main{max-width:var(--measure);margin:0 auto;padding:0 1.25rem 6rem}
a{color:var(--accent);text-decoration:none;border-bottom:1px solid transparent}
a:hover{border-bottom-color:currentColor}

header.site{max-width:var(--measure);margin:0 auto;padding:1.75rem 1.25rem;
  display:flex;align-items:baseline;justify-content:space-between;gap:1rem;flex-wrap:wrap}
.brand{font-weight:700;font-size:1.05rem;color:var(--fg)}
header.site nav a{margin-left:1.1rem;font-size:.9rem;color:var(--dim)}

h1{font-size:1.95rem;line-height:1.35;margin:.5rem 0 .6rem;letter-spacing:-.01em}
h2{font-size:1.32rem;margin:3.2rem 0 1rem;padding-top:1.1rem;border-top:1px solid var(--rule)}
h3{font-size:1.08rem;margin:2.2rem 0 .7rem;color:var(--fg)}
p{margin:0 0 1.15rem}
strong{font-weight:650}
hr{border:0;border-top:1px solid var(--rule);margin:2.6rem 0}
blockquote{margin:0 0 1.2rem;padding:.85rem 1.1rem;background:var(--card);
  border-left:3px solid var(--accent);border-radius:0 8px 8px 0;color:var(--dim);font-size:.96rem}
code{background:var(--rule);padding:.12em .4em;border-radius:4px;font-size:.88em;
  font-family:ui-monospace,SFMono-Regular,Menlo,monospace}

figure{margin:0 0 1.6rem}
figure.code{background:var(--code-bg);border-radius:10px;overflow:hidden}
figure.code figcaption{padding:.55rem .95rem;font:.78rem ui-monospace,Menlo,monospace;
  color:#7b8798;border-bottom:1px solid rgba(255,255,255,.07)}
figure.code pre{margin:0;padding:.95rem 1.1rem;overflow-x:auto}
figure.code code{background:none;padding:0;color:var(--code-fg);font-size:.84rem;line-height:1.7}

figure.fig{margin:2rem 0 2.2rem}
figure.fig img{width:100%;display:block;border-radius:12px;background:#fffdf8;
  border:1px solid var(--rule)}
figure.fig figcaption,p.note{font-size:.86rem;line-height:1.7;color:var(--dim);
  margin:.7rem 0 0;text-align:center}
p.note{text-align:left;margin:0 0 1.15rem}

.tablewrap{overflow-x:auto;margin:0 0 1.6rem}
table{border-collapse:collapse;width:100%;font-size:.92rem}
th,td{border-bottom:1px solid var(--rule);padding:.55rem .7rem;text-align:left;vertical-align:top}
th{font-weight:650;background:var(--card)}

.meta{color:var(--dim);font-size:.88rem;margin:0 0 2.4rem}
.tag{display:inline-block;background:var(--card);border:1px solid var(--rule);
  border-radius:999px;padding:.08rem .6rem;margin-right:.35rem;font-size:.78rem;color:var(--dim)}

.hero{padding:1rem 0 2.6rem;border-bottom:1px solid var(--rule);margin-bottom:2.2rem}
.hero p{color:var(--dim);margin:0}
.postlist{list-style:none;padding:0;margin:0}
.postlist li{padding:1.6rem 0;border-bottom:1px solid var(--rule)}
.postlist h2{font-size:1.2rem;margin:0 0 .35rem;border:0;padding:0}
.postlist .sum{color:var(--dim);font-size:.95rem;margin:.4rem 0 .55rem}
.postlist time{color:var(--dim);font-size:.82rem;font-variant-numeric:tabular-nums}

footer.site{max-width:var(--measure);margin:0 auto;padding:2rem 1.25rem 3rem;
  border-top:1px solid var(--rule);color:var(--dim);font-size:.86rem}
footer.site p{margin:0 0 .35rem}
.dim{color:var(--dim)}
@media (max-width:640px){ body{font-size:16px} h1{font-size:1.6rem} main{padding-bottom:4rem} }
"""

# ---------------------------------------------------------------- build
def build(base: str) -> None:
    if OUT.exists(): shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    (OUT / "style.css").write_text(STYLE)
    (OUT / "figures").mkdir()
    for f in sorted(FIGS.glob("*.svg")):
        shutil.copy(f, OUT / "figures" / f.name)

    posts = []
    for md_path in sorted(BLOG.glob("*.md")):
        meta, body = split_frontmatter(md_path.read_text())
        if not meta.get("title"):
            print(f"  跳过 {md_path.name}（没有 frontmatter）"); continue
        slug = meta.get("slug") or md_path.stem
        posts.append({**meta, "slug": slug, "body": body})

    posts.sort(key=lambda p: str(p.get("date", "")), reverse=True)

    for p in posts:
        tags = "".join(f'<span class="tag">{html.escape(t)}</span>' for t in p.get("tags", []))
        article = (f"<article><h1>{html.escape(p['title'])}</h1>"
                   f"<p class='meta'><time>{p.get('date','')}</time> · {SITE['author']}<br>{tags}</p>"
                   f"{render(p['body'], base)}</article>")
        d = OUT / "posts" / p["slug"]; d.mkdir(parents=True)
        (d / "index.html").write_text(shell(base, p["title"], p.get("summary", ""), article, True))

    items = "".join(
        f"<li><h2><a href='{base}/posts/{p['slug']}/'>{html.escape(p['title'])}</a></h2>"
        f"<time>{p.get('date','')}</time>"
        f"<p class='sum'>{html.escape(p.get('summary',''))}</p></li>" for p in posts)
    index = (f"<div class='hero'><h1>{SITE['title']}</h1><p>{SITE['tagline']}</p></div>"
             f"<ul class='postlist'>{items}</ul>")
    (OUT / "index.html").write_text(shell(base, SITE["title"], SITE["tagline"], index, False))

    rss = "".join(
        f"<item><title>{html.escape(p['title'])}</title>"
        f"<link>{SITE['url']}/posts/{p['slug']}/</link>"
        f"<guid>{SITE['url']}/posts/{p['slug']}/</guid>"
        f"<description>{html.escape(p.get('summary',''))}</description></item>" for p in posts)
    (OUT / "feed.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>'
        f"<title>{SITE['title']}</title><link>{SITE['url']}</link>"
        f"<description>{SITE['tagline']}</description>{rss}</channel></rss>")
    (OUT / ".nojekyll").write_text("")

    print(f"✓ {len(posts)} 篇文章 → {OUT.relative_to(ROOT)}  (base={base or '/'})")
    for p in posts:
        print(f"    /posts/{p['slug']}/  {p['title']}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="", help="站点子路径，GitHub 项目站用 /blog")
    build(ap.parse_args().base)
