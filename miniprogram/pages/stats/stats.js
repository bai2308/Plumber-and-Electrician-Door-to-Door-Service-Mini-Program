const api = require("../../utils/api");

Page({
  data: {
    month: "",
    months: [],          // 最近12个月供选择
    stats: null,
    incomeTrend: []      // 简易条形图数据
  },
  onLoad() {
    const now = new Date();
    const months = [];
    for (let i = 0; i < 12; i++) {
      const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
      months.push(d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0"));
    }
    this.setData({ months, month: months[0] }, () => this.fetch());
  },
  bindMonth(e) {
    this.setData({ month: this.data.months[e.detail.value] }, () => this.fetch());
  },
  fetch() {
    api.request("/api/master/stats?month=" + this.data.month, { master: true }).then(stats => {
      const max = Math.max(...stats.orders.map(o => o.price || 0), 1);
      const incomeTrend = stats.orders.map(o => ({
        id: o.id,
        type: o.service_type,
        price: o.price || 0,
        pct: Math.round((o.price || 0) / max * 100)
      }));
      this.setData({ stats, incomeTrend });
    }).catch(() => {});
  }
});
