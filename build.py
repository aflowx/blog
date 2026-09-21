#!/usr/bin/env python3
"""把 posts/*.md 构建成静态博客站点。

    python3 build.py                # 本地预览，产物在 _site/
    python3 build.py --base /blog   # GitHub Pages 项目站（CI 用）

新增文章：在 posts/ 下放一个 .md，开头写 frontmatter（title / date / slug /
summary / tags / cover）。图放 posts/figures/，正文里用 ![图 N](figures/xxx.svg)
引用。cover 省略时自动取正文第一张图。推到 main 后 Actions 自动发布。
"""
from __future__ import annotations
import argparse, html, json, re, shutil, sys
from datetime import datetime
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BLOG, FIGS, OUT = ROOT / "posts", ROOT / "posts" / "figures", ROOT / "_site"

SITE = {
    "title": "推理工程笔记",
    "tagline": "把模型放进生产系统时，那些真正决定成败的细节。",
    "author": "Albert",
    "url": "https://aflowx.github.io",
    "repo": "https://github.com/aflowx/blog",
}

# ── frontmatter ──────────────────────────────────────────────────────────────
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

# ── markdown ─────────────────────────────────────────────────────────────────
def inline(t: str) -> str:
    t = html.escape(t)
    t = re.sub(r"`([^`]+)`", lambda m: f'<code>{m.group(1)}</code>', t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', t)
    return t

def slugify(s: str) -> str:
    return re.sub(r"[^\w一-鿿]+", "-", s).strip("-")

def render(md: str, base: str) -> str:
    out, lines, i = [], md.split("\n"), 0
    while i < len(lines):
        ln = lines[i]

        if ln.startswith("```"):
            lang, body = ln[3:].strip() or "text", []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                body.append(lines[i]); i += 1
            out.append(f'<figure class="code"><figcaption><span class="chip">{lang}</span></figcaption>'
                       f'<pre><code>{html.escape(chr(10).join(body))}</code></pre></figure>')
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
                out.append(f'<div class="tablewrap"><table><thead><tr>{head}</tr></thead>'
                           f"<tbody>{body}</tbody></table></div>")
            continue

        if m := re.match(r"^!\[(.*?)\]\((.*?)\)$", ln):
            src = m.group(2)
            if not src.startswith(("http", "/")):
                src = f"{base}/{src}"
            cap, alt = "", m.group(1)
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and lines[j].startswith("*图 "):
                raw = lines[j].strip().strip("*")
                cap = f"<figcaption>{inline(raw)}</figcaption>"
                alt = re.sub(r"[`*]", "", re.sub(r"^图 \d+：", "", raw))[:160]
                i = j
            out.append(f'<figure class="fig"><img src="{src}" alt="{html.escape(alt)}" '
                       f'loading="lazy" decoding="async">{cap}</figure>')
            i += 1; continue

        if ln.startswith("### "):
            out.append(f"<h3>{inline(ln[4:])}</h3>")
        elif ln.startswith("## "):
            t = ln[3:]
            out.append(f'<h2 id="{slugify(t)}">{inline(t)}</h2>')
        elif ln.startswith("> "):
            out.append(f"<blockquote>{inline(ln[2:])}</blockquote>")
        elif ln.strip() == "---":
            out.append("<hr>")
        elif ln.strip().startswith("*") and ln.strip().endswith("*") and len(ln) > 30:
            out.append(f'<p class="note">{inline(ln.strip().strip("*"))}</p>')
        elif ln.strip():
            out.append(f"<p>{inline(ln)}</p>")
        i += 1
    return "\n".join(out)

# ── token 条：全站视觉签名，17 块里 3 块是答案 ────────────────────────────────
ANSWERS = {4, 9, 15}
def token_strip(n: int = 17) -> str:
    return ('<div class="strip" aria-hidden="true">'
            + "".join(f'<i class="{"on" if k in ANSWERS else ""}"'
                      f' style="--k:{k}"></i>' for k in range(n))
            + "</div>")

# ── shell ────────────────────────────────────────────────────────────────────
def shell(base: str, title: str, desc: str, body: str, is_post: bool,
          url: str = "", image: str = "", published: str = "", ld: str = "") -> str:
    home = base or "/"
    canon = f'{SITE["url"]}{url}'
    img = f'{SITE["url"]}{image}' if image else ""
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(desc)}">
<meta name="author" content="{SITE['author']}">
<link rel="canonical" href="{canon}">
<meta property="og:title" content="{html.escape(title)}">
<meta property="og:description" content="{html.escape(desc)}">
<meta property="og:type" content="{'article' if is_post else 'website'}">
<meta property="og:url" content="{canon}">
<meta property="og:site_name" content="{SITE['title']}">
<meta property="og:locale" content="zh_CN">
{f'<meta property="og:image" content="{img}">' if img else ''}
{f'<meta property="article:published_time" content="{published}">' if published else ''}
{f'<meta property="article:author" content="{SITE["author"]}">' if is_post else ''}
<meta name="twitter:card" content="{'summary_large_image' if img else 'summary'}">
<meta name="twitter:title" content="{html.escape(title)}">
<meta name="twitter:description" content="{html.escape(desc)}">
{f'<meta name="twitter:image" content="{img}">' if img else ''}
<link rel="icon" href="{base}/favicon.svg" type="image/svg+xml">
<link rel="alternate" type="application/rss+xml" title="{SITE['title']}" href="{base}/feed.xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<link rel="stylesheet" href="{base}/style.css">
{ld}
</head><body>
{'<div id="bar"></div>' if is_post else ''}
<header class="site"><div class="in">
  <a class="brand" href="{home}"><span class="mark" aria-hidden="true"></span>{SITE['title']}</a>
  <nav><a href="{base}/feed.xml">RSS</a></nav>
</div></header>
{body}
<footer class="site"><div class="in">
  <p class="tag-line">{SITE['tagline']}</p>
</div></footer>
{POST_JS if is_post else ''}
</body></html>"""

POST_JS = """<script>
(function(){
  var bar=document.getElementById('bar');
  var links=[].slice.call(document.querySelectorAll('.toc a'));
  var heads=links.map(function(a){return document.getElementById(a.getAttribute('href').slice(1));});
  function tick(){
    var h=document.documentElement;
    if(bar) bar.style.width=(h.scrollTop/(h.scrollHeight-h.clientHeight||1)*100).toFixed(2)+'%';
    var cur=-1;
    for(var i=0;i<heads.length;i++){ if(heads[i]&&heads[i].getBoundingClientRect().top<140) cur=i; }
    links.forEach(function(a,i){ a.classList.toggle('on', i===cur); });
  }
  addEventListener('scroll',tick,{passive:true}); addEventListener('resize',tick); tick();
})();
</script>"""

STYLE = """
:root{
  --paper:#FAF8F3; --raise:#FFFFFF; --ink:#1A2230; --body:#3A4351; --dim:#8B94A3;
  --line:#E7E4DC; --hair:#F0EDE6;
  --accent:#0E7C63; --accent-ink:#0B5F4C; --accent-wash:#E4F2EC;
  --mint:#A8E0D1; --peach:#FFB4A2; --lilac:#C9C4F0; --butter:#FFE9A8;
  --code-bg:#171C25; --code-fg:#DEE4EE; --code-dim:#6B7789;
  --measure:40rem; --page:66rem;
}
@media (prefers-color-scheme:dark){
  :root{ --paper:#0F1217; --raise:#171B22; --ink:#ECEEF2; --body:#BFC6D1; --dim:#7C8593;
         --line:#242A34; --hair:#1A1F27;
         --accent:#6FC9AA; --accent-ink:#8ED9BF; --accent-wash:#16302A;
         --code-bg:#0A0D12; --code-fg:#D9E0EA; --code-dim:#5C6674; }
}
*,*::before,*::after{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;scroll-behavior:smooth}
body{margin:0;background:var(--paper);color:var(--body);
  font:17px/1.9 -apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Noto Sans SC",sans-serif;
  -webkit-font-smoothing:antialiased}
a{color:inherit;text-decoration:none}
.mono{font-family:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,monospace;
  font-variant-numeric:tabular-nums;letter-spacing:.01em}
.dim{color:var(--dim)}

#bar{position:fixed;top:0;left:0;height:2px;width:0;background:var(--accent);z-index:99}

/* ── chip：全站结构母题 ───────────────────────────── */
.chip{display:inline-block;font-family:"IBM Plex Mono",ui-monospace,Menlo,monospace;
  font-size:.7rem;font-weight:500;line-height:1.7;padding:.05rem .48rem;border-radius:6px;
  background:var(--hair);color:var(--dim);border:1px solid var(--line)}
.chip.solid{background:var(--accent-wash);color:var(--accent-ink);border-color:transparent}

/* ── token 条 ──────────────────────────────────────── */
.strip{display:flex;gap:4px;flex-wrap:wrap}
.strip i{width:14px;height:14px;border-radius:4px;background:var(--line);display:block}
.strip i.on{background:var(--peach);animation:pop .5s cubic-bezier(.2,.9,.3,1.4) both;
  animation-delay:calc(var(--k) * 60ms + 200ms)}
@keyframes pop{from{transform:scale(.4);background:var(--line)}to{transform:scale(1)}}
@media (prefers-reduced-motion:reduce){ .strip i.on{animation:none} }

/* ── header ───────────────────────────────────────── */
header.site{position:sticky;top:0;z-index:20;background:var(--paper);border-bottom:1px solid var(--hair)}
header.site .in{max-width:var(--page);margin:0 auto;padding:.9rem 1.5rem;
  display:flex;align-items:center;justify-content:space-between;gap:1rem}
.brand{display:inline-flex;align-items:center;gap:.55rem;color:var(--ink);
  font-weight:800;font-size:.95rem;letter-spacing:-.01em}
.mark{width:10px;height:10px;border-radius:3px;background:var(--accent)}
header.site nav a{font-family:"IBM Plex Mono",ui-monospace,Menlo,monospace;
  font-size:.74rem;color:var(--dim);margin-left:1.2rem}
header.site nav a:hover{color:var(--accent)}

/* ── index ────────────────────────────────────────── */
.masthead{max-width:var(--page);margin:0 auto;padding:5rem 1.5rem 3rem}
.masthead h1{margin:1.3rem 0 .9rem;font-size:clamp(2.1rem,5.6vw,3.2rem);line-height:1.12;
  color:var(--ink);font-weight:850;letter-spacing:-.035em;text-wrap:balance}
.masthead p{margin:0;max-width:34rem;color:var(--dim);font-size:1rem;line-height:1.85}

.feed{max-width:var(--page);margin:0 auto;padding:0 1.5rem 6rem;
  display:grid;grid-template-columns:repeat(auto-fill,minmax(20rem,1fr));gap:2.6rem 2rem}
.entry.lead{grid-column:1/-1;display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,1fr);
  gap:2.4rem;align-items:start}
.entry.lead .cover{margin-bottom:0}
.entry.lead h2{font-size:clamp(1.5rem,3.2vw,2rem);line-height:1.34;margin:.15rem 0 .7rem}
.entry.lead .sum{font-size:.98rem;line-height:1.85}
@media (max-width:760px){ .entry.lead{display:block} .entry.lead .cover{margin-bottom:1.05rem} }
.entry{display:block;border-top:1px solid var(--line);padding-top:1.1rem}
.entry .cover{display:block;border-radius:12px;overflow:hidden;border:1px solid var(--line);
  background:var(--raise);margin-bottom:1.05rem;line-height:0}
.entry .cover img{width:100%;height:auto;display:block}
.entry:hover .cover{border-color:var(--accent)}
.entry .kicker{display:flex;align-items:center;gap:.5rem;margin-bottom:.6rem;flex-wrap:wrap}
.entry time{font-family:"IBM Plex Mono",ui-monospace,Menlo,monospace;font-size:.72rem;color:var(--dim)}
.entry h2{margin:0 0 .5rem;font-size:1.22rem;line-height:1.45;color:var(--ink);
  font-weight:760;letter-spacing:-.02em;text-wrap:balance}
.entry:hover h2{color:var(--accent)}
.entry .sum{margin:0;color:var(--dim);font-size:.9rem;line-height:1.8}

/* ── article ──────────────────────────────────────── */
.hero{background:var(--raise);border-bottom:1px solid var(--line)}
.hero .in{max-width:var(--page);margin:0 auto;padding:3.4rem 1.5rem 2.6rem}
.hero .strip{margin-bottom:1.6rem}
.hero h1{margin:0 0 1.1rem;max-width:26ch;font-size:clamp(1.9rem,4.4vw,2.8rem);line-height:1.24;
  color:var(--ink);font-weight:850;letter-spacing:-.032em;text-wrap:balance}
.hero .meta{display:flex;align-items:center;gap:.55rem;flex-wrap:wrap;
  font-family:"IBM Plex Mono",ui-monospace,Menlo,monospace;font-size:.74rem;color:var(--dim)}
.hero .meta .sep{width:3px;height:3px;border-radius:50%;background:var(--line)}

.wrap{max-width:var(--page);margin:0 auto;padding:3rem 1.5rem 6rem;
  display:grid;grid-template-columns:minmax(0,var(--measure)) 1fr;gap:4rem;justify-content:center}
@media (max-width:1000px){ .wrap{display:block} .toc{display:none} }
article{min-width:0;max-width:var(--measure)}

article h2{margin:3.6rem 0 1.15rem;font-size:1.3rem;line-height:1.5;color:var(--ink);
  font-weight:790;letter-spacing:-.018em;scroll-margin-top:5.5rem}
article h3{margin:2.4rem 0 .8rem;font-size:1.05rem;color:var(--ink);font-weight:720}
article p{margin:0 0 1.25rem}
article strong{color:var(--ink);font-weight:700}
article a[href]{color:var(--accent);border-bottom:1px solid var(--accent-wash)}
article a[href]:hover{border-bottom-color:var(--accent)}
article hr{border:0;border-top:1px solid var(--line);margin:3rem 0}
blockquote{margin:0 0 1.4rem;padding:1rem 1.2rem;background:var(--raise);
  border:1px solid var(--line);border-left:3px solid var(--accent);border-radius:0 10px 10px 0;
  color:var(--dim);font-size:.95rem;line-height:1.82}
article code{font-family:"IBM Plex Mono",ui-monospace,Menlo,monospace;font-size:.85em;
  background:var(--hair);color:var(--ink);padding:.1em .42em;border-radius:6px;
  border:1px solid var(--line)}

figure{margin:0 0 1.8rem}
figure.code{background:var(--code-bg);border-radius:12px;overflow:hidden}
figure.code figcaption{padding:.65rem .9rem;border-bottom:1px solid rgba(255,255,255,.06)}
figure.code .chip{background:rgba(255,255,255,.07);color:var(--code-dim);border-color:transparent}
figure.code pre{margin:0;padding:1rem 1.15rem;overflow-x:auto}
figure.code code{background:none;border:0;padding:0;color:var(--code-fg);
  font-family:"IBM Plex Mono",ui-monospace,Menlo,monospace;font-size:.82rem;line-height:1.78}

figure.fig{margin:2.4rem 0 2.6rem}
@media (min-width:1100px){ figure.fig{width:calc(100% + 4rem);margin-left:-2rem} }
figure.fig img{width:100%;display:block;border-radius:14px;border:1px solid var(--line)}
figure.fig figcaption{margin:.85rem 0 0;font-size:.82rem;line-height:1.78;color:var(--dim)}
p.note{margin:0 0 1.25rem;font-size:.84rem;line-height:1.82;color:var(--dim)}

.tablewrap{margin:0 0 1.8rem;overflow-x:auto;border:1px solid var(--line);border-radius:12px}
table{border-collapse:collapse;width:100%;font-size:.88rem}
th,td{padding:.64rem .85rem;text-align:left;vertical-align:top;border-bottom:1px solid var(--hair)}
th{font-weight:700;color:var(--ink);background:var(--raise);white-space:nowrap}
tbody tr:last-child td{border-bottom:0}
td{font-variant-numeric:tabular-nums}

/* ── TOC ──────────────────────────────────────────── */
.toc{position:sticky;top:5.5rem;align-self:start;max-height:calc(100vh - 8rem);overflow-y:auto}
.toc .lab{margin:0 0 1rem;font-family:"IBM Plex Mono",ui-monospace,Menlo,monospace;
  font-size:.66rem;letter-spacing:.16em;text-transform:uppercase;color:var(--dim)}
.toc ol{list-style:none;margin:0;padding:0;counter-reset:t;display:flex;flex-direction:column;gap:.55rem}
.toc li{counter-increment:t}
.toc a{display:grid;grid-template-columns:1.9rem 1fr;gap:.2rem;align-items:start;
  font-size:.82rem;line-height:1.55;color:var(--dim)}
.toc a::before{content:counter(t,decimal-leading-zero);
  font-family:"IBM Plex Mono",ui-monospace,Menlo,monospace;font-size:.66rem;
  color:var(--dim);opacity:.5;padding-top:.13rem}
.toc a:hover,.toc a.on{color:var(--accent)}
.toc a.on::before{color:var(--accent);opacity:1}

.post-foot{margin-top:4rem;padding-top:1.8rem;border-top:1px solid var(--line)}
.post-foot a{color:var(--accent);font-size:.9rem;font-weight:650}

footer.site{border-top:1px solid var(--line)}
footer.site .in{max-width:var(--page);margin:0 auto;padding:2.2rem 1.5rem 3.5rem;
  color:var(--dim);font-size:.84rem;line-height:1.8}
footer.site .tag-line{margin:0 0 .3rem}
footer.site p{margin:0}
footer.site a{color:var(--accent)}
@media (max-width:640px){ body{font-size:16px} .masthead{padding:3.2rem 1.5rem 2.2rem} }
"""

# ── build ────────────────────────────────────────────────────────────────────
def build(base: str) -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    (OUT / "style.css").write_text(STYLE)
    (OUT / "figures").mkdir()
    for f in sorted(FIGS.iterdir()):
        if f.suffix.lower() in {".svg", ".png", ".jpg", ".jpeg", ".webp", ".gif"}:
            shutil.copy(f, OUT / "figures" / f.name)
    (OUT / ".nojekyll").write_text("")

    posts = []
    for md_path in sorted(BLOG.glob("*.md")):
        meta, body = split_frontmatter(md_path.read_text())
        if not meta.get("title"):
            print(f"  跳过 {md_path.name}（缺 frontmatter）"); continue
        posts.append({**meta, "slug": meta.get("slug") or md_path.stem, "body": body})
    posts.sort(key=lambda p: str(p.get("date", "")), reverse=True)

    for p in posts:
        body_html = render(p["body"], base)
        heads = re.findall(r'<h2 id="([^"]+)">(.*?)</h2>', body_html)
        toc = ""
        if len(heads) > 2:
            li = "".join(f'<li><a href="#{a}"><span>{re.sub(r"<[^>]+>","",t)}</span></a></li>'
                         for a, t in heads)
            toc = f'<nav class="toc"><p class="lab">目录</p><ol>{li}</ol></nav>'
        chips = "".join(f'<span class="chip">{html.escape(t)}</span>' for t in p.get("tags", []))
        mins = max(1, round(len(re.sub(r"<[^>]+>", "", body_html)) / 500))
        hero = (f'<section class="hero"><div class="in">{token_strip()}'
                f'<h1>{html.escape(p["title"])}</h1>'
                f'<div class="meta"><span>{p.get("date","")}</span><span class="sep"></span>'
                f'<span>{SITE["author"]}</span><span class="sep"></span>'
                f'<span>约 {mins} 分钟</span><span class="sep"></span>{chips}</div></div></section>')
        foot = f'<div class="post-foot"><a href="{base or "/"}">← 全部文章</a></div>'
        page = hero + f'<div class="wrap"><article>{body_html}{foot}</article>{toc}</div>'
        d = OUT / "posts" / p["slug"]; d.mkdir(parents=True)
        cover = p.get("cover") or (re.search(r"!\[.*?\]\((figures/[^)]+)\)", p["body"]) or [None, ""])[1]
        purl = f'{base}/posts/{p["slug"]}/'
        ld = json.dumps({
            "@context": "https://schema.org", "@type": "BlogPosting",
            "headline": p["title"], "description": p.get("summary", ""),
            "datePublished": str(p.get("date", "")), "dateModified": str(p.get("date", "")),
            "author": {"@type": "Person", "name": SITE["author"]},
            "publisher": {"@type": "Organization", "name": SITE["title"]},
            "mainEntityOfPage": f'{SITE["url"]}{purl}',
            "inLanguage": "zh-CN",
            "keywords": ", ".join(p.get("tags", [])),
            **({"image": f'{SITE["url"]}{base}/{cover}'} if cover else {}),
        }, ensure_ascii=False)
        ld_tag = f'<script type="application/ld+json">{ld}</script>'
        (d / "index.html").write_text(shell(
            base, p["title"], p.get("summary", ""), page, True,
            url=purl, image=f"{base}/{cover}" if cover else "",
            published=str(p.get("date", "")), ld=ld_tag))

    cards = []
    for idx, p in enumerate(posts):
        cover = p.get("cover") or (re.search(r"!\[.*?\]\((figures/[^)]+)\)", p["body"]) or [None, ""])[1]
        img = (f'<span class="cover"><img src="{base}/{cover}" alt="" loading="lazy"></span>'
               if cover else "")
        chips = "".join(f'<span class="chip">{html.escape(t)}</span>' for t in p.get("tags", [])[:2])
        lead = " lead" if idx == 0 else ""
        cards.append(f'<a class="entry{lead}" href="{base}/posts/{p["slug"]}/">{img}'
                     f'<span class="body">'
                     f'<span class="kicker"><time>{p.get("date","")}</time>{chips}</span>'
                     f'<h2>{html.escape(p["title"])}</h2>'
                     f'<p class="sum">{html.escape(p.get("summary",""))}</p></span></a>')
    index = (f'<section class="masthead">{token_strip()}'
             f'<h1>{SITE["title"]}</h1><p>{SITE["tagline"]}</p></section>'
             f'<section class="feed">{"".join(cards)}</section>')
    site_ld = json.dumps({
        "@context": "https://schema.org", "@type": "Blog",
        "name": SITE["title"], "description": SITE["tagline"],
        "url": SITE["url"], "inLanguage": "zh-CN",
        "author": {"@type": "Person", "name": SITE["author"]},
        "blogPost": [{"@type": "BlogPosting", "headline": q["title"],
                      "url": f'{SITE["url"]}{base}/posts/{q["slug"]}/',
                      "datePublished": str(q.get("date", ""))} for q in posts],
    }, ensure_ascii=False)
    home_cover = posts[0].get("cover") if posts else ""
    (OUT / "index.html").write_text(shell(
        base, SITE["title"], SITE["tagline"], index, False,
        url=f"{base}/", image=f"{base}/{home_cover}" if home_cover else "",
        ld=f'<script type="application/ld+json">{site_ld}</script>'))

    def rfc822(d: str) -> str:
        try:
            return datetime.strptime(str(d), "%Y-%m-%d").strftime("%a, %d %b %Y 00:00:00 +0000")
        except ValueError:
            return ""
    rss = "".join(
        f"<item><title>{html.escape(p['title'])}</title>"
        f"<link>{SITE['url']}{base}/posts/{p['slug']}/</link>"
        f"<guid isPermaLink=\"true\">{SITE['url']}{base}/posts/{p['slug']}/</guid>"
        f"<pubDate>{rfc822(p.get('date',''))}</pubDate>"
        + "".join(f"<category>{html.escape(t)}</category>" for t in p.get("tags", []))
        + f"<description>{html.escape(p.get('summary',''))}</description></item>"
        for p in posts)
    (OUT / "feed.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>'
        f"<title>{SITE['title']}</title><link>{SITE['url']}{base}/</link>"
        f'<atom:link href="{SITE["url"]}{base}/feed.xml" rel="self" type="application/rss+xml"/>'
        f"<language>zh-CN</language>"
        f"<description>{SITE['tagline']}</description>{rss}</channel></rss>")

    # sitemap / robots / favicon
    urls = [f"{base}/"] + [f"{base}/posts/{p['slug']}/" for p in posts]
    lastmod = max((str(p.get("date", "")) for p in posts), default="")
    (OUT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(f"<url><loc>{SITE['url']}{u}</loc>"
                  + (f"<lastmod>{lastmod}</lastmod>" if lastmod else "")
                  + f"<changefreq>{'weekly' if u.endswith('/') and u == urls[0] else 'monthly'}</changefreq>"
                  + f"<priority>{'1.0' if u == urls[0] else '0.8'}</priority></url>" for u in urls)
        + "</urlset>")
    (OUT / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\n\nSitemap: {SITE['url']}{base}/sitemap.xml\n")
    (OUT / "favicon.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
        '<rect width="32" height="32" rx="7" fill="#0E7C63"/>'
        '<rect x="7" y="9" width="7" height="7" rx="2" fill="#FAF8F3" opacity=".45"/>'
        '<rect x="18" y="9" width="7" height="7" rx="2" fill="#FFB4A2"/>'
        '<rect x="7" y="19" width="7" height="7" rx="2" fill="#FAF8F3" opacity=".45"/>'
        '<rect x="18" y="19" width="7" height="7" rx="2" fill="#FAF8F3" opacity=".45"/></svg>')

    print(f"✓ {len(posts)} 篇 → {OUT.relative_to(ROOT)}  (base={base or '/'})")
    for p in posts:
        print(f"    /posts/{p['slug']}/  {p['title']}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="", help="站点子路径，GitHub 项目站用 /blog")
    build(ap.parse_args().base)
