import sys, os, numpy as np
from PIL import Image
# despill.py <frames dir> : 초록 배경 번짐(외곽선 초록기) 제거 — G 를 max(R,B) 이하로 + 반투명 초록 픽셀 정리
d = sys.argv[1]
for f in os.listdir(d):
    if not f.endswith(".png"): continue
    p = os.path.join(d, f); a = np.array(Image.open(p).convert("RGBA")).astype(np.int16)
    r, g, b, al = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
    m = np.maximum(r, b)
    spill = g > m + 8
    a[..., 1] = np.where(spill, m + 8, g)
    # 거의 투명한데 초록이던 픽셀은 지움
    a[..., 3] = np.where(spill & (al < 90) & (g - m > 60), 0, al)
    Image.fromarray(a.clip(0, 255).astype(np.uint8)).save(p)
print("despilled", d)
