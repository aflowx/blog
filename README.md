# 推理工程笔记

静态博客源码，发布到 <https://aflowx.github.io/blog>

## 写一篇新文章

在 `posts/` 下新建 `.md`，开头写 frontmatter：

```markdown
---
title: "文章标题"
date: 2026-10-01
slug: my-post                      # 网址 /posts/my-post/
cover: figures/my-cover.svg        # 首页卡片封面，省略则取正文第一张图
summary: "列表页与 RSS 的一句话摘要。"
tags: [标签A, 标签B]
---

## 第一节

正文……
```

配图放 `posts/figures/`，正文里这样引用（紧跟的 `*图 N：...*` 会成为图注）：

```markdown
![图 1](figures/my-figure.svg)

*图 1：这张图让眼睛算出了什么。*
```

提交推到 `main`，Actions 自动构建发布，约一分钟生效。

## 本地预览

```bash
python3 build.py
cd _site && python3 -m http.server 8000
```

线上是 `/blog` 子路径，CI 自动带上；本地用根路径。

## 设计

**Token Grid**：视觉母题取自首篇的核心配图——一次 JSON 回复被切成 17 个 token
方块，只有 3 块是答案。这组「离散方块」成了全站的结构语言：标签、目录编号、
代码语言标签、行内代码都是圆角小块，首页与文章页顶部各有一条 token 条，
载入时三个「答案块」依次点亮。

- 暖纸 `#FAF8F3` / 蓝石板 `#1A2230` / 深松绿 `#0E7C63`，方块用配图的薄荷与蜜桃
- 中文标题用系统黑体重字重收紧字距；个性交给 IBM Plex Mono，用在日期、序号、
  标签、代码上
- 深浅两套配色，跟随系统
- 文章页：宽屏下左正文右目录（滚动高亮 + 顶部进度条），配图略微出血

改站名、副标题、作者在 `build.py` 顶部的 `SITE`；样式在同文件的 `STYLE`。
