(function (root) {
  function validate(groups) {
    if (!Array.isArray(groups) || groups.length === 0) throw new Error('群配置为空');
    for (const group of groups) {
      if (!group.name || !/^assets\/groups\/[\w-]+\.jpg$/.test(group.image) ||
          typeof group.expiresAt !== 'string' ||
          !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:\d{2})$/.test(group.expiresAt) ||
          !Number.isFinite(Date.parse(group.expiresAt))) {
        throw new Error('群配置无效，请检查名称、图片和带时区的到期时间');
      }
    }
    return groups;
  }
  function expired(group, now = Date.now()) {
    return now >= Date.parse(group.expiresAt);
  }
  function imageUrl(group) {
    return './' + group.image + '?v=' + encodeURIComponent(group.version || group.expiresAt);
  }
  const api = { validate, expired, imageUrl };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.GroupQR = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
