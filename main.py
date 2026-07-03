# -*- coding: utf-8 -*-
"""
main.py
应用主界面（前台 Activity）。
- 设置：刷新间隔(分钟)、第2档比例(低)、第3档比例(高)、监控地址
- 启动/停止：把设置写入配置文件，并启动/停止后台前台服务(service.py)
- 展示：定时读取后台服务写入的状态文件，刷新界面显示的 第1档实时比例 / CGC数量 / WGDC数量
"""
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.clock import Clock

from monitor_core import load_config, save_config, load_status, DEFAULT_ADDRESS

# 必须和 buildozer.spec 中的 package.domain / package.name 保持一致
SERVICE_JAVA_CLASS = "org.goodchain.cgcmonitor.ServiceMonitor"


def start_android_service():
    try:
        from jnius import autoclass
        service = autoclass(SERVICE_JAVA_CLASS)
        mActivity = autoclass("org.kivy.android.PythonActivity").mActivity
        service.start(mActivity, "")
        return True
    except Exception as e:
        print("启动后台服务失败（非Android环境时属正常）：", e)
        return False


def stop_android_service():
    try:
        from jnius import autoclass
        service = autoclass(SERVICE_JAVA_CLASS)
        mActivity = autoclass("org.kivy.android.PythonActivity").mActivity
        service.stop(mActivity)
        return True
    except Exception as e:
        print("停止后台服务失败（非Android环境时属正常）：", e)
        return False


def request_android_permissions():
    try:
        from android.permissions import request_permissions, Permission
        perms = [Permission.INTERNET, Permission.WAKE_LOCK]
        try:
            perms.append(Permission.POST_NOTIFICATIONS)  # Android 13+ 通知权限
        except Exception:
            pass
        request_permissions(perms)
    except Exception as e:
        print("权限请求跳过（非Android环境）：", e)


class MonitorApp(App):
    title = "CGC/WGDC 比例监控"

    def build(self):
        request_android_permissions()
        self.cfg = load_config()

        root = BoxLayout(orientation="vertical", padding=16, spacing=10)

        form = GridLayout(cols=2, spacing=8, size_hint_y=None)
        form.bind(minimum_height=form.setter("height"))

        form.add_widget(Label(text="刷新间隔（分钟）："))
        self.interval_input = TextInput(
            text=str(self.cfg.get("interval_minutes", 5)),
            multiline=False, input_filter="int",
        )
        form.add_widget(self.interval_input)

        form.add_widget(Label(text="第2档比例（低于则提醒“比例数低”）："))
        self.tier2_input = TextInput(
            text=str(self.cfg.get("tier2_low", "")),
            multiline=False, input_filter="float",
        )
        form.add_widget(self.tier2_input)

        form.add_widget(Label(text="第3档比例（高于则提醒“比例数高”）："))
        self.tier3_input = TextInput(
            text=str(self.cfg.get("tier3_high", "")),
            multiline=False, input_filter="float",
        )
        form.add_widget(self.tier3_input)

        form.add_widget(Label(text="监控地址（DEX交易对）："))
        self.address_input = TextInput(
            text=self.cfg.get("address", DEFAULT_ADDRESS),
            multiline=False,
        )
        form.add_widget(self.address_input)

        form.add_widget(Label(text="RPC 节点地址："))
        self.rpc_input = TextInput(
            text=self.cfg.get("rpc_url", "https://rpc1.goodchainscan.org/"),
            multiline=False,
        )
        form.add_widget(self.rpc_input)

        root.add_widget(form)

        btn_row = BoxLayout(size_hint_y=None, height=48, spacing=8)
        self.start_btn = Button(text="保存并启动监控", on_press=self.on_start)
        self.stop_btn = Button(text="停止监控", on_press=self.on_stop)
        btn_row.add_widget(self.start_btn)
        btn_row.add_widget(self.stop_btn)
        root.add_widget(btn_row)

        self.status_label = Label(
            text="第1档实时比例：--\nCGC 数量：--\nWGDC 数量：--\n上次更新：--",
            size_hint_y=None, height=160, halign="left", valign="top",
        )
        self.status_label.bind(size=self._sync_text_size)
        root.add_widget(self.status_label)

        hint = Label(
            text="提示：开启后请在系统设置中允许本应用【后台运行】并关闭【电池优化】，"
                 "否则息屏一段时间后系统可能会限制服务。",
            size_hint_y=None, height=60, halign="left", valign="top",
        )
        hint.bind(size=self._sync_text_size)
        root.add_widget(hint)

        Clock.schedule_interval(self.refresh_display, 5)
        return root

    def _sync_text_size(self, instance, value):
        instance.text_size = (instance.width, None)

    def on_start(self, *args):
        try:
            interval = int(self.interval_input.text or 5)
        except ValueError:
            interval = 5
        try:
            tier2 = float(self.tier2_input.text) if self.tier2_input.text else 0.0
        except ValueError:
            tier2 = 0.0
        try:
            tier3 = float(self.tier3_input.text) if self.tier3_input.text else 0.0
        except ValueError:
            tier3 = 0.0

        self.cfg.update({
            "interval_minutes": interval,
            "tier2_low": tier2,
            "tier3_high": tier3,
            "address": self.address_input.text.strip() or DEFAULT_ADDRESS,
            "rpc_url": self.rpc_input.text.strip() or "https://rpc1.goodchainscan.org/",
            "running": True,
        })
        save_config(self.cfg)
        start_android_service()
        self.status_label.text = "监控已启动，等待第一次刷新..."

    def on_stop(self, *args):
        self.cfg["running"] = False
        save_config(self.cfg)
        stop_android_service()
        self.status_label.text = "监控已停止"

    def refresh_display(self, dt):
        status = load_status()
        if not status:
            return
        if status.get("error"):
            self.status_label.text = (
                f"获取失败：{status.get('error')}\n上次更新：{status.get('updated_at', '--')}"
            )
            return
        ratio = status.get("ratio")
        ratio_text = f"{ratio:.6f}" if ratio is not None else "--"
        self.status_label.text = (
            f"第1档实时比例（CGC/WGDC）：{ratio_text}\n"
            f"CGC 数量：{status.get('cgc_amount', '--')}\n"
            f"WGDC 数量：{status.get('wgdc_amount', '--')}\n"
            f"上次更新：{status.get('updated_at', '--')}"
        )


if __name__ == "__main__":
    MonitorApp().run()
