import sys
from PIL import Image
# stitchg.py out W H ox,oy:file ...  (later args paste over earlier)
out, W, H = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
img = Image.new("RGB", (W, H), (0, 255, 0))
for a in sys.argv[4:]:
    o, f = a.split(":", 1); x, y = map(int, o.split(","))
    t = Image.open(f).convert("RGB"); img.paste(t, (x, y))
img.save(out); print(out, img.size)
