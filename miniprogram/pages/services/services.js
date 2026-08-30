const app = getApp();

Page({
  data: { services: [] },
  onShow() {
    const load = list => this.setData({ services: list });
    if (app.globalData.services.length) {
      load(app.globalData.services);
    } else {
      const api = require("../../utils/api");
      api.request("/api/services").then(load).catch(() => {});
    }
  },
  goOrder(e) {
    const name = e.currentTarget.dataset.name || "";
    wx.navigateTo({ url: "/pages/order-create/order-create?type=" + encodeURIComponent(name) });
  }
});
