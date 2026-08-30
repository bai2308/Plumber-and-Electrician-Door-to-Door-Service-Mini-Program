const app = getApp();

Page({
  data: { services: [] },
  onShow() {
    // 优先渲染缓存，瞬时显示
    const list = app.globalData.services || [];
    if (list.length) this.setData({ services: list });
    // 后台拉新（5 分钟内已拉过则跳过）
    const lastFetch = wx.getStorageSync("services_fetched_at") || 0;
    if (Date.now() - lastFetch > 5 * 60 * 1000) {
      const api = require("../../utils/api");
      api.request("/api/services").then(list => {
        this.setData({ services: list });
        app.globalData.services = list;
        wx.setStorageSync("services_cache", list);
        wx.setStorageSync("services_fetched_at", Date.now());
      }).catch(() => {});
    }
  },
  goOrder(e) {
    const name = e.currentTarget.dataset.name || "";
    wx.navigateTo({ url: "/pages/order-create/order-create?type=" + encodeURIComponent(name) });
  },
  goServices() {
    wx.switchTab({ url: "/pages/services/services" });
  },
  goMaster() {
    if (wx.getStorageSync("master_token")) {
      wx.navigateTo({ url: "/pages/master-orders/master-orders" });
    } else {
      wx.navigateTo({ url: "/pages/master-login/master-login" });
    }
  }
});