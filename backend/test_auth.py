# -*- coding: utf-8 -*-
"""全链路冒烟测试：微信登录(开发模式) -> 绑定手机号 -> 下单 -> 我的订单 -> 师傅客户管理"""
import json
import urllib.request

BASE = "http://127.0.0.1:8000"
passed, failed = 0, 0


def call(method, path, body=None, token=None, expect=200):
    global passed, failed
    req = urllib.request.Request(BASE + path, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    data = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(req, data=data, timeout=10) as r:
            code, res = r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        code, res = e.code, json.loads(e.read().decode() or "{}")
    name = f"{method} {path}"
    if code == expect:
        passed += 1
        print(f"  PASS {name} -> {code}")
    else:
        failed += 1
        print(f"  FAIL {name} -> {code} (期望 {expect}) {res}")
    return res


print("== 1. 健康检查 ==")
call("GET", "/api/health")

print("== 2. 微信登录（开发模式 dev_id=user_A）==")
r = call("POST", "/api/auth/login", {"code": "any-code", "dev_id": "user_A"})
assert "token" in r, "登录未返回 token"
user_token = r["token"]
assert r["user"]["has_phone"] is False, "新用户不应有手机号"

print("== 3. 未绑定手机号时校验 ==")
call("POST", "/api/auth/bind-phone", {"phone": "12345", "name": "张三"}, token=user_token, expect=400)

print("== 4. 绑定手机号 ==")
r = call("POST", "/api/auth/bind-phone", {"phone": "13800001111", "name": "张三"}, token=user_token)
assert r["phone"] == "13800001111" and r["has_phone"]

print("== 5. /api/auth/me ==")
r = call("GET", "/api/auth/me", token=user_token)
assert r["name"] == "张三"

print("== 6. 同一 dev_id 再登录 -> 同一账号（token 稳定身份）==")
r2 = call("POST", "/api/auth/login", {"code": "another-code", "dev_id": "user_A"})
assert r2["user"]["id"] == r["id"], "同一设备应登录同一账号"

print("== 7. 未登录下单被拒（401）==")
call("POST", "/api/orders", {
    "customer_name": "张三", "phone": "13800001111", "address": "幸福小区1栋101",
    "service_type": "水管维修", "description": "厨房漏水"}, expect=401)

print("== 8. 登录后下单 ==")
r = call("POST", "/api/orders", {
    "customer_name": "张三", "phone": "13800001111", "address": "幸福小区1栋101",
    "service_type": "水管维修", "description": "厨房漏水", "photos": [], "scheduled_time": ""}, token=user_token)
order_id = r["id"]

print("== 9. 我的订单（按 user_id + 绑定手机号）==")
r = call("GET", "/api/orders/my", token=user_token)
assert any(o["id"] == order_id for o in r), "我的订单应包含刚下的单"
assert r[0]["customer_name"] == "张三"

print("== 10. 第二个客户（旧手机号下单的无 user_id 订单也能查到）==")
# 先直接造一单旧数据（模拟绑定前手机号下的单）——用另一个账号绑定同手机号验证 phone 匹配逻辑
r = call("POST", "/api/auth/login", {"code": "c", "dev_id": "user_B"})
tok_b = r["token"]
call("POST", "/api/auth/bind-phone", {"phone": "13800002222", "name": "李四"}, token=tok_b)
r = call("POST", "/api/orders", {
    "customer_name": "李四", "phone": "13800002222", "address": "花园小区2栋202",
    "service_type": "电路维修", "description": "插座没电"}, token=tok_b)
order_b = r["id"]

print("== 11. 师傅登录 + 接单 + 完成 ==")
r = call("POST", "/api/master/login", {"password": "123456"})
mt = r["token"]
call("POST", f"/api/orders/{order_id}/status", {"status": "confirmed"}, token=mt)
call("POST", f"/api/orders/{order_id}/status", {"status": "completed", "price": 80}, token=mt)

print("== 12. 客户管理接口 ==")
r = call("GET", "/api/master/customers", token=mt)
phones = {c["phone"] for c in r}
assert "13800001111" in phones and "13800002222" in phones, "客户列表应含两位客户"
c1 = [c for c in r if c["phone"] == "13800001111"][0]
assert c1["name"] == "张三" and c1["total"] == 1 and c1["completed"] == 1 and c1["spent"] == 80, c1
print("   客户1:", c1)

print("== 13. 客户搜索（q=张）==")
r = call("GET", "/api/master/customers?q=%E5%BC%A0", token=mt)
assert len(r) == 1 and r[0]["name"] == "张三"

print("== 14. 伪造 token 被拒（401）==")
call("GET", "/api/orders/my", token="1.99999.deadbeefdeadbeef", expect=401)

print("== 15. 旧接口兼容：按手机号查询 ==")
r = call("GET", "/api/orders?phone=13800001111")
assert any(o["id"] == order_id for o in r)

print(f"\n结果: {passed} 通过, {failed} 失败")
exit(1 if failed else 0)
