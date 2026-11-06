---
name: weekly-group-qr
description: 每周更新 csphd.org 的微信群二维码图片和有效期，检查过期通知并验证上线结果。用于用户提供新群码、要求换码或测试二维码过期 CI 时。
---

# Weekly Group QR

在 csphd 项目中操作。固定入口为 `https://csphd.org/join.html`，Google 表单确认消息已指向该地址，换码时无需修改表单。

## Refresh

1. 读取 `data/groups.json` 和工作区状态。查看用户提供的原图，按群名区分求职群与审稿群，确认图上到期日期及群编号。缺图或日期看不清时问用户，不猜测，也不生成二维码。
2. 用原图覆盖 `assets/groups/jobs.jpg` 或 `assets/groups/review.jpg`。只更新本次收到的群，保留另一群。若源文件不是 JPEG，做无裁剪的格式转换并核对二维码清晰度；不要只改扩展名。
3. 修改对应配置的 `name` 和 `expiresAt`。使用带时区的 ISO 时间；图上写“某月某日前有效”时，按北京时间该日零点保守截止，例如 `2026-11-12T00:00:00+08:00`。年份根据当前日期和图片确认，跨年有歧义时询问。不要机械地从今天加七天。若到期时间未变却换了图，更新 `version` 为新的时间戳，避免旧图缓存。
4. 运行 `node --test tests/group-qr.test.js`、`node tools/check_group_qr.js` 和 `git diff --check`。若未更新的另一群仍过期，明确报告，不能修改其日期来消除失败。
5. 通过 HTTP 预览 `join.html`，检查新图、群名、到期日和原图链接。不要使用 `file://`，它无法读取 JSON 配置。有效期内不显示备用微信；过期后才显示 `yzhao062`，要求备注「学校/单位 + 姓名」。
6. 汇报改动和有效期。提交、push 需要本次任务的明确授权，并先展示实际命令。有授权时上线后验证正式页面和两张图片，再确认 `check-group-qr` 与 Pages 部署通过。

## Notification Test

CI 每天检查一次。GitHub Actions 邮件依赖用户通知设置，测试失败不等于已经收到邮件。用户需要在 GitHub Settings → Notifications → System → Actions 中启用 Email，可选 Only notify for failed workflows。

本地执行 `SIMULATE_EXPIRED=true node tools/check_group_qr.js`，预期退出码为 1，配置和网站保持不变。测试选项上线后，可在 Actions → check-group-qr → Run workflow 勾选 `simulate_expired`。只有用户要求实际测试通知时才触发该失败运行，等待结果并请用户确认收件；不要声称已验证邮箱送达。正常检查不勾选该选项。

此技能供每周换码时调用，不自动创建提醒或获取新二维码。
