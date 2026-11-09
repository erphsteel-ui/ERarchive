"""Small local masthead descriptors; no OCR/model loading and no external API."""
from PIL import Image,ImageOps,ImageFilter,ImageStat

def header_signature(path):
    try:
        with Image.open(path) as src:
            im=ImageOps.exif_transpose(src).convert('RGB')
            if im.width<40 or im.height<40:return None
            header=im.crop((0,0,im.width,max(1,round(im.height*.23)))).resize((96,32),Image.Resampling.BILINEAR)
            pixels=list(header.getdata())
            # Near-empty paper and uniform bands are insufficient evidence.
            ink=sum(min(p)<210 for p in pixels)/len(pixels)
            variance=sum(ImageStat.Stat(header).stddev)/3
            if ink<.035 or variance<12:return None
            blurred=header.filter(ImageFilter.GaussianBlur(1.5)).resize((24,8),Image.Resampling.BILINEAR)
            rgb=list(blurred.getdata())
            gray=header.convert('L').resize((25,8),Image.Resampling.BILINEAR)
            values=list(gray.getdata());bits=[int(values[y*25+x]>values[y*25+x+1]) for y in range(8) for x in range(24)]
            # Spatial color grid + edge-direction pattern, not color alone.
            return {'rgb':rgb,'bits':bits,'ink':ink,'ratio':im.width/im.height}
    except (OSError,ValueError,Image.DecompressionBombError):return None

def similarity(a,b):
    if not a or not b or abs(a['ratio']-b['ratio'])>.12:return 0
    if abs(a['ink']-b['ink'])>.22:return 0
    color=1-sum(abs(x-y) for p,q in zip(a['rgb'],b['rgb']) for x,y in zip(p,q))/(len(a['rgb'])*3*255)
    edges=1-sum(x!=y for x,y in zip(a['bits'],b['bits']))/len(a['bits'])
    # Both layout and color must agree. This score is similarity, not probability.
    return min(color,edges)
