const api = require("../../utils/api");

Page({
  data: {
    step: "login",      // login 未登录 | bind 待绑手机号 | done 已登录
    name: "",
    phone: "",
    logining: false,
    binding: false,
    user: null
  },
  onLoad() {
    this.refresh();
  },
  onShow() {
    this.refresh();
  },
  refresh() {
    const user = wx.getStorageSync("user_info");
    if (user && wx.getStorageSync("user_token")) {
      this.setData({ step: "done", user });
    } else {
      this.setData({ step: "login", user: null });
    }
  },
  bindInput(e) {
    const key = e.currentTarget.dataset.key;
    this.setData({ [key]: String(e.detail.value == null ? "" : e.detail.value) });
  },
  // 微信一键登录：wx.login 拿 code -> 后端换 openid 自动注册
  wxLogin() {
    if (this.data.logining) return;
    this.setData({ logining: true });
    let devId = wx.getStorageSync("dev_id");
    if (!devId) {
      devId = Math.random().toString(36).slice(2, 12);
      wx.setStorageSync("dev_id", devId);
    }
    api.login(devId).then(r => {
      wx.setStorageSync("user_token", r.token);
      wx.setStorageSync("user_info", r.user);
      getApp().globalData.user = r.user;
      if (r.user && r.user.phone) {
        this.done();
      } else {
        // 已授权微信身份，还需绑定手机号
        this.setData({ step: "bind", user: r.user, name: r.user.name || "" });
        wx.showToast({ title: "微信授权成功", icon: "success" });
      }
    }).catch(() => {}).finally(() => this.setData({ logining: false }));
  },
  // 绑定手机号与称呼
  bindPhone() {
    if (this.data.binding) return;
    const phone = (this.data.phone || "").trim();
    const name = (this.data.name || "").trim();
    if (!name) return wx.showToast({ title: "请填写您的称呼", icon: "none" });
    if (!/^1\d{10}$/.test(phone)) return wx.showToast({ title: "手机号格式不正确", icon: "none" });
    this.setData({ binding: true });
    api.bindPhone(phone, name).then(user => {
      wx.setStorageSync("user_info", user);
      getApp().globalData.user = user;
      this.done();
    }).catch(() => {}).finally(() => this.setData({ binding: false }));
  },
  done() {
    this.refresh();
    wx.showToast({ title: "登录成功", icon: "success" });
    setTimeout(() => {
      wx.navigateBack({
        fail: () => wx.switchTab({ url: "/pages/index/index" })
      });
    }, 600);
  },
  goOrders() {
    wx.switchTab({ url: "/pages/order-list/order-list" });
  },
  logout() {
    wx.showModal({
      title: "退出登录",
      content: "退出后需重新登录才能下单",
      success: res => {
        if (!res.confirm) return;
        api.logout();
        this.setData({ step: "login", user: null, phone: "", name: "" });
      }
    });
  }
});
