# -*- coding: utf-8 -*-
"""
service.py
后台前台服务入口。在 buildozer.spec 中通过：
    services = Monitor:service.py
注册为 Android 前台服务（Foreground Service），
配合持久通知栏图标，可以在应用切到后台、甚至手机息屏时继续运行。

工作流程：
    循环 -> 读取配置(interval/tier2/tier3/address)
         -> 调用 API 获取 CGC / WGDC 数量
         -> 计算第1档实时比例 = CGC / WGDC
         -> 与第2档(低)/第3档(高)比较，触发通知
         -> 把结果写入状态文件，供前台界面读取展示
         -> sleep(interval分钟) 后重复
"""
import time
import traceback

from monitor_core import (
    load_config, save_status, fetch_token_amounts,
    compute_ratio, check_alert, now_str,
)

# 把当前服务提升为 Android 前台服务（会常驻一条通知，Android系统要求这样才能长期后台运行）
try:
    from android import AndroidService
    _service = AndroidService("CGC/WGDC 比例监控", "监控服务运行中")
    _service.start("监控已启动")
except Exception:
    _service = None  # 非 Android 环境（比如桌面调试）时忽略

# 通知使用 plyer（Android 上会调用系统通知）
try:
    from plyer import notification as plyer_notification
except Exception:
    plyer_notification = None


def send_notification(title, message):
    if plyer_notification:
        try:
            plyer_notification.notify(title=title, message=message, timeout=10)
            return
        except Exception:
            pass
    # 桌面调试兜底：打印到控制台
    print("[通知]", title, message)


def run_forever():
    while True:
        cfg = load_config()
        try:
            interval = max(1, int(cfg.get("interval_minutes", 5)))
        except (TypeError, ValueError):
            interval = 5
        address = cfg.get("address")
        rpc_url = cfg.get("rpc_url") or "https://rpc1.goodchainscan.org/"

        try:
            amounts = fetch_token_amounts(address, symbols=("CGC", "WGDC"), rpc_url=rpc_url)
            cgc = amounts.get("CGC")
            wgdc = amounts.get("WGDC")
            ratio = compute_ratio(cgc, wgdc)
            alert = check_alert(ratio, cfg.get("tier2_low"), cfg.get("tier3_high"))

            save_status({
                "cgc_amount": cgc,
                "wgdc_amount": wgdc,
                "ratio": ratio,
                "updated_at": now_str(),
                "error": None,
            })

            if alert == "low":
                send_notification("CGC/WGDC 比例提醒", "提示我现在比例数低！")
            elif alert == "high":
                send_notification("CGC/WGDC 比例提醒", "提示我现在比例数高！")

        except Exception as e:
            save_status({
                "error": str(e),
                "updated_at": now_str(),
            })
            traceback.print_exc()

        time.sleep(interval * 60)


if __name__ == "__main__":
    run_forever()
