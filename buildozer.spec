[app]
title = MusicDL
package.name = musicdl
package.domain = org.musicdl
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 0.01
icon.filename = %(source.dir)s/icon.png
presplash.filename = %(source.dir)s/icon.png
android.presplash_color = #12141C
requirements = python3,kivy,yt-dlp,requests,certifi,openssl
orientation = portrait
android.manifest.intent_filters = intent_filters.xml
android.manifest.launch_mode = singleTask
fullscreen = 0
android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE
android.api = 33
android.minapi = 21
android.archs = arm64-v8a
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
