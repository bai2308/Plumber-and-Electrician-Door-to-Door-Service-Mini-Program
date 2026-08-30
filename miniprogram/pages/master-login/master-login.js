const api = require("../../utils/api");

Page({
  data: { password: "", loading: false },
  bindInput(e) {
    this.setData({ password: e.detail.value });
  },
  login() {
    if (this.data.loading) return;
    if (!this.data.password) return wx.showToast({ title: "请输入密码", icon: "none" });
    this.setData({ loading: true });
    api.request("/api/master/login", {
      method: "POST",
      data: { password: this.data.password }
    }).then(res => {
      wx.setStorageSync("master_token", res.token);
      wx.redirectTo({ url: "/pages/master-orders/master-orders" });
    }).catch(() => {}).finally(() => this.setData({ loading: false }));
  }
});
