# -*- coding: utf-8 -*-
"""数据库模型：订单、服务项目、客户账号"""
import os
from datetime import datetime

from sqlalchemy import (JSON, Column, DateTime, Float, Integer, String,
                        create_engine, text)
from sqlalchemy.orm import declarative_base, sessionmaker

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 支持 DATA_DIR 环境变量（Docker 部署挂载数据卷），默认与代码同目录
DATA_DIR = os.environ.get("DATA_DIR", BASE_DIR)
DB_PATH = os.path.join(DATA_DIR, "repair.db")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False)
Base = declarative_base()

# 订单状态流转: pending -> confirmed -> repairing -> completed / cancelled
ORDER_STATUS = {
    "pending": "待接单",
    "confirmed": "已预约",
    "repairing": "维修中",
    "completed": "已完成",
    "cancelled": "已取消",
}


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_name = Column(String(50), nullable=False)          # 客户姓名
    phone = Column(String(20), nullable=False)                   # 联系电话
    address = Column(String(200), nullable=False)                # 上门地址
    service_type = Column(String(50), nullable=False)            # 服务项目
    description = Column(String(500), default="")                # 故障描述
    photos = Column(JSON, default=list)                          # 照片URL列表
    scheduled_time = Column(String(50), default="")              # 期望上门时间
    status = Column(String(20), default="pending", index=True)   # 订单状态
    price = Column(Float, default=None)                          # 实际收费(完成时填写)
    note = Column(String(500), default="")                       # 师傅备注
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    user_id = Column(Integer, default=None, index=True)         # 下单客户(users.id)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    openid = Column(String(64), unique=True, index=True)          # 微信openid
    nickname = Column(String(50), default="")                     # 微信昵称
    name = Column(String(50), default="")                         # 联系称呼
    phone = Column(String(20), default="", index=True)            # 绑定手机号
    created_at = Column(DateTime, default=datetime.now)
    last_login_at = Column(DateTime, default=datetime.now)


class Service(Base):
    __tablename__ = "services"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)                    # 项目名称
    unit = Column(String(20), default="次")                      # 计价单位
    price = Column(Float, nullable=False)                        # 参考价格
    description = Column(String(200), default="")                # 说明


def init_db():
    Base.metadata.create_all(engine)
    # 已有库迁移：orders 表补充 user_id 列（create_all 不会给已存在的表加列）
    with engine.connect() as conn:
        cols = [row[1] for row in conn.execute(text("PRAGMA table_info(orders)"))]
        if "user_id" not in cols:
            conn.execute(text("ALTER TABLE orders ADD COLUMN user_id INTEGER"))
            conn.commit()
    # 预置服务项目
    with SessionLocal() as db:
        if db.query(Service).count() == 0:
            seeds = [
                ("水管维修", "次", 80, "漏水、水管爆裂、更换阀门"),
                ("水路改造", "米", 60, "PPR水管改线、重排"),
                ("电路维修", "次", 80, "跳闸、插座失灵、灯具更换"),
                ("电路改造", "米", 45, "开槽布线、换线、配电箱整理"),
                ("灯具安装", "个", 50, "吸顶灯、吊灯、筒灯安装"),
                ("洁具安装", "个", 100, "马桶、花洒、水龙头安装"),
                ("疏通下水", "次", 120, "马桶、地漏、下水道疏通"),
                ("上门检查", "次", 50, "仅排查问题，不维修"),
            ]
            for name, unit, price, desc in seeds:
                db.add(Service(name=name, unit=unit, price=price, description=desc))
            db.commit()
