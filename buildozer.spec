[app]

title = لحظه‌ساز
package.name = lahzesaz
package.domain = org.amirvsh

source.dir = .

source.include_exts = py,png,jpg,jpeg,kv,json,txt,ttf,otf,atlas
source.include_patterns = assets/*,assets/**/*,fonts/*,fonts/**/*,logo/*,logo/**/*

version = 1.0.0

requirements = python3,kivy==2.3.0,requests,pillow,arabic-reshaper,python-bidi,plyer,pyjnius

orientation = portrait

fullscreen = 0

icon.filename = logo/logo.png

android.api = 34
android.minapi = 24

android.ndk = 25b
android.ndk_api = 24

android.archs = arm64-v8a,armeabi-v7a

android.permissions = INTERNET,CAMERA,READ_MEDIA_IMAGES

android.enable_androidx = True

android.accept_sdk_license = True

android.logcat_filters = *:S python:D
android.logcat_pid_only = True

p4a.bootstrap = sdl2

android.copy_libs = 1

android.release_artifact = apk

log_level = 2
warn_on_root = 0
