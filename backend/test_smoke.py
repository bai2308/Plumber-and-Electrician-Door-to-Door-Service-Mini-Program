# -*- coding: utf-8 -*-
"""接口冒烟测试"""
import json
import urllib.request

BASE = "http://127.0.0.1:8000"


def req(path, method="GET", data=None, token=None):
    r = urllib.request.Request(BASE + path, method=method)
    r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("Authorization", "Bearer " + token)
    body = json.dumps(data).encode() if data is not None else None
    try:
        with urllib.request.urlopen(r, body) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


ok = 0
fail = 0


def check(name, cond, extra=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"PASS  {name}")
    else:
        fail += 1
        print(f"FAIL  {name}  {extra}")


# 1. 服务列表
s, d = req("/api/services")
check("服务列表", s == 200 and len(d) == 8, str(d)[:100])

# 2. 客户下单
s, d = req("/api/orders", "POST", {
    "customer_name": "张三", "phone": "13800001111",
    "address": "幸福小区3栋502", "service_type": "水管维修",
    "description": "厨房下水管漏水", "photos": [], "scheduled_time": "2026-09-01"
})
check("客户下单", s == 200 and d.get("id"), str(d)[:100])
oid = d["id"]

# 3. 手机号查询
s, d = req("/api/orders?phone=13800001111")
check("手机号查单", s == 200 and len(d) == 1 and d[0]["status"] == "pending", str(d)[:100])

# 4. 订单详情
s, d = req(f"/api/orders/{oid}")
check("订单详情", s == 200 and d["address"] == "幸福小区3栋502", str(d)[:100])

# 5. 未登录访问师傅接口应401
s, d = req("/api/master/orders")
check("未登录拦截", s == 401, str(s))

# 6. 错误密码
s, d = req("/api/master/login", "POST", {"password": "wrong"})
check("错误密码拒绝", s == 401, str(s))

# 7. 正确登录
s, d = req("/api/master/login", "POST", {"password": "123456"})
check("师傅登录", s == 200 and d.get("token"), str(d)[:100])
token = d["token"]

# 8. 师傅订单列表
s, d = req("/api/master/orders", token=token)
check("师傅订单列表", s == 200 and len(d) == 1, str(d)[:100])

# 9. 状态筛选
s, d = req("/api/master/orders?status=confirmed", token=token)
check("状态筛选(应为空)", s == 200 and len(d) == 0, str(d)[:100])

# 10. 非法状态
s, d = req(f"/api/orders/{oid}/status", "POST", {"status": "hack"}, token=token)
check("非法状态拒绝", s == 400, str(s))

# 11. 状态流转 confirmed
s, d = req(f"/api/orders/{oid}/status", "POST", {"status": "confirmed"}, token=token)
check("接单", s == 200 and d["status"] == "confirmed", str(d)[:100])

# 12. repairing
s, d = req(f"/api/orders/{oid}/status", "POST", {"status": "repairing"}, token=token)
check("开始维修", s == 200, str(d)[:100])

# 13. completed + 收费
s, d = req(f"/api/orders/{oid}/status", "POST", {"status": "completed", "price": 150, "note": "更换下水管"}, token=token)
check("完成收费", s == 200, str(d)[:100])

# 14. 统计
s, d = req("/api/master/stats", token=token)
check("收入统计", s == 200 and d["completed_count"] == 1 and d["total_income"] == 150, str(d)[:200])

# 15. 下第二单测试取消流程
s, d = req("/api/orders", "POST", {
    "customer_name": "李四", "phone": "13800002222",
    "address": "花园小区", "service_type": "电路维修"
})
oid2 = d["id"]
s, d = req(f"/api/orders/{oid2}/status", "POST", {"status": "cancelled"}, token=token)
check("取消订单", s == 200, str(d)[:100])

# 16. 表单校验（空姓名）
s, d = req("/api/orders", "POST", {
    "customer_name": "", "phone": "13800002222", "address": "x", "service_type": "y"
})
check("空姓名校验", s == 422, str(s))

print(f"\n结果: {ok} 通过, {fail} 失败")
exit(1 if fail else 0)
