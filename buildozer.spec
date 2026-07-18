[app]

title = لحظه‌ساز

package.name = lahzesaz
package.domain = org.amirvsh


source.dir = .

source.include_exts = py,png,jpg,jpeg,kv,json,txt,ttf,otf,atlas
source.include_patterns = assets/*,assets/**/*,fonts/*,fonts/**/*,logo/*,logo/**/*


version = 1.0.0


# Python + Kivy dependencies
requirements = python3,kivy==2.3.1,requests,pillow==10.2.0,arabic-reshaper,python-bidi,plyer,pyjnius


orientation = portrait

fullscreen = 0


# App icon
icon.filename = logo/logo.png



# Android SDK
android.api = 34
android.minapi = 24


# Match GitHub Actions NDK
android.ndk = 25b
android.ndk_api = 24


# Only build 64-bit
android.archs = arm64-v8a



# Permissions
android.permissions = INTERNET,CAMERA,READ_MEDIA_IMAGES



# AndroidX support
android.enable_androidx = True

android.accept_sdk_license = True



# Logs
android.logcat_filters = *:S python:D
android.logcat_pid_only = True



# Build system
p4a.bootstrap = sdl2


# Output
android.release_artifact = apk



# Debug
log_level = 2

warn_on_root = 0
