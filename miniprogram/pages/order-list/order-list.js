const api = require("../../utils/api");

Page({
  data: { orders: [], loaded: false, logged: false },
  onShow() {
    const logged = api.isLogged();
    this.setData({ logged, loaded: logged ? this.data.loaded : false });
    if (logged) this.fetch();
  },
  onPullDownRefresh() {
    if (this.data.logged) {
      this.fetch().finally(() => wx.stopPullDownRefresh());
    } else {
      wx.stopPullDownRefresh();
    }
  },
  fetch() {
    return api.request("/api/orders/my", { auth: true }).then(orders => {
      this.setData({ orders, loaded: true });
    }).catch(() => this.setData({ loaded: true }));
  },
  goLogin() {
    wx.navigateTo({ url: "/pages/login/login" });
  },
  goDetail(e) {
    wx.navigateTo({ url: "/pages/order-detail/order-detail?id=" + e.currentTarget.dataset.id });
  },
  goCreate() {
    wx.navigateTo({ url: "/pages/order-create/order-create" });
  }
});
