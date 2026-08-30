App({
  onLaunch() {
    // 1. 先用本地缓存的服务列表渲染首页（毫秒级）
    const cached = wx.getStorageSync("services_cache");
    if (cached && Array.isArray(cached) && cached.length) {
      this.globalData.services = cached;
    }
    // 2. 恢复客户登录态（token + 用户信息）
    const user = wx.getStorageSync("user_info");
    if (user && wx.getStorageSync("user_token")) {
      this.globalData.user = user;
    }
    // 3. 后台异步拉新服务列表，5分钟才允许刷新一次
    const lastFetch = wx.getStorageSync("services_fetched_at") || 0;
    if (Date.now() - lastFetch > 5 * 60 * 1000) {
      const api = require("./utils/api");
      api.request("/api/services").then(list => {
        this.globalData.services = list;
        wx.setStorageSync("services_cache", list);
        wx.setStorageSync("services_fetched_at", Date.now());
      }).catch(() => {});
    }
  },
  globalData: {
    services: [],
    user: null   // {id, nickname, name, phone, has_phone}
  }
});
