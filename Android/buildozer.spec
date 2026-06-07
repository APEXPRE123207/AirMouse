[app]

# App identity
title           = AirMouse
package.name    = airmouse
package.domain  = com.airmouse

# Source
source.dir      = src
source.include_exts = py,png,jpg,kv,atlas,json

# Version
version         = 0.1.0

# Python / Kivy requirements
requirements = python3,kivy==2.3.0,pyjnius,android

# Android-specific
android.permissions = BODY_SENSORS, INTERNET, ACCESS_NETWORK_STATE
android.api         = 34
android.minapi      = 24
android.ndk         = 25b
android.sdk         = 34
android.archs       = arm64-v8a, armeabi-v7a

# Sensor feature declaration (needed for Google Play)
android.manifest.sensors = android.hardware.sensor.gyroscope

# Orientation lock
orientation = portrait

# Icons (placeholder — replace before release)
# icon.filename = %(source.dir)s/icon.png

# Buildozer / p4a internals
log_level   = 2
warn_on_root = 1

[buildozer]
log_level = 2
