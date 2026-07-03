[app]
title = CGC比例监控
package.name = cgcmonitor
package.domain = org.goodchain

source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 1.0

# 核心修复：去掉了末尾错误的 android，移除了 kivy 的强行版本号
requirements = python3,kivy,requests,plyer,pyjnius,certifi,urllib3,chardet,idna

# 注册后台前台服务：
services = Monitor:service.py

orientation = portrait
fullscreen = 0

android.permissions = INTERNET,WAKE_LOCK,FOREGROUND_SERVICE,POST_NOTIFICATIONS,RECEIVE_BOOT_COMPLETED

android.api = 33
android.minapi = 24
android.ndk = 25b
android.accept_sdk_license = True
android.archs = arm64-v8a,armeabi-v7a

[buildozer]
log_level = 2
warn_on_root = 1
