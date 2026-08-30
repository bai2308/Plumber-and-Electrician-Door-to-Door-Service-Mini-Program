const api = require("../../utils/api");

Page({
  data: { order: null, photoUrls: [] },
  onLoad(options) {
    this._id = options.id;
    this.fetch();
  },
  onShow() {
    // 从详情页返回 / 师傅改完状态切回，强制刷新一次
    if (this._id) this.fetch();
  },
  onPullDownRefresh() {
    this.fetch().finally(() => wx.stopPullDownRefresh());
  },
  fetch() {
    return api.request("/api/orders/" + this._id).then(order => {
      this.setData({
        order,
        photoUrls: (order.photos || []).map(u => u.startsWith("http") ? u : api.BASE_URL + u)
      });
    });
  },
  preview(e) {
    wx.previewImage({ current: e.currentTarget.dataset.url, urls: this.data.photoUrls });
  },
  callMaster() {
    api.callPhone("13800000000");  // 改成师傅真实号码
  }
});