import sys, numpy as np
from PIL import Image
for f in sys.argv[1:]:
    im=np.array(Image.open(f).convert('RGB'))
    if im.shape[1]==864: im[:, -5:]=[0,255,0]; Image.fromarray(im).save(f); print('fixed',f)
