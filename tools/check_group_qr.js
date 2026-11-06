const fs = require('node:fs');
const path = require('node:path');
const { validate, expired } = require('../js/group-qr.js');
const root = path.resolve(__dirname, '..');

try {
  const groups = validate(JSON.parse(fs.readFileSync(path.join(root, 'data/groups.json'), 'utf8')));
  const now = Date.now();
  for (const group of groups) {
    if (!fs.existsSync(path.join(root, group.image))) {
      console.error(`::error::${group.name}: 图片缺失 ${group.image}`);
      process.exitCode = 1;
    }
    if (expired(group, now)) {
      console.error(`::error::${group.name}: 二维码已于 ${group.expiresAt} 到期。请覆盖 ${group.image} 并更新 data/groups.json 中的 expiresAt。`);
      process.exitCode = 1;
    } else {
      console.log(`${group.name}: 有效至 ${group.expiresAt}`);
    }
  }
} catch (error) {
  console.error(`::error::${error.message}`);
  process.exitCode = 1;
}
