(async function () {
  const container = document.getElementById('groups');
  const status = document.getElementById('status');
  function element(tag, text, className) {
    const node = document.createElement(tag);
    if (text) node.textContent = text;
    if (className) node.className = className;
    return node;
  }
  try {
    const response = await fetch('./data/groups.json', { cache: 'no-store' });
    if (!response.ok) throw new Error('配置加载失败');
    const groups = GroupQR.validate(await response.json());
    let previousState = '';
    function render() {
      const now = Date.now();
      const state = groups.map(group => GroupQR.expired(group, now)).join(',');
      if (state === previousState) return;
      previousState = state;
      container.replaceChildren();
      for (const group of groups) {
        const card = element('article');
        card.append(element('h2', group.name));
        if (GroupQR.expired(group, now)) {
          const fallback = element('div', '', 'expired');
          fallback.append(element('p', '本群二维码已过期，请添加微信联系入群：'));
          fallback.append(element('p', 'yzhao062', 'wechat'));
          fallback.append(element('p', '添加好友时必须备注「学校/单位 + 姓名」，请严格按此格式填写。'));
          card.append(fallback);
        } else {
          const expires = new Intl.DateTimeFormat('zh-CN', {
            timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit',
            hour: '2-digit', minute: '2-digit', hourCycle: 'h23'
          }).format(new Date(group.expiresAt));
          card.append(element('p', `有效至北京时间 ${expires}（到时失效）`, 'note'));
          const link = element('a');
          link.href = GroupQR.imageUrl(group);
          const img = element('img');
          img.src = link.href;
          img.alt = `${group.name}微信入群二维码`;
          img.addEventListener('error', () => {
            link.replaceWith(element('p', '二维码图片加载失败，请刷新页面重试。'));
          });
          link.append(img);
          card.append(link);
          const download = element('a', '保存二维码', 'download');
          download.href = GroupQR.imageUrl(group);
          download.download = group.image.split('/').pop();
          card.append(download);
        }
        container.append(card);
      }
    }
    render();
    status.textContent = '';
    setInterval(render, 1000);
    document.addEventListener('visibilitychange', render);
  } catch (error) {
    status.textContent = '入群信息加载失败，请刷新页面重试，或通过页面底部联系邮箱反馈。';
  }
})();
