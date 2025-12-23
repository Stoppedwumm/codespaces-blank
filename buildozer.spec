[app]

# (str) Title of your application
title = Movie2k Explorer

# (str) Package name (one word, no special characters)
package.name = movieexplorer

# (str) Package domain (needed for android packaging)
package.domain = org.yourname

# (str) Source code where the main.py lives (the dot '.' means current directory)
source.dir = .

# (list) Source files to include
source.include_exts = py,png,jpg,kv,atlas

# (str) Application version
version = 0.1

# (list) Application requirements
# pyjnius is required for the Android Intent (video player) logic
requirements = python3, kivy, kivymd, requests, urllib3, certifi, chardet, idna, pillow, pyjnius, ffpyplayer, ffpyplayer_codecs

# (str) Supported orientation
orientation = portrait

# (bool) Fullscreen mode
fullscreen = 0

# (list) Permissions
android.permissions = INTERNET

android.meta_data = android.hardware.graphics.external=true