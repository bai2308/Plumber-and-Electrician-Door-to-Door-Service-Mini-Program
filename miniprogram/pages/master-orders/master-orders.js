const api = require("../../utils/api");

const TABS = [
  { key: "", text: "全部" },
  { key: "pending", text: "待接单" },
  { key: "confirmed", text: "已预约" },
  { key: "repairing", text: "维修中" },
  { key: "completed", text: "已完成" }
];

Page({
  data: { tabs: TABS, active: "", orders: [] },
  onShow() {
    this.fetch();
  },
  fetch() {
    const q = this.data.active ? "?status=" + this.data.active : "";
    api.request("/api/master/orders" + q, { master: true }).then(orders => {
      this.setData({ orders });
    }).catch(() => {});
  },
  switchTab(e) {
    this.setData({ active: e.currentTarget.dataset.key }, () => this.fetch());
  },
  callCustomer(e) {
    api.callPhone(e.currentTarget.dataset.phone);
  },
  // 状态操作入口
  act(e) {
    const { id, action } = e.currentTarget.dataset;
    if (action === "confirm") return this.update(id, { status: "confirmed" });
    if (action === "repairing") return this.update(id, { status: "repairing" });
    if (action === "cancel") {
      wx.showModal({
        title: "取消订单",
        content: "确定取消该订单吗？",
        success: res => {
          if (res.confirm) this.update(id, { status: "cancelled" });
        }
      });
    }
    if (action === "complete") {
      wx.showModal({
        title: "完成维修",
        editable: true,
        placeholderText: "请输入实际收费金额（元）",
        success: res => {
          if (!res.confirm) return;
          const price = parseFloat(res.content);
          if (isNaN(price) || price < 0) {
            return wx.showToast({ title: "金额不合法", icon: "none" });
          }
          this.update(id, { status: "completed", price });
        }
      });
    }
  },
  update(id, payload) {
    api.request(`/api/orders/${id}/status`, {
      method: "POST",
      data: payload,
      master: true
    }).then(() => {
      wx.showToast({ title: "已更新" });
      this.fetch();
    }).catch(() => {});
  },
  // 删除订单（硬删除，不可恢复）
  delOrder(e) {
    const { id } = e.currentTarget.dataset;
    wx.showModal({
      title: "删除订单",
      content: `删除后订单记录不可恢复，确定删除 #${id} 吗？`,
      confirmColor: "#e64340",
      success: res => {
        if (!res.confirm) return;
        api.request(`/api/orders/${id}`, { method: "DELETE", master: true }).then(() => {
          wx.showToast({ title: "已删除" });
          this.fetch();
        }).catch(() => {});
      }
    });
  },
  goStats() {
    wx.navigateTo({ url: "/pages/stats/stats" });
  },
  goCustomers() {
    wx.navigateTo({ url: "/pages/master-customers/master-customers" });
  },
  logout() {
    wx.removeStorageSync("master_token");
    wx.redirectTo({ url: "/pages/master-login/master-login" });
  }
});
