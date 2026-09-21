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
def shell(base: str, title: str, desc: str, body: str, is_post: bool, toc: str = "") -> str:
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
{'<div id="bar"></div>' if is_post else ''}
<header class="site"><div class="in">
  <a class="brand" href="{home}">{SITE['title']}</a>
  <nav><a href="{SITE['repo']}">GitHub</a><a href="{base}/feed.xml">RSS</a></nav>
</div></header>
<main>{body}</main>
<footer class="site"><div class="in">
  <p>{SITE['tagline']}</p>
  <p>© {date.today().year} {SITE['author']} · 内容与代码在 <a href="{SITE['repo']}">GitHub</a></p>
</div></footer>
{POST_JS if is_post else ''}
</body></html>"""

POST_JS = """<script>
(function(){
  var bar=document.getElementById('bar');
  var links=[].slice.call(document.querySelectorAll('aside.toc a'));
  var heads=links.map(function(a){return document.getElementById(a.getAttribute('href').slice(1));});
  function tick(){
    var h=document.documentElement;
    var p=h.scrollTop/(h.scrollHeight-h.clientHeight||1);
    if(bar) bar.style.width=(p*100).toFixed(2)+'%';
    var cur=-1;
    for(var i=0;i<heads.length;i++){ if(heads[i]&&heads[i].getBoundingClientRect().top<120) cur=i; }
    links.forEach(function(a,i){ a.classList.toggle('on', i===cur); });
  }
  addEventListener('scroll',tick,{passive:true}); addEventListener('resize',tick); tick();
})();
</script>"""

STYLE = """
:root{
  --paper:#FBFAF7; --ink:#1B2430; --body:#39414F; --dim:#8A93A3;
  --line:#E8E6E0; --hair:#F1EFEA; --card:#FFFFFF;
  --accent:#16876A; --accent-soft:#D9F0E6; --mint:#A8E0D1; --peach:#FFB4A2;
  --code-bg:#181D26; --code-fg:#DDE3EC; --code-dim:#6B7789;
  --measure:40rem;
}
@media (prefers-color-scheme:dark){
  :root{ --paper:#0E1116; --ink:#EDEFF3; --body:#C3C9D4; --dim:#7D8797;
         --line:#232833; --hair:#1A1E26; --card:#151A22;
         --accent:#6FC9AA; --accent-soft:#17362D;
         --code-bg:#0A0D12; --code-fg:#D7DEE9; --code-dim:#5B6675; }
}
*,*::before,*::after{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;scroll-behavior:smooth}
body{margin:0;background:var(--paper);color:var(--body);
  font:17px/1.9 -apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Noto Sans SC",sans-serif;
  -webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
.mono{font-family:ui-monospace,SFMono-Regular,"SF Mono",Menlo,monospace;
  font-variant-numeric:tabular-nums;letter-spacing:.02em}
a{color:inherit;text-decoration:none}

/* progress */
#bar{position:fixed;top:0;left:0;height:2px;width:0;background:var(--accent);z-index:99}

/* header */
header.site{position:sticky;top:0;z-index:20;background:color-mix(in srgb,var(--paper) 88%,transparent);
  backdrop-filter:saturate(1.4) blur(10px);border-bottom:1px solid var(--hair)}
header.site .in{max-width:64rem;margin:0 auto;padding:.85rem 1.5rem;
  display:flex;align-items:center;justify-content:space-between;gap:1rem}
.brand{font-weight:800;font-size:.95rem;color:var(--ink);letter-spacing:-.01em;
  display:inline-flex;align-items:center;gap:.5rem}
.brand::before{content:"";width:9px;height:9px;border-radius:3px;background:var(--accent)}
header.site nav a{font-size:.8rem;color:var(--dim);margin-left:1.1rem}
header.site nav a:hover{color:var(--accent)}

main{max-width:64rem;margin:0 auto;padding:0 1.5rem 7rem}

/* ---------- index ---------- */
.masthead{padding:5.5rem 0 3.5rem;border-bottom:1px solid var(--line)}
.masthead h1{font-size:clamp(2.2rem,6vw,3.4rem);line-height:1.1;margin:0 0 1rem;
  color:var(--ink);font-weight:850;letter-spacing:-.035em}
.masthead p{max-width:34rem;margin:0;color:var(--dim);font-size:1.02rem;line-height:1.8}
.masthead .rule{width:56px;height:4px;border-radius:2px;background:var(--accent);margin:0 0 1.6rem}

.postlist{list-style:none;padding:0;margin:0}
.postlist li{border-bottom:1px solid var(--line)}
.postlist a.card{display:block;padding:2.4rem 0;transition:padding-left .25s ease}
.postlist a.card:hover{padding-left:.7rem}
.postlist .kicker{display:flex;align-items:center;gap:.75rem;margin-bottom:.7rem}
.postlist time{font-size:.76rem;color:var(--dim)}
.postlist .dot{width:3px;height:3px;border-radius:50%;background:var(--line)}
.postlist h2{font-size:clamp(1.25rem,2.6vw,1.6rem);line-height:1.4;margin:0 0 .6rem;
  color:var(--ink);font-weight:750;letter-spacing:-.02em}
.postlist a.card:hover h2{color:var(--accent)}
.postlist .sum{margin:0 0 1rem;color:var(--dim);font-size:.95rem;line-height:1.85;max-width:44rem}
.more{font-size:.8rem;color:var(--accent);font-weight:600}

.tag{display:inline-block;font-size:.7rem;color:var(--dim);border:1px solid var(--line);
  border-radius:999px;padding:.1rem .58rem;margin-right:.3rem;background:var(--card)}

/* ---------- article ---------- */
.wrap{display:grid;grid-template-columns:minmax(0,var(--measure)) 1fr;gap:3.5rem;
  justify-content:center;padding-top:3.5rem}
@media (max-width:980px){ .wrap{display:block;padding-top:2.5rem} aside.toc{display:none} }

article{min-width:0;max-width:var(--measure)}
.post-head{margin-bottom:3rem}
.post-head .eyebrow{margin:0 0 1rem}
.post-head h1{font-size:clamp(1.85rem,4.2vw,2.6rem);line-height:1.28;margin:0 0 1.1rem;
  color:var(--ink);font-weight:850;letter-spacing:-.03em}
.post-head .meta{display:flex;align-items:center;gap:.7rem;font-size:.78rem;color:var(--dim);
  padding-bottom:1.6rem;border-bottom:1px solid var(--line)}

article h2{font-size:1.28rem;line-height:1.5;margin:3.6rem 0 1.1rem;color:var(--ink);
  font-weight:780;letter-spacing:-.015em;padding-left:.9rem;border-left:3px solid var(--accent);
  scroll-margin-top:5rem}
article h3{font-size:1.04rem;margin:2.4rem 0 .8rem;color:var(--ink);font-weight:700}
article p{margin:0 0 1.25rem}
article strong{color:var(--ink);font-weight:700}
article a[href]{color:var(--accent);border-bottom:1px solid var(--accent-soft)}
article a[href]:hover{border-bottom-color:var(--accent)}
hr{border:0;border-top:1px solid var(--line);margin:3rem 0}
blockquote{margin:0 0 1.35rem;padding:1rem 1.2rem;background:var(--card);
  border:1px solid var(--line);border-left:3px solid var(--accent);border-radius:0 10px 10px 0;
  color:var(--dim);font-size:.95rem;line-height:1.8}
code{background:var(--hair);color:var(--ink);padding:.12em .42em;border-radius:5px;
  font:500 .86em ui-monospace,SFMono-Regular,Menlo,monospace}

figure{margin:0 0 1.8rem}
figure.code{background:var(--code-bg);border-radius:12px;overflow:hidden;margin-bottom:1.8rem}
figure.code figcaption{padding:.6rem 1rem;font:.72rem ui-monospace,Menlo,monospace;
  color:var(--code-dim);letter-spacing:.08em;text-transform:uppercase;
  border-bottom:1px solid rgba(255,255,255,.06)}
figure.code pre{margin:0;padding:1rem 1.15rem;overflow-x:auto}
figure.code code{background:none;padding:0;color:var(--code-fg);font-size:.82rem;line-height:1.75}

figure.fig{margin:2.4rem 0 2.6rem}
@media (min-width:1100px){ figure.fig{width:calc(100% + 5rem);margin-left:-2.5rem} }
figure.fig img{width:100%;display:block;border-radius:14px;border:1px solid var(--line);
  background:#FBFAF7}
figure.fig figcaption{margin:.85rem 0 0;font-size:.82rem;line-height:1.75;color:var(--dim)}
p.note{font-size:.84rem;line-height:1.8;color:var(--dim);margin:0 0 1.25rem}

.tablewrap{overflow-x:auto;margin:0 0 1.8rem;border:1px solid var(--line);border-radius:12px}
table{border-collapse:collapse;width:100%;font-size:.88rem}
th,td{padding:.62rem .85rem;text-align:left;vertical-align:top;border-bottom:1px solid var(--hair)}
th{font-weight:700;color:var(--ink);background:var(--card);white-space:nowrap}
tbody tr:last-child td{border-bottom:0}

/* TOC rail */
aside.toc{position:sticky;top:5rem;align-self:start;max-height:calc(100vh - 8rem);overflow-y:auto;
  font-size:.82rem;line-height:1.6;padding-left:1.5rem;border-left:1px solid var(--line)}
aside.toc .lab{font-size:.68rem;letter-spacing:.14em;text-transform:uppercase;color:var(--dim);
  margin:0 0 .85rem;font-weight:700}
aside.toc ol{list-style:none;margin:0;padding:0;counter-reset:t}
aside.toc li{counter-increment:t;margin:0 0 .6rem}
aside.toc a{color:var(--dim);display:block;padding-left:1.6rem;position:relative}
aside.toc a::before{content:counter(t,decimal-leading-zero);position:absolute;left:0;
  font:600 .68rem ui-monospace,Menlo,monospace;color:var(--line)}
aside.toc a:hover,aside.toc a.on{color:var(--accent)}
aside.toc a.on::before{color:var(--accent)}

.post-foot{margin-top:4rem;padding-top:2rem;border-top:1px solid var(--line)}
.post-foot a{color:var(--accent);font-size:.9rem;font-weight:600}

footer.site{border-top:1px solid var(--line);margin-top:4rem}
footer.site .in{max-width:64rem;margin:0 auto;padding:2.2rem 1.5rem 3.5rem;
  color:var(--dim);font-size:.82rem;line-height:1.8}
footer.site a{color:var(--accent)}
@media (max-width:640px){ body{font-size:16px} .masthead{padding:3.2rem 0 2.4rem} }
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
        html_body = render(p["body"], base)
        heads = re.findall(r'<h2 id="([^"]+)">(.*?)</h2>', html_body)
        toc = ""
        if len(heads) > 2:
            items = "".join(f'<li><a href="#{a}">{re.sub(r"<[^>]+>", "", t)}</a></li>' for a, t in heads)
            toc = f'<aside class="toc"><p class="lab">目录</p><ol>{items}</ol></aside>'
        tags = "".join(f'<span class="tag">{html.escape(t)}</span>' for t in p.get("tags", []))
        mins = max(1, round(len(re.sub(r"<[^>]+>", "", html_body)) / 500))
        head = (f'<div class="post-head"><p class="eyebrow">{tags}</p>'
                f'<h1>{html.escape(p["title"])}</h1>'
                f'<p class="meta"><span class="mono">{p.get("date","")}</span>'
                f'<span class="dot"></span><span>{SITE["author"]}</span>'
                f'<span class="dot"></span><span class="mono">约 {mins} 分钟</span></p></div>')
        foot = f'<div class="post-foot"><a href="{base or "/"}">← 回到全部文章</a></div>'
        page = f'<div class="wrap"><article>{head}{html_body}{foot}</article>{toc}</div>'
        d = OUT / "posts" / p["slug"]; d.mkdir(parents=True)
        (d / "index.html").write_text(shell(base, p["title"], p.get("summary", ""), page, True, toc))

    items = "".join(
        f'<li><a class="card" href="{base}/posts/{p["slug"]}/">'
        f'<div class="kicker"><time class="mono">{p.get("date","")}</time>'
        f'<span class="dot"></span>'
        + "".join(f'<span class="tag">{html.escape(t)}</span>' for t in p.get("tags", [])) +
        f'</div><h2>{html.escape(p["title"])}</h2>'
        f'<p class="sum">{html.escape(p.get("summary",""))}</p>'
        f'<span class="more">读全文 →</span></a></li>' for p in posts)
    index = (f'<div class="masthead"><div class="rule"></div>'
             f'<h1>{SITE["title"]}</h1><p>{SITE["tagline"]}</p></div>'
             f'<ul class="postlist">{items}</ul>')
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
