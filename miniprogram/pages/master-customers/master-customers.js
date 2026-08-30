const api = require("../../utils/api");

Page({
  data: { q: "", customers: [], expanded: -1, loading: false },
  onShow() {
    this.fetch();
  },
  bindInput(e) {
    this.setData({ q: e.detail.value });
  },
  fetch() {
    if (this.data.loading) return;
    this.setData({ loading: true, expanded: -1 });
    const q = (this.data.q || "").trim();
    const path = "/api/master/customers" + (q ? "?q=" + encodeURIComponent(q) : "");
    api.request(path, { master: true }).then(customers => {
      customers.forEach(c => { c.orders = null; });
      this.setData({ customers });
    }).catch(() => {}).finally(() => this.setData({ loading: false }));
  },
  // 展开/收起某客户的历史订单
  toggle(e) {
    const index = e.currentTarget.dataset.index;
    if (this.data.expanded === index) {
      return this.setData({ expanded: -1 });
    }
    this.setData({ expanded: index });
    const c = this.data.customers[index];
    if (c.orders) return; // 已加载过
    api.request("/api/orders?phone=" + encodeURIComponent(c.phone)).then(orders => {
      this.setData({ ["customers[" + index + "].orders"]: orders });
    }).catch(() => this.setData({ ["customers[" + index + "].orders"]: [] }));
  },
  call(e) {
    api.callPhone(e.currentTarget.dataset.phone);
  },
  goBack() {
    wx.navigateBack({ fail: () => wx.redirectTo({ url: "/pages/master-orders/master-orders" }) });
  }
});
