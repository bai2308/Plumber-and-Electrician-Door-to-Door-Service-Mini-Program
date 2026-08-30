// 全局配置：改成你后端电脑的局域网IP，手机预览时也要用局域网IP
const BASE_URL = "http://10.1.44.193:8000";

// 登录状态快捷判断
function isLogged() {
  return !!(wx.getStorageSync("user_token") && wx.getStorageSync("user_info"));
}

// 封装请求：master=true 带师傅token；auth=true 带客户登录token
function request(path, { method = "GET", data = {}, master = false, auth = false } = {}) {
  return new Promise((resolve, reject) => {
    const header = { "Content-Type": "application/json" };
    let kind = null; // 'master' | 'auth'，用于区分401跳转目标
    if (master && wx.getStorageSync("master_token")) {
      header["Authorization"] = "Bearer " + wx.getStorageSync("master_token");
      kind = "master";
    } else if (auth && wx.getStorageSync("user_token")) {
      header["Authorization"] = "Bearer " + wx.getStorageSync("user_token");
      kind = "auth";
    }
    wx.request({
      url: BASE_URL + path,
      method,
      data,
      header,
      success(res) {
        if (res.statusCode === 401) {
          // 只有「带了 token 仍被拒」才是会话过期；否则直接透出错误信息
          if (kind === "master") {
            wx.removeStorageSync("master_token");
            wx.showModal({
              title: "提示", content: "登录已过期，请重新登录",
              showCancel: false,
              success: () => wx.redirectTo({ url: "/pages/master-login/master-login" })
            });
          } else if (kind === "auth") {
            wx.removeStorageSync("user_token");
            wx.removeStorageSync("user_info");
            wx.showModal({
              title: "提示", content: "登录已过期，请重新登录",
              showCancel: false,
              success: () => wx.navigateTo({ url: "/pages/login/login" })
            });
          }
          return reject(new Error((res.data && res.data.detail) || "未授权"));
        }
        if (res.statusCode >= 400) {
          const msg = (res.data && res.data.detail) || "请求失败";
          wx.showToast({ title: String(msg).slice(0, 20), icon: "none" });
          return reject(new Error(msg));
        }
        resolve(res.data);
      },
      fail(err) {
        wx.showToast({ title: "网络连接失败", icon: "none" });
        reject(err);
      }
    });
  });
}

// 微信一键登录：code 交给后端换 openid，返回 {token, user}
function login(devId) {
  return new Promise((resolve, reject) => {
    wx.login({
      success(r) {
        request("/api/auth/login", { method: "POST", data: { code: r.code, dev_id: devId || "" } })
          .then(resolve).catch(reject);
      },
      fail(err) { reject(new Error("微信登录失败：" + (err.errMsg || ""))); }
    });
  });
}

// 绑定手机号与称呼
function bindPhone(phone, name) {
  return request("/api/auth/bind-phone", { method: "POST", data: { phone, name }, auth: true });
}

// 上传图片，返回服务器URL（带30秒超时+重试）
function uploadImage(filePath) {
  return new Promise((resolve, reject) => {
    const attempt = (n) => wx.uploadFile({
      url: BASE_URL + "/api/upload",
      filePath,
      name: "file",
      timeout: 30000,
      success(res) {
        try {
          const data = JSON.parse(res.data);
          if (res.statusCode >= 400) return reject(new Error(data.detail || "上传失败"));
          resolve(data.url);
        } catch (e) { reject(new Error("服务器返回格式错误")); }
      },
      fail(err) {
        if (n > 0) return setTimeout(() => attempt(n - 1), 1000);
        reject(new Error(err.errMsg || "网络连接失败"));
      }
    });
    attempt(1);
  });
}

function callPhone(phone) {
  wx.makePhoneCall({ phoneNumber: phone });
}

// 退出客户登录
function logout() {
  wx.removeStorageSync("user_token");
  wx.removeStorageSync("user_info");
  const app = getApp();
  if (app && app.globalData) app.globalData.user = null;
}

module.exports = { BASE_URL, request, uploadImage, callPhone, isLogged, login, bindPhone, logout };
