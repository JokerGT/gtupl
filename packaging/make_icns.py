"""Build packaging/GTUpl.icns from the icon.png stored in assets.py (macOS only:
uses sips and iconutil). Run from the repository root."""
import base64
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from assets import ASSETS  # noqa: E402

out_dir = os.path.join("packaging", "GTUpl.iconset")
os.makedirs(out_dir, exist_ok=True)
src = os.path.join("packaging", "icon-source.png")
with open(src, "wb") as fh:
    fh.write(base64.b64decode(ASSETS["icon.png"]))

for size in (16, 32, 128, 256, 512):
    for scale in (1, 2):
        px = size * scale
        name = f"icon_{size}x{size}" + ("@2x" if scale == 2 else "") + ".png"
        subprocess.run(["sips", "-z", str(px), str(px), src, "--out", os.path.join(out_dir, name)],
                       check=True, stdout=subprocess.DEVNULL)

subprocess.run(["iconutil", "-c", "icns", out_dir, "-o", os.path.join("packaging", "GTUpl.icns")], check=True)
print("packaging/GTUpl.icns written")
