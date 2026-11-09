from PIL import Image, ImageFilter
from pathlib import Path
from collections import OrderedDict
src=Image.open(Path('Profili_cataloghi')/'_atl150_p21_source.png').convert('L')
out=Path('Profili_ritagliati')
# Coordinates verified against the source page: isolate the five individual profile drawings.
# AZ6600, 6601, 6602, 6603, 6604 in the left illustration column.
boxes=OrderedDict([
 ('AZ6600',(183,508,368,601)),
 ('AZ6601',(181,668,368,765)),
 ('AZ6602',(182,824,367,918)),
 ('AZ6603',(208,929,326,1083)),
 ('AZ6604',(177,1078,300,1155)),
])
# AZ4653 section profile, from the original clean 512px crop: retain all strokes and just trim whitespace.
for code,box in boxes.items():
    im=src.crop(box)
    # grayscale threshold to suppress paper texture but retain antialiased catalog linework
    im=im.filter(ImageFilter.UnsharpMask(radius=1.4,percent=130,threshold=2))
    im=im.point(lambda v: 0 if v<190 else 255,mode='L')
    bb=im.point(lambda v:255 if v<245 else 0).getbbox()
    if bb:
        pad=5; bb=(max(0,bb[0]-pad),max(0,bb[1]-pad),min(im.width,bb[2]+pad),min(im.height,bb[3]+pad))
        im=im.crop(bb)
    scale=min(1200/max(im.size),4)
    im=im.resize((round(im.width*scale),round(im.height*scale)),Image.Resampling.LANCZOS)
    im=im.point(lambda v:0 if v<185 else 255,mode='L')
    im.save(out/f'{code}.png',optimize=True)
# AZ4653 was already clean in the source illustration folder; preserve its full contour and improve only contrast/upscale.
im=Image.open(Path('Profili_cataloghi')/'AZ4653.png').convert('L')
bb=im.point(lambda v:255 if v<190 else 0).getbbox()
if bb:
 pad=10; bb=(max(0,bb[0]-pad),max(0,bb[1]-pad),min(im.width,bb[2]+pad),min(im.height,bb[3]+pad)); im=im.crop(bb)
im=im.filter(ImageFilter.UnsharpMask(radius=1.2,percent=100,threshold=3))
im=im.resize((900,round(im.height*900/im.width)),Image.Resampling.LANCZOS).point(lambda v:0 if v<185 else 255,mode='L')
im.save(out/'AZ4653.png',optimize=True)
print('updated',', '.join([*boxes.keys(),'AZ4653']))
