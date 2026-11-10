# -*- coding: utf-8 -*-
import sys
from PIL import ImageGrab

out = sys.argv[1] if len(sys.argv) > 1 else "shot.png"
box = None
if len(sys.argv) > 5:
    box = tuple(int(v) for v in sys.argv[2:6])
img = ImageGrab.grab(all_screens=True, bbox=box)
img.save(out)
print(out, img.size)
