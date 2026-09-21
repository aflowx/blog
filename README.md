# 推理工程笔记

静态博客源码，构建后发布到 GitHub Pages：<https://aflowx.github.io/blog>

## 写一篇新文章

1. 在 `posts/` 下新建一个 `.md`，开头写 frontmatter：

```markdown
---
title: "文章标题"
date: 2026-10-01
slug: my-post          # 决定网址 /posts/my-post/
summary: "列表页和 RSS 里显示的一句话摘要。"
tags: [标签A, 标签B]
---

## 第一节

正文……
```

2. 配图放 `posts/figures/`，正文里这样引用（紧跟其后的 `*图 N：...*` 会成为图注）：

```markdown
![图 1](figures/my-figure.svg)

*图 1：这张图让眼睛算出了什么。*
```

3. 提交并推到 `main`。GitHub Actions 会自动构建发布，约一分钟后生效。

## 本地预览

```bash
python3 build.py          # 产物在 _site/
cd _site && python3 -m http.server 8000
```

打开 <http://localhost:8000>。注意本地用根路径，线上是 `/blog` 子路径，CI 里自动带上。

## 支持的 Markdown

标题（`##` / `###`）、段落、**粗体**、`行内代码`、链接、围栏代码块（带语言标签）、表格、引用、分隔线、图片与图注。

斜体整行（`*……*`）会渲染成小字注释，用于来源说明那类内容。

## 站点信息

站名、副标题、作者、域名在 `build.py` 顶部的 `SITE` 字典里改。样式在同文件的 `STYLE` 字符串里，支持浅色/深色两套配色。
