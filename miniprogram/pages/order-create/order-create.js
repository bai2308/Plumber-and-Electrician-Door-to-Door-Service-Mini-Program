const app = getApp();
const api = require("../../utils/api");

Page({
  data: {
    services: [],
    serviceIndex: -1,
    form: { customer_name: "", phone: "", address: "", description: "", scheduled_time: "" },
    photos: [],        // 已上传的URL
    localPhotos: [],   // 本地临时路径
    uploading: false,
    submitting: false,
    today: ""
  },
  onLoad(options) {
    // 登录拦截：未登录先去登录
    if (!wx.getStorageSync("user_token")) {
      wx.showModal({
        title: "提示", content: "请先登录后再下单", showCancel: false,
        success: () => wx.redirectTo({ url: "/pages/login/login" })
      });
      return;
    }

    const today = new Date().toISOString().slice(0, 10);
    this.setData({ today });

    // 等服务列表就绪
    const initWith = list => {
      let idx = -1;
      if (options.type) idx = list.findIndex(s => s.name === decodeURIComponent(options.type));
      this.setData({ services: list, serviceIndex: idx });
    };
    if (app.globalData.services.length) {
      initWith(app.globalData.services);
    } else {
      api.request("/api/services").then(initWith);
    }

    // 回填联系方式：登录绑定信息优先，其次上次下单记录；全部强制转字符串
    const user = wx.getStorageSync("user_info") || {};
    const last = wx.getStorageSync("last_contact") || {};
    const form = {
      customer_name: String(user.name || last.customer_name || ""),
      phone:         String(user.phone || last.phone || ""),
      address:       String(last.address || ""),
      description:   "",  // 描述不回填，避免上次内容残留
      scheduled_time: ""
    };
    this.setData({ form });
  },
  bindInput(e) {
    const key = e.currentTarget.dataset.key;
    // 强制转字符串，防止 textarea 把对象塞进来导致 [object Object]
    this.setData({ ["form." + key]: String(e.detail.value == null ? "" : e.detail.value) });
  },
  bindService(e) {
    this.setData({ serviceIndex: Number(e.detail.value) });
  },
  bindTime(e) {
    this.setData({ "form.scheduled_time": String(e.detail.value || "") });
  },
  choosePhoto() {
    const left = 3 - this.data.localPhotos.length;
    if (left <= 0) return;
    wx.chooseMedia({
      count: left,
      mediaType: ["image"],
      success: res => {
        const files = res.tempFiles.map(f => f.tempFilePath);
        this.setData({ localPhotos: this.data.localPhotos.concat(files) });
      }
    });
  },
  removePhoto(e) {
    const i = e.currentTarget.dataset.index;
    const localPhotos = this.data.localPhotos.slice();
    localPhotos.splice(i, 1);
    this.setData({ localPhotos });
  },
  async submit() {
    const { form, serviceIndex, services, localPhotos, uploading, submitting } = this.data;
    if (submitting || uploading) return;
    if (!form.customer_name.trim()) return wx.showToast({ title: "请填写姓名", icon: "none" });
    if (!/^1\d{10}$/.test(form.phone.trim())) return wx.showToast({ title: "手机号格式不正确", icon: "none" });
    if (!form.address.trim()) return wx.showToast({ title: "请填写上门地址", icon: "none" });
    if (serviceIndex < 0) return wx.showToast({ title: "请选择服务项目", icon: "none" });

    this.setData({ submitting: true });
    try {
      // 逐张上传，任一张失败立即提示并终止
      const photos = [];
      for (let i = 0; i < localPhotos.length; i++) {
        this.setData({ uploading: true });
        try {
          const res = await api.uploadImage(localPhotos[i]);
          photos.push(res.url);
        } catch (err) {
          wx.showToast({ title: `第${i + 1}张照片上传失败`, icon: "none" });
          this.setData({ uploading: false, submitting: false });
          return;
        }
        this.setData({ uploading: false });
      }

      await api.request("/api/orders", {
        method: "POST",
        auth: true,
        data: {
          customer_name: form.customer_name.trim(),
          phone:         form.phone.trim(),
          address:       form.address.trim(),
          service_type:  services[serviceIndex].name,
          description:   String(form.description || "").trim(),
          scheduled_time: form.scheduled_time || "",
          photos
        }
      });
      wx.setStorageSync("last_contact", {
        customer_name: form.customer_name,
        phone: form.phone,
        address: form.address
      });
      wx.showModal({
        title: "下单成功",
        content: "师傅会尽快与您联系确认上门时间",
        showCancel: false,
        success: () => wx.switchTab({ url: "/pages/order-list/order-list" })
      });
    } catch (e) {
      // 错误提示已在 request 内处理
    } finally {
      this.setData({ submitting: false, uploading: false });
    }
  }
});