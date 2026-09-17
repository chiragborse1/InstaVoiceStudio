"""Rebuild the original README banner with Pillow on Windows."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import math

ROOT = Path(__file__).resolve().parent
im = Image.new('RGB', (1600, 560), '#181b1a')
d = ImageDraw.Draw(im)
def font(size, bold=False):
    path = Path('C:/Windows/Fonts') / ('segoeuib.ttf' if bold else 'segoeui.ttf')
    return ImageFont.truetype(str(path), size)
d.rounded_rectangle((30,30,1570,530),radius=26,outline='#3b423e',width=2)
d.text((90,76),'A SMALL STUDIO. ALL YOUR CONTROLS.',font=font(20,True),fill='#a5c1ad')
d.text((84,137),'InstaVoice',font=font(100,True),fill='#f2eedf')
d.text((90,260),'STUDIO',font=font(30,True),fill='#a5c1ad')
d.text((90,338),'Your audio. Your controls.',font=font(33),fill='#f2eedf')
d.text((90,391),'Preview locally. Review the recipient. Send manually.',font=font(23),fill='#9da6a0')
for i in range(43):
    x=987+i*10
    h=14+144*abs(math.sin(i*.37))*math.exp(-((i-21)/19)**2)
    d.rounded_rectangle((x,264-h/2,x+5,264+h/2),radius=3,fill='#a5c1ad' if i<26 else '#55655c')
d.line((950,405,1470,405),fill='#3b423e',width=2)
d.text((996,425),'FILE  /  MIC  /  PREVIEW  /  SEND',font=font(18,True),fill='#a5c1ad')
d.text((90,477),'WINDOWS DESKTOP    ·    PYTHON    ·    OPEN SOURCE',font=font(17),fill='#77877c')
im.save(ROOT/'banner.png',optimize=True)
print('Rendered',ROOT/'banner.png',im.size)
