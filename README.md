<div align="center">

# 博士栈 · CSPhD.org

**CS / AI / EE / Stats 博士的成长社区**
从入学前到毕业后,陪你走过每一步

<sub>A non-profit community hub for (mostly North American) CS / AI / EE / Stats PhDs.</sub>

[**🌐 csphd.org**](https://csphd.org) · [PhD 机会板](https://csphd.org/board.html) · [注册进群](https://forms.gle/ACJUTaqc5QPfLWPg8)

![live](https://img.shields.io/badge/live-csphd.org-1f6feb)
![students](https://img.shields.io/badge/对同学-永久免费-15803d)

</div>

---

## 这是什么

博士栈(csphd.org)是一个面向 CS / AI / EE / Stats 博士的**公益社区门户**,立足北美、面向全球。它建立在一个已运营 5 年、覆盖数千位同学的微信社群之上:

- **网站**负责看得见、查得到、进得来:社区介绍、PhD 机会板、注册入口。
- **微信群**负责日常交流与第一手机会分发:求职、教职、AP、审稿、开会等系列群。

纯公益,对同学永久免费,没有收费、没有套路。发起与维护:USC 计算机系 [Yue Zhao](https://yzhao062.github.io)。

## 网站结构

| 页面 | 文件 | 内容 |
|---|---|---|
| [首页](https://csphd.org) | `index.html` | 社区介绍、群系列与截图、三步加入、注册进群 |
| [PhD 机会板](https://csphd.org/board.html) | `board.html` | 500+ 长期与短期 PhD / RA / Postdoc 机会,按学校分组,可搜索筛选 |
| [隐私与使用说明](https://csphd.org/privacy.html) | `privacy.html` | 本站做什么、收集什么信息、如何查询或删除 |

## PhD 机会板的数据从哪来

机会信息来自一份由各位导师本人维护的公开 Google 表格([tinyurl.com/2026phd](https://tinyurl.com/2026phd))。一个每日运行的 GitHub Action 把表格同步成 `data/openings.js`,所以板块不会过期:

- 导师在**源表格**里增删、更新自己的招生信息。
- 学生在 **csphd.org** 上检索、筛选、查看。

同步脚本 `tools/build_openings.py`,定时任务 `.github/workflows/sync-openings.yml`。

## 怎么加入

1. 填写[注册 Google 表单](https://forms.gle/ACJUTaqc5QPfLWPg8),留下研究方向与所在阶段。
2. 提交后获取群分类与拉群小助手微信。
3. 加拉群小助手,按方向被拉进对应微信群。

## 技术说明

- 纯静态站点,GitHub Pages 托管,无构建步骤。
- 视图时**不加载任何外部资源**(无 CDN、无 Google 字体、无第三方统计),在中国大陆可直接访问。
- 系统字体、内联样式、本地资源;机会数据每日自动同步。

## 联系

建议或合作:[contact@csphd.org](mailto:contact@csphd.org)
