[app]

# App identity
title           = AirMouse
package.name    = airmouse
package.domain  = com.airmouse

# Source
source.dir      = src
source.include_exts = py,png,jpg,kv,atlas,json,ttf

# Version
version         = 0.1.0

# IMPORTANT: pin python3 to 3.11 explicitly.
# p4a (python-for-android) now defaults to Python 3.14, but Kivy 2.3.0's
# Cython-generated C code calls _PyLong_AsByteArray() with 5 args.
# Python 3.14 changed that internal API to require 6 args → compile error.
# Kivy 2.3.0 only supports up to Python 3.11 / 3.12. Pin to 3.11 to be safe.
requirements = python3==3.11.9,hostpython3==3.11.9,kivy==2.3.0,pyjnius,android

# Android-specific
android.permissions = BODY_SENSORS, INTERNET, ACCESS_NETWORK_STATE
android.api         = 34
android.minapi      = 24
android.ndk         = 25b
# android.sdk is deprecated — removed
# Build arm64 only for CI speed; add armeabi-v7a for a release build
android.archs       = arm64-v8a

# NOTE: android.manifest.sensors is NOT a valid buildozer key and breaks the build.
# To declare the gyroscope feature, add it via a custom manifest fragment instead:
# android.add_manifest_xml_path = manifest_extras.xml
# (see BUILD_GUIDE for how to create that file if needed for Play Store)

# Orientation lock
orientation = portrait

# Icons
icon.filename = %(source.dir)s/logo.jpg

# Buildozer internals
log_level = 2

[buildozer]
log_level    = 2
warn_on_root = 0
