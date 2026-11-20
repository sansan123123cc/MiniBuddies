# st.py <out.png> <W> <H> <idx:ox:oy> ...  — 최신 스크린샷 폴더의 타일을 원본 크기로 이어 붙이기
import sys, glob, os
from PIL import Image
out, W, H = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
d = max(glob.glob('/tmp/claude-chrome-screenshots-*'), key=os.path.getmtime)
im = Image.new('RGB', (W, H), (0, 255, 0))
for t in sys.argv[4:]:
    i, ox, oy = map(int, t.split(':'))
    f = glob.glob(f'{d}/screenshot-*-{i}.jpg')[0]
    tl = Image.open(f).convert('RGB')
    im.paste(tl.crop((0, 0, min(tl.width, W - ox), min(tl.height, H - oy))), (ox, oy))
im.save(out); print(out, im.size, os.path.basename(d))
