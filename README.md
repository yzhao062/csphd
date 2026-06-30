<div align="center">

<a href="https://csphd.org"><img src="./assets/hero.png" alt="博士栈 · CSPhD.org" width="760"></a>

# 博士栈 · CSPhD.org

**CS / AI / EE / Stats 博士的成长社区 · 从入学前到毕业后，陪你走过每一步**

<sub>A non-profit, zero-backend community hub for (mostly North-American) CS / AI / EE / Stats PhDs. Static, reachable from mainland China, and auto-synced.</sub>

[![website](https://img.shields.io/website?url=https%3A%2F%2Fcsphd.org&label=csphd.org&up_message=online&up_color=1f6feb)](https://csphd.org)
[![sync](https://github.com/yzhao062/csphd/actions/workflows/sync-openings.yml/badge.svg)](https://github.com/yzhao062/csphd/actions/workflows/sync-openings.yml)
[![openings](https://img.shields.io/badge/PhD%2FRA%20机会-540%2B-1f6feb)](https://csphd.org/board.html)
[![china-safe](https://img.shields.io/badge/零外部依赖-中国大陆可直连-15803d)](#-技术亮点)
[![free](https://img.shields.io/badge/对同学-永久免费-15803d)](https://csphd.org)

[**🌐 csphd.org**](https://csphd.org) · [PhD 机会板](https://csphd.org/board.html) · [申请读博](https://csphd.org/grad.html) · [实习全职](https://csphd.org/jobs.html) · [教职资源](https://csphd.org/faculty.html) · [注册进群](https://forms.gle/ACJUTaqc5QPfLWPg8)

</div>

---

## 这是什么

**博士栈（csphd.org）** 是一个面向 CS / AI / EE / Stats 博士的**公益社区门户**，立足北美、面向全球、以中文交流。它建立在一个已运营 5 年、覆盖数千位同学的微信社群之上：

- **网站**负责看得见、查得到、进得来：社区介绍、机会板、各阶段资源、注册入口。
- **微信群**负责日常交流与第一手机会分发：求职、教职、AP、审稿、开会等系列群。

纯公益，对同学永久免费，没有收费、没有套路。发起与维护：USC 计算机系 [Yue Zhao](https://yzhao062.github.io)。

## ✨ 提供什么

| | 页面 | 一句话 |
|:--:|---|---|
| 🎯 | [**PhD 机会板**](https://csphd.org/board.html) | 540+ 长期与短期 PhD / RA / Postdoc 机会，按学校分组，可搜索筛选，**每日自动同步** |
| 🎓 | [**申请读博**](https://csphd.org/grad.html) | 选校找导师、申请材料、读博工具、会议审稿；专门标出国际生（F-1/J-1）常被卡的 GRE、fee waiver 与 fellowship 资格 |
| 💼 | [**实习全职**](https://csphd.org/jobs.html) | 北美工业界实习与全职：职位追踪、求职时间线、面试准备、薪资基准、国际生身份基础 |
| 🧑‍🏫 | [**教职资源**](https://csphd.org/faculty.html) | 教职申请全流程、材料清单、推荐信、面试题库、CRA 薪资数据 |
| 👥 | [**社群**](https://csphd.org/#community) | 求职、教职、AP、审稿、开会等系列微信群，按方向分流 |

## 🔄 PhD 机会板：永不过期的数据

机会信息来自一份由各位导师本人维护的公开 Google 表格（[tinyurl.com/2026phd](https://tinyurl.com/2026phd)）。一个每日运行的 GitHub Action 把表格同步成 `data/openings.js`：导师在源表格里更新，学生在 csphd.org 上检索，板块不会过期。

```text
  导师 · Google 表格  (tinyurl.com/2026phd)
       │
       │   每日 GitHub Action ·  build_openings.py（纯标准库）
       ▼
  data/openings.js  ──►  csphd.org/board.html  ◄──  学生：搜索 · 筛选
```

同步脚本 `tools/build_openings.py`（纯标准库），定时任务 `.github/workflows/sync-openings.yml`（每日 cron，仅在数据有变化时提交）。

## 🛠 技术亮点

几个有意识的设计取舍，也是这个站点为什么干净、快、可信：

- **纯静态，零后端**：没有构建步骤、没有服务器、没有数据库，整站就是几个 HTML 文件加一份 JS 数据。
- **零外部运行时依赖，中国大陆可直连**：视图时不加载任何 CDN、Google 字体或第三方统计；系统字体 + 内联样式 + 本地资源。这是面向中国大陆用户的硬约束，顺带让站点更快、更私密。
- **数据自动保鲜**：GitHub Actions 每天把一份协作 Google 表格抓成静态数据，把「表格会过期」变成「板块永远最新」，全程无人值守。
- **GitHub Pages + 自定义域名 + 自动 HTTPS**：一个仓库托管整站，`csphd.org` 自动签发证书。
- **可访问 + 移动友好**：语义化标签、aria 标注、响应式布局、全角中文标点。

一句话：它干净、轻、私密，在防火墙后也能直连，不追踪访客，数据每天自己更新。

## 🗂 仓库结构

```text
csphd/
├── index.html          首页：社区介绍、群系列、三步加入、注册
├── board.html          PhD / RA / Postdoc 机会板（搜索 + 筛选）
├── grad.html           申请读博：选校、材料、读博工具、会议审稿
├── jobs.html           实习全职：工业界求职资源
├── faculty.html        教职资源：CS 教职求职合集
├── privacy.html        隐私与使用说明
├── data/openings.js    机会数据（GitHub Action 每日生成，含 firstSeen/lastChanged 新鲜度字段）
├── tools/              build_openings.py（表格 → JSON / JS）
├── .github/workflows/  sync-openings.yml（每日同步）
├── screenshots/        微信群截图
└── CNAME               csphd.org
```

## 🙋 怎么加入

1. 填写[注册 Google 表单](https://forms.gle/ACJUTaqc5QPfLWPg8)，留下研究方向与所在阶段。
2. 提交后获取群分类与拉群小助手微信。
3. 加拉群小助手，按方向被拉进对应微信群。

> 表单与部分链接走 Google，中国大陆需自备网络环境。

## 🔍 透明

整站源码与机会数据都公开在本仓库，你可以核对它确实不加载任何第三方资源、不追踪访客。本仓库公开仅供透明与查阅。

## 📫 联系

建议或合作：[contact@csphd.org](mailto:contact@csphd.org) · 发起人 [Yue Zhao](https://yzhao062.github.io)（USC 计算机系）

<div align="center"><sub>纯公益 · 已运营 5 年 · 帮助过数千位同学 · 对同学永久免费</sub></div>

---

<div align="center"><sub>© 2026 Yue Zhao · 本仓库公开仅供透明与查阅，保留所有权利；未经许可请勿复制或二次分发。<br>Published for transparency only. All rights reserved; not licensed for reuse.</sub></div>
