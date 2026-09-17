"""Render a local logo concept for review; does not publish anything."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
DARK, SAGE, CREAM = '#181b1a', '#a5c1ad', '#f2eedf'
HEIGHTS = [110, 180, 254, 158, 222, 140, 90]

def font(size, bold=False):
    return ImageFont.truetype('C:/Windows/Fonts/'+('segoeuib.ttf' if bold else 'segoeui.ttf'), size)

def icon(size, tile=True, mono=False):
    im = Image.new('RGBA',(1024,1024))
    d = ImageDraw.Draw(im)
    if tile:
        d.rounded_rectangle((24,24,1000,1000),radius=218,fill=DARK)
    for i,h in enumerate(HEIGHTS):
        x=132+i*118
        color = DARK if mono else (CREAM if i==2 else SAGE)
        d.rounded_rectangle((x,512-h,x+52,512+h),radius=26,fill=color)
    return im.resize((size,size),Image.Resampling.LANCZOS)

for size in (512,128,64,32):
    icon(size).save(ROOT/f'logo-icon-{size}.png')
icon(512,False).save(ROOT/'logo-icon-transparent-dark-surface.png')
bars=''.join(f'<rect x="{66+i*59}" y="{256-h/2}" width="26" height="{h}" rx="13" fill="{CREAM if i==2 else SAGE}"/>' for i,h in enumerate(HEIGHTS))
(ROOT/'logo-icon.svg').write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><rect x="12" y="12" width="488" height="488" rx="109" fill="{DARK}"/>{bars}</svg>',encoding='utf-8')

sheet=Image.new('RGBA',(1440,900),'#eeeee7')
d=ImageDraw.Draw(sheet)
d.text((60,40),'INSTAVOICE STUDIO',font=font(23,True),fill=DARK)
d.text((1040,44),'LOGO CONCEPT / 01',font=font(18),fill='#68746b')
d.line((60,92,1380,92),fill='#c9cec7',width=2)
sheet.alpha_composite(icon(340),(94,154))
d.text((107,522),'Primary app icon',font=font(22),fill=DARK)
d.rounded_rectangle((530,132,1380,592),radius=22,fill=DARK)
d.text((578,169),'VOICE, MADE VISIBLE.',font=font(17,True),fill=SAGE)
sheet.alpha_composite(icon(150),(572,280))
d.text((752,276),'InstaVoice',font=font(78,True),fill=CREAM)
d.text((759,382),'S T U D I O',font=font(25,True),fill=SAGE)
d.text((580,530),'Charcoal / Sage / Warm cream',font=font(19),fill='#99a59c')
d.line((60,640,1380,640),fill='#c9cec7',width=2)
d.text((80,684),'At small sizes',font=font(21,True),fill=DARK)
for x,size in ((310,64),(428,32)):
    sheet.alpha_composite(icon(size),(x,686))
    d.text((x,770),str(size)+' px',font=font(17),fill='#68746b')
sheet.alpha_composite(icon(100,False,True),(735,688))
d.text((862,707),'Single-color mark',font=font(23),fill=DARK)
d.text((862,747),'For light backgrounds and print',font=font(18),fill='#68746b')
d.text((80,842),'Preview only — not applied to the app or GitHub.',font=font(17),fill='#68746b')
sheet.convert('RGB').save(ROOT/'logo-review-sheet.png')
wm=Image.new('RGBA',(1300,320),DARK)
wm.alpha_composite(icon(220),(35,50))
w=ImageDraw.Draw(wm)
w.text((300,54),'InstaVoice',font=font(125,True),fill=CREAM)
w.text((310,218),'S T U D I O',font=font(33,True),fill=SAGE)
wm.save(ROOT/'logo-wordmark.png')
print('Rendered review sheet, SVG, wordmark, and 4 icon sizes.')
