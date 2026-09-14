from __future__ import annotations
import base64, io, re
from contextlib import closing
from PIL import Image
from .db import webapp_conn
from .secret_store import decrypt_secret
from .textbook_browser import capture_pages

def page_numbers(text: str) -> list[int]:
    pages=[]
    for start,end in re.findall(r"(?:S(?:eite)?\.?)\s*(\d{1,4})(?:\s*[-–]\s*(\d{1,4}))?",text,re.I):
        a,b=int(start),int(end or start)
        if a<=b<=a+10: pages.extend(range(a,b+1))
    return list(dict.fromkeys(pages))[:6]

def _join(blobs):
    images=[Image.open(io.BytesIO(x)).convert("RGB") for x in blobs]
    canvas=Image.new("RGB",(max(x.width for x in images),sum(x.height for x in images)),"white");pos=0
    for image in images: canvas.paste(image,(0,pos));pos+=image.height
    out=io.BytesIO();canvas.save(out,"JPEG",quality=88);return out.getvalue()

async def homework_page_images(account_id:int,subject:str,task_text:str):
    pages=page_numbers(task_text)
    if not pages:return [],{"status":"no_pages"}
    with closing(webapp_conn()) as c:
        book=c.execute("SELECT * FROM digital_textbook_catalog WHERE account_id=? AND lower(subject_name)=lower(?) LIMIT 1",(account_id,subject)).fetchone()
        credentials=c.execute("SELECT * FROM digital_textbook_credentials WHERE account_id=?",(account_id,)).fetchone()
    if not book or not credentials:return [],{"status":"not_configured","pages":pages}
    password=decrypt_secret(credentials["password_ciphertext"])
    try: captured=await capture_pages(credentials["portal_url"],credentials["username"],password,book["title"],pages)
    finally: password=""
    parts=[]
    for i in range(0,min(len(captured),4),2):
        blob=_join([x[1] for x in captured[i:i+2]])
        parts.append({"type":"image_url","image_url":{"url":"data:image/jpeg;base64,"+base64.b64encode(blob).decode(),"detail":"high"}})
    return parts,{"status":"loaded","book":book["title"],"pages":pages}
