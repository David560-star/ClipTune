[app]
title = MusicDL
package.name = musicdl2
package.domain = org.musicdl
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 0.03
icon.filename = %(source.dir)s/icon.png
icon.adaptive_foreground.filename = %(source.dir)s/icon_fg.png
icon.adaptive_background.filename = %(source.dir)s/icon_bg.png
presplash.filename = %(source.dir)s/presplash.png
android.presplash_color = #FFFFFF
requirements = python3,kivy,yt-dlp,requests,certifi,openssl
orientation = portrait
fullscreen = 0
android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE,FOREGROUND_SERVICE,POST_NOTIFICATIONS
android.api = 33
android.minapi = 21
android.archs = arm64-v8a
android.accept_sdk_license = True
android.add_src = java
services = descargas:servicio.py:foreground

[buildozer]
log_level = 2
warn_on_root = 1
