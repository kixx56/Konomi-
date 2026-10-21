"""Actual ISO QR symbols, vector print PDF and SVG/PNG download ZIP; no AI images."""
import io
import json
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
import zipfile
import qrcode
from qrcode.constants import ERROR_CORRECT_Q
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pydantic import BaseModel, Field, field_validator
from xml.sax.saxutils import escape

ASSETS=Path(__file__).with_name('assets')

class QRRequest(BaseModel):
    base_url:str=Field(min_length=8,max_length=500)
    count:int=Field(default=30,ge=1,le=200)
    start:int=Field(default=1,ge=1,le=9999)
    venue:str=Field(default='',max_length=100)
    @field_validator('base_url')
    @classmethod
    def url(cls,v):
        p=urlsplit(v.strip())
        if p.scheme not in ('https','http') or not p.hostname or p.username or p.password or p.query or p.fragment or p.path not in ('','/'):
            raise ValueError('Укажите origin сайта без пути, логина, параметров и якоря: https://restaurant.example')
        try:p.port
        except ValueError:raise ValueError('Неверный порт в URL')
        return urlunsplit((p.scheme,p.netloc,'','',''))

def matrix(url):
    qr=qrcode.QRCode(error_correction=ERROR_CORRECT_Q,box_size=10,border=4)
    qr.add_data(url);qr.make(fit=True)
    return qr.get_matrix(),qr

def svg(url):
    grid,_=matrix(url);n=len(grid)
    squares=''.join(f'M{x} {y}h1v1h-1z' for y,row in enumerate(grid) for x,value in enumerate(row) if value)
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="600" height="600" viewBox="0 0 {n} {n}" role="img"><title>{escape(url)}</title><rect width="{n}" height="{n}" fill="#fff"/><path d="{squares}" fill="#0f1115"/></svg>'

def manifest(body):
    if body.start+body.count-1>9999:raise ValueError('Последний столик должен иметь номер не больше 9999')
    return [{'table':i,'url':f'{body.base_url}/?table={i}'} for i in range(body.start,body.start+body.count)]

def print_pdf(body,venue):
    rows=manifest(body);buf=io.BytesIO()
    if 'KonomiPrint' not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(TTFont('KonomiPrint',str(ASSETS/'DejaVuSans.ttf')))
    c=canvas.Canvas(buf,pagesize=A4,pageCompression=1)
    c.setTitle(f'{venue} — table QR cards');c.setAuthor('Konomi AI')
    # Six cut cards on A4. QR size 50mm, quiet zone included. Print at 100% scale.
    W,H=A4;cw,ch=89*mm,87*mm;mx=(W-2*cw)/2;my=(H-3*ch)/2
    for k,row in enumerate(rows):
        if k and k%6==0:c.showPage()
        pos=k%6;x=mx+(pos%2)*cw;y=H-my-(pos//2+1)*ch
        c.setStrokeColorRGB(.85,.87,.82);c.setDash(2,3);c.rect(x,y,cw,ch,stroke=1,fill=0);c.setDash()
        c.setFillColorRGB(.06,.07,.08);c.setFont('KonomiPrint',10)
        title=venue if pdfmetrics.stringWidth(venue,'KonomiPrint',10)<cw-14*mm else venue[:36]+'…'
        c.drawCentredString(x+cw/2,y+ch-9*mm,title)
        c.setFont('KonomiPrint',9);c.drawCentredString(x+cw/2,y+ch-16*mm,f'TABLE / STÓŁ {row["table"]}')
        grid,_=matrix(row['url']);size=50*mm;step=size/len(grid);qx=x+(cw-size)/2;qy=y+14*mm
        c.setFillColorRGB(1,1,1);c.rect(qx,qy,size,size,fill=1,stroke=0)
        c.setFillColorRGB(.06,.07,.08)
        for iy,line in enumerate(grid):
            for ix,bit in enumerate(line):
                if bit:c.rect(qx+ix*step,qy+size-(iy+1)*step,step+.01,step+.01,fill=1,stroke=0)
        c.setFont('KonomiPrint',7);c.drawCentredString(x+cw/2,y+9*mm,'Konomi AI · Scan for menu')
        c.setFont('KonomiPrint',5.5);c.drawCentredString(x+cw/2,y+5*mm,urlsplit(body.base_url).netloc)
    c.save();return buf.getvalue()

def archive(body,venue):
    buf=io.BytesIO();rows=manifest(body)
    with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('table-cards-a4.pdf',print_pdf(body,venue))
        z.writestr('tables.json',json.dumps(rows,ensure_ascii=False,indent=2))
        for row in rows:
            z.writestr(f'table-{row["table"]}.svg',svg(row['url']))
            image=io.BytesIO();_,qr=matrix(row['url']);qr.make_image(fill_color='#0f1115',back_color='white').save(image,format='PNG')
            z.writestr(f'table-{row["table"]}.png',image.getvalue())
    return buf.getvalue()
