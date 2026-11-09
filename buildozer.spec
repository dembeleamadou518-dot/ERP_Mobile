[app]
title = ERP Quincaillerie Mobile
package.name = erpquincaillerie
package.domain = ml.dembele
p4a.branch = develop
source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas
version = 9.0
requirements = python3,kivy,plyer
orientation = portrait
fullscreen = 0

# Android moderne. Le APK doit être testé sur l'appareil avant utilisation réelle.
android.api = 33
android.accept_sdk_license = True
android.minapi = 23
android.ndk = 23b
android.archs = arm64-v8a, armeabi-v7a
android.permissions = READ_MEDIA_IMAGES

[buildozer]
log_level = 2
warn_on_root = 1

