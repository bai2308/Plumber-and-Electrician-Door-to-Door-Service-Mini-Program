# -*- coding: utf-8 -*-
"""水电工上门维修小程序后端 — FastAPI + SQLite"""
import hashlib
import hmac
import json
import os
import re
import secrets
import time
import urllib.request
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import case, extract, func, or_
from sqlalchemy.orm import Session

from models import ORDER_STATUS, SessionLocal, Service, UPLOAD_DIR, Order, User, init_db

# ===== 配置 =====
MASTER_PASSWORD = os.environ.get("MASTER_PASSWORD", "123456")  # 师傅端登录密码
TOKEN_TTL = 7 * 24 * 3600  # 师傅 token 有效期（秒）
USER_TOKEN_TTL = 365 * 24 * 3600  # 客户登录 token 有效期（秒）
AUTH_SECRET = os.environ.get("AUTH_SECRET", "repair-secret-do-not-use-in-prod")
# 微信小程序正式登录需要配置（微信公众平台-开发设置里获取）；不配置则走开发模式
WX_APPID = os.environ.get("WX_APPID", "")
WX_SECRET = os.environ.get("WX_SECRET", "")

app = FastAPI(title="水电维修上门服务")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()
# 照片静态访问: /uploads/xxx.jpg
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


# ===== 依赖 =====
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ===== 师傅认证 =====
_tokens = {}  # token -> 过期时间戳（个人使用，内存存储即可，重启需重登）


def require_master(authorization: str = Header(default="")):
    token = authorization.replace("Bearer ", "").strip()
    exp = _tokens.get(token)
    if not exp or exp < datetime.now().timestamp():
        raise HTTPException(401, "请先登录师傅账号")
    return token


# ===== 客户（微信）认证 =====
def _sign(payload: str) -> str:
    return hmac.new(AUTH_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()[:16]


def make_user_token(uid: int) -> str:
    """无状态签名 token：uid.过期时间.签名（服务重启不失效）"""
    exp = int(time.time()) + USER_TOKEN_TTL
    return f"{uid}.{exp}.{_sign(f'{uid}.{exp}')}"


def require_user(authorization: str = Header(default=""),
                 db: Session = Depends(get_db)) -> User:
    token = authorization.replace("Bearer ", "").strip()
    parts = token.split(".")
    if len(parts) != 3:
        raise HTTPException(401, "请先登录")
    uid, exp, sig = parts
    try:
        exp_int = int(exp)
    except ValueError:
        raise HTTPException(401, "登录凭证无效")
    if not hmac.compare_digest(_sign(f"{uid}.{exp}"), sig) or exp_int < time.time():
        raise HTTPException(401, "登录已过期，请重新登录")
    user = db.get(User, int(uid))
    if not user:
        raise HTTPException(401, "账号不存在")
    return user


def user_to_dict(u: User) -> dict:
    return {
        "id": u.id,
        "nickname": u.nickname or "",
        "name": u.name or "",
        "phone": u.phone or "",
        "has_phone": bool(u.phone),
    }


def wx_code2session(code: str) -> Optional[str]:
    """code 换 openid；未配置 AppID/Secret 时返回 None（开发模式）"""
    if not (WX_APPID and WX_SECRET):
        return None
    url = (f"https://api.weixin.qq.com/sns/jscode2session?appid={WX_APPID}"
           f"&secret={WX_SECRET}&js_code={code}&grant_type=authorization_code")
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        raise HTTPException(502, "微信登录服务暂不可用，请稍后再试")
    if "openid" not in data:
        raise HTTPException(400, "微信登录失败：" + str(data.get("errmsg", "未知错误")))
    return data["openid"]


def order_to_dict(o: Order, with_detail: bool = False) -> dict:
    d = {
        "id": o.id,
        "customer_name": o.customer_name,
        "phone": o.phone,
        "address": o.address,
        "service_type": o.service_type,
        "status": o.status,
        "status_text": ORDER_STATUS.get(o.status, o.status),
        "price": o.price,
        "created_at": o.created_at.strftime("%Y-%m-%d %H:%M"),
    }
    if with_detail:
        d.update({
            "description": o.description,
            "photos": o.photos or [],
            "scheduled_time": o.scheduled_time,
            "note": o.note,
            "updated_at": o.updated_at.strftime("%Y-%m-%d %H:%M"),
        })
    return d


# ===== 请求模型 =====
class OrderCreate(BaseModel):
    customer_name: str = Field(min_length=1, max_length=50)
    phone: str = Field(min_length=5, max_length=20)
    address: str = Field(min_length=1, max_length=200)
    service_type: str = Field(min_length=1, max_length=50)
    description: str = ""
    photos: List[str] = []
    scheduled_time: str = ""


class MasterLogin(BaseModel):
    password: str


class WxLogin(BaseModel):
    code: str
    dev_id: str = ""     # 开发模式下区分不同设备的账号
    nickname: str = ""


class BindPhone(BaseModel):
    phone: str
    name: str = ""


class StatusUpdate(BaseModel):
    status: str  # confirmed / repairing / completed / cancelled
    price: Optional[float] = None
    note: Optional[str] = None


# ===== 客户端接口 =====
@app.get("/api/services")
def list_services(db: Session = Depends(get_db)):
    items = db.query(Service).order_by(Service.id).all()
    return [{"id": s.id, "name": s.name, "unit": s.unit,
             "price": s.price, "description": s.description} for s in items]


# ---- 微信登录 ----
@app.post("/api/auth/login")
def auth_login(data: WxLogin, db: Session = Depends(get_db)):
    """微信一键登录：code 换 openid，自动注册；需绑定手机号后才能下单"""
    openid = wx_code2session(data.code)
    if openid is None:  # 开发模式（未配置 WX_APPID/WX_SECRET），按 dev_id 生成稳定身份
        openid = "dev_" + hashlib.sha1(("dev:" + (data.dev_id or "default")).encode()).hexdigest()[:16]
    user = db.query(User).filter(User.openid == openid).first()
    if not user:
        user = User(openid=openid, nickname=(data.nickname or "").strip()[:50])
        db.add(user)
    user.last_login_at = datetime.now()
    db.commit()
    return {"token": make_user_token(user.id), "user": user_to_dict(user)}


@app.post("/api/auth/bind-phone")
def bind_phone(data: BindPhone, db: Session = Depends(get_db),
               user: User = Depends(require_user)):
    """绑定/更新联系手机号与称呼（登录后必填）"""
    phone = data.phone.strip()
    if not re.match(r"^1\d{10}$", phone):
        raise HTTPException(400, "手机号格式不正确")
    user.phone = phone
    if data.name.strip():
        user.name = data.name.strip()[:50]
    db.commit()
    return user_to_dict(user)


@app.get("/api/auth/me")
def auth_me(user: User = Depends(require_user)):
    return user_to_dict(user)


@app.post("/api/orders")
def create_order(data: OrderCreate, db: Session = Depends(get_db),
                 user: User = Depends(require_user)):
    """下单（需登录）；同时把手机号同步为客户绑定手机号"""
    order = Order(
        customer_name=data.customer_name.strip(),
        phone=data.phone.strip(),
        address=data.address.strip(),
        service_type=data.service_type.strip(),
        description=data.description.strip(),
        photos=data.photos,
        scheduled_time=data.scheduled_time.strip(),
        user_id=user.id,
    )
    # 下单手机号与绑定手机号保持一致（客户改号即视为更新绑定）
    if user.phone != order.phone:
        user.phone = order.phone
    if not user.name:
        user.name = order.customer_name
    db.add(order)
    db.commit()
    return {"id": order.id, "message": "下单成功，请等待师傅接单"}


@app.get("/api/orders/my")
def my_orders(db: Session = Depends(get_db), user: User = Depends(require_user)):
    """登录客户查询自己的订单（按账号或绑定手机号）"""
    q = db.query(Order).filter(Order.user_id == user.id)
    if user.phone:
        q = db.query(Order).filter(or_(Order.user_id == user.id, Order.phone == user.phone))
    orders = q.order_by(Order.id.desc()).all()
    return [order_to_dict(o, with_detail=True) for o in orders]


@app.get("/api/orders")
def query_orders(phone: str, db: Session = Depends(get_db)):
    """按手机号查询订单（师傅端客户历史也复用此接口）"""
    orders = (db.query(Order).filter(Order.phone == phone.strip())
              .order_by(Order.id.desc()).all())
    return [order_to_dict(o, with_detail=True) for o in orders]


@app.get("/api/orders/{order_id}")
def order_detail(order_id: int, db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(404, "订单不存在")
    return order_to_dict(order, with_detail=True)


@app.post("/api/upload")
async def upload_photo(file: UploadFile = File(...)):
    """上传故障照片，返回可访问URL"""
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise HTTPException(400, "仅支持 jpg/png/webp 图片")
    content = await file.read()
    if len(content) > 8 * 1024 * 1024:
        raise HTTPException(400, "图片不能超过8MB")
    name = f"{uuid.uuid4().hex}{ext}"
    with open(os.path.join(UPLOAD_DIR, name), "wb") as f:
        f.write(content)
    return {"url": f"/uploads/{name}"}


# ===== 师傅端接口 =====
@app.post("/api/master/login")
def master_login(data: MasterLogin):
    if data.password != MASTER_PASSWORD:
        raise HTTPException(401, "密码错误")
    token = secrets.token_hex(16)
    _tokens[token] = datetime.now().timestamp() + TOKEN_TTL
    return {"token": token, "expires_in": TOKEN_TTL}


@app.get("/api/master/orders")
def master_orders(status: Optional[str] = None, db: Session = Depends(get_db),
                  _: str = Depends(require_master)):
    q = db.query(Order)
    if status:
        q = q.filter(Order.status == status)
    orders = q.order_by(Order.id.desc()).all()
    return [order_to_dict(o, with_detail=True) for o in orders]


@app.post("/api/orders/{order_id}/status")
def update_status(order_id: int, data: StatusUpdate,
                  db: Session = Depends(get_db), _: str = Depends(require_master)):
    """师傅更新订单状态；完成时填写实际收费"""
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(404, "订单不存在")
    if data.status not in ORDER_STATUS or data.status == "pending":
        raise HTTPException(400, "非法的订单状态")
    order.status = data.status
    if data.price is not None:
        order.price = data.price
    if data.note is not None:
        order.note = data.note
    db.commit()
    return {"message": "状态已更新", "status": order.status}


@app.delete("/api/orders/{order_id}")
def delete_order(order_id: int, db: Session = Depends(get_db),
                 _: str = Depends(require_master)):
    """师傅删除订单（硬删除，同时清理关联的照片文件）"""
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(404, "订单不存在")
    for photo in (order.photos or []):
        path = os.path.join(UPLOAD_DIR, os.path.basename(photo))
        if os.path.isfile(path):
            try:
                os.remove(path)
            except OSError:
                pass
    db.delete(order)
    db.commit()
    return {"message": "订单已删除"}


@app.get("/api/master/customers")
def master_customers(q: str = "", db: Session = Depends(get_db),
                     _: str = Depends(require_master)):
    """客户信息管理：按手机号聚合订单量、完成量、累计消费、最近下单"""
    rows = (db.query(
        Order.phone.label("phone"),
        func.max(Order.customer_name).label("name"),
        func.count(Order.id).label("total"),
        func.sum(case((Order.status == "completed", 1), else_=0)).label("completed"),
        func.coalesce(func.sum(case((Order.status == "completed", Order.price), else_=0)), 0).label("spent"),
        func.max(Order.created_at).label("last_at"),
        func.max(Order.address).label("address"),
    ).filter(Order.phone != "").group_by(Order.phone).all())

    # 已注册客户（微信登录过）的手机号 -> 昵称
    users = {u.phone: u for u in db.query(User).filter(User.phone != "").all()}

    kw = q.strip()
    result = []
    for r in rows:
        if kw and kw not in (r.phone or "") and kw not in (r.name or ""):
            continue
        u = users.get(r.phone)
        result.append({
            "phone": r.phone,
            "name": r.name or "",
            "nickname": (u.nickname if u else "") or "",
            "total": int(r.total),
            "completed": int(r.completed or 0),
            "spent": round(float(r.spent or 0), 2),
            "last_at": r.last_at.strftime("%Y-%m-%d %H:%M") if r.last_at else "",
            "address": r.address or "",
            "registered": bool(u),
        })
    result.sort(key=lambda x: x["last_at"], reverse=True)
    return result


@app.get("/api/master/stats")
def master_stats(month: Optional[str] = None, db: Session = Depends(get_db),
                 _: str = Depends(require_master)):
    """收入统计；month 格式 YYYY-MM，默认当月"""
    if not month:
        month = datetime.now().strftime("%Y-%m")
    try:
        year, mon = int(month[:4]), int(month[5:7])
    except (ValueError, IndexError):
        raise HTTPException(400, "month 格式应为 YYYY-MM")

    base = (db.query(Order)
            .filter(Order.status == "completed",
                    extract("year", Order.created_at) == year,
                    extract("month", Order.created_at) == mon))
    total = base.with_entities(func.count(Order.id), func.coalesce(func.sum(Order.price), 0)).one()
    completed_orders = base.order_by(Order.id.desc()).all()

    # 各状态订单数量
    status_count = dict(
        db.query(Order.status, func.count(Order.id))
        .filter(extract("year", Order.created_at) == year,
                extract("month", Order.created_at) == mon)
        .group_by(Order.status).all()
    )

    return {
        "month": month,
        "completed_count": total[0],
        "total_income": round(float(total[1]), 2),
        "status_count": {ORDER_STATUS.get(k, k): v for k, v in status_count.items()},
        "orders": [order_to_dict(o) for o in completed_orders],
    }


@app.get("/api/health")
def health():
    return {"status": "ok"}
