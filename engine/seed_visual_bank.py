from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw, ImageFilter

SIZE = 512
ROOT = Path(__file__).resolve().parent.parent / "visual_bank"
ASSETS = ROOT / "assets"


def _canvas(alpha: bool = True, color=(0, 0, 0, 0)) -> Image.Image:
    return Image.new("RGBA" if alpha else "RGB", (SIZE, SIZE), color)


def _save(img: Image.Image, rel: str) -> str:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PNG")
    return rel.replace("\\", "/")


def _bg_plain(draw: ImageDraw.ImageDraw):
    draw.rectangle((0, 0, SIZE, SIZE), fill=(242, 247, 252))
    draw.ellipse((330, 45, 520, 235), fill=(228, 238, 249))
    draw.ellipse((-70, 330, 180, 580), fill=(235, 244, 250))


def _bg_forest(draw: ImageDraw.ImageDraw):
    draw.rectangle((0, 0, SIZE, 300), fill=(180, 225, 245))
    draw.rectangle((0, 300, SIZE, SIZE), fill=(136, 190, 92))
    draw.ellipse((360, 45, 430, 115), fill=(255, 232, 126))
    for x, h in [(35, 230), (105, 200), (405, 220), (455, 190)]:
        draw.rectangle((x + 23, 300-h//2, x + 43, 390), fill=(116, 79, 46))
        draw.ellipse((x-15, 95 if h > 210 else 125, x+85, 260), fill=(54, 139, 75))
        draw.ellipse((x-30, 155, x+100, 290), fill=(66, 157, 82))
    draw.polygon([(0, 370), (130, 345), (260, 385), (390, 350), (512, 390), (512,512), (0,512)], fill=(118, 174, 81))


def _bg_kitchen(draw: ImageDraw.ImageDraw):
    draw.rectangle((0, 0, SIZE, 330), fill=(245, 239, 226))
    draw.rectangle((0, 330, SIZE, SIZE), fill=(196, 166, 125))
    draw.rectangle((25, 70, 180, 225), fill=(215, 225, 231), outline=(130, 151, 165), width=5)
    draw.line((102, 70, 102, 225), fill=(130,151,165), width=4)
    draw.line((25, 148, 180, 148), fill=(130,151,165), width=4)
    draw.rectangle((250, 90, 470, 250), fill=(220, 188, 137))
    for x in [260, 365]:
        draw.rectangle((x, 105, x+95, 230), fill=(236, 207, 163), outline=(171, 139, 95), width=3)
    draw.rectangle((0, 280, SIZE, 335), fill=(205, 205, 196))


def _bg_bedroom(draw: ImageDraw.ImageDraw):
    draw.rectangle((0,0,SIZE,365), fill=(227, 221, 247))
    draw.rectangle((0,365,SIZE,SIZE), fill=(190,154,116))
    draw.rectangle((300,70,465,210), fill=(191,225,247), outline=(130,135,170), width=5)
    draw.line((382,70,382,210), fill=(130,135,170), width=4)
    draw.line((300,140,465,140), fill=(130,135,170), width=4)
    draw.rectangle((35,260,275,410), fill=(247,247,250), outline=(159,149,170), width=4)
    draw.rectangle((35,235,275,285), fill=(192,129,170))
    draw.rectangle((52,245,115,278), fill=(255,255,255))


def _bg_school(draw: ImageDraw.ImageDraw):
    draw.rectangle((0,0,SIZE,360), fill=(244,238,214))
    draw.rectangle((0,360,SIZE,SIZE), fill=(184,144,95))
    draw.rectangle((65,60,445,250), fill=(57,105,82), outline=(92,65,43), width=12)
    draw.rectangle((270,305,455,345), fill=(181,128,77))
    draw.rectangle((295,345,315,470), fill=(131,91,62))
    draw.rectangle((410,345,430,470), fill=(131,91,62))


def _bg_city(draw: ImageDraw.ImageDraw):
    draw.rectangle((0,0,SIZE,300), fill=(173,220,245))
    draw.rectangle((0,300,SIZE,SIZE), fill=(183,190,197))
    buildings=[(20,150,110,330,(229,161,118)),(120,90,225,330,(139,174,205)),(330,125,480,330,(224,197,122))]
    for x1,y1,x2,y2,c in buildings:
        draw.rectangle((x1,y1,x2,y2), fill=c)
        for x in range(x1+18,x2-12,28):
            for y in range(y1+22,y2-25,42):
                draw.rectangle((x,y,x+13,y+18), fill=(244,235,170))
    draw.rectangle((0,350,SIZE,390), fill=(100,105,112))
    draw.line((0,370,SIZE,370), fill=(240,224,150), width=4)


def _bg_playground(draw: ImageDraw.ImageDraw):
    draw.rectangle((0,0,SIZE,290), fill=(185,229,249))
    draw.rectangle((0,290,SIZE,SIZE), fill=(126,190,95))
    draw.rectangle((310,185,330,385), fill=(92,112,140))
    draw.rectangle((420,185,440,385), fill=(92,112,140))
    draw.line((320,190,320,315), fill=(80,80,80), width=3)
    draw.line((430,190,430,315), fill=(80,80,80), width=3)
    draw.rectangle((292,315,346,335), fill=(226,88,76))
    draw.rectangle((402,315,456,335), fill=(226,88,76))
    draw.polygon([(55,350),(175,350),(145,260),(85,260)], fill=(241,163,65))
    draw.rectangle((92,215,142,260), fill=(89,153,218))


def _bg_sports(draw: ImageDraw.ImageDraw):
    draw.rectangle((0,0,SIZE,270), fill=(177,224,247))
    draw.rectangle((0,270,SIZE,SIZE), fill=(82,169,82))
    draw.ellipse((90,240,430,500), outline=(240,240,240), width=6)
    draw.line((260,270,260,512), fill=(240,240,240), width=5)
    draw.rectangle((15,200,497,260), fill=(150,155,172))
    for x in range(25,490,35):
        draw.ellipse((x,215,x+15,230), fill=(242,188,95))


def _bg_beach(draw: ImageDraw.ImageDraw):
    draw.rectangle((0,0,SIZE,250), fill=(173,224,250))
    draw.rectangle((0,250,SIZE,360), fill=(95,185,215))
    draw.rectangle((0,360,SIZE,SIZE), fill=(240,211,139))
    draw.ellipse((385,45,455,115), fill=(255,226,97))
    draw.polygon([(40,390),(155,390),(97,285)], fill=(242,115,77))
    draw.rectangle((91,285,104,475), fill=(133,96,64))


def _bg_space(draw: ImageDraw.ImageDraw):
    draw.rectangle((0,0,SIZE,SIZE), fill=(34,32,72))
    stars=[(35,60),(95,110),(155,42),(220,95),(280,50),(350,130),(440,70),(470,190),(70,230),(180,200),(300,230),(400,275)]
    for x,y in stars:
        draw.ellipse((x-2,y-2,x+2,y+2), fill=(248,244,206))
    draw.ellipse((330,300,500,470), fill=(115,98,165))
    draw.ellipse((370,325,465,420), fill=(135,117,184))


def make_backgrounds():
    specs = [
        ("plain_light", ["claro","simples","quiz","fundo claro"], _bg_plain),
        ("forest_day", ["floresta","mata","árvores","dia"], _bg_forest),
        ("kitchen", ["cozinha","casa","comida"], _bg_kitchen),
        ("bedroom", ["quarto","cama","casa"], _bg_bedroom),
        ("school", ["escola","sala de aula","quadro"], _bg_school),
        ("city", ["cidade","rua","prédios"], _bg_city),
        ("playground", ["parque","playground","brinquedos"], _bg_playground),
        ("sports_field", ["esporte","campo","futebol"], _bg_sports),
        ("beach", ["praia","mar","areia"], _bg_beach),
        ("space", ["espaço","planeta","estrelas"], _bg_space),
    ]
    out=[]
    for name,tags,fn in specs:
        img=_canvas(False,(255,255,255))
        d=ImageDraw.Draw(img)
        fn(d)
        rel=_save(img.convert("RGB"),f"assets/backgrounds/{name}.png")
        out.append({"id":f"bg_{name}","category":"background","file":rel,"tags":tags,"style":["2d","limpo"],"free_space":"right" if name in {"forest_day","school"} else "center"})
    return out


def make_pose_pointing_right():
    img=_canvas()
    d=ImageDraw.Draw(img)
    skin=(224,169,125,255)
    # neck + arms + hands + shoes
    d.rounded_rectangle((170,180,206,270), radius=14, fill=skin)
    d.line((188,238,265,270), fill=skin, width=28)
    d.line((263,270,342,245), fill=skin, width=24)
    d.ellipse((334,231,366,260), fill=skin)
    d.polygon([(360,243),(395,238),(366,250)], fill=skin)
    d.line((190,245,145,300), fill=skin, width=24)
    d.ellipse((128,292,158,320), fill=skin)
    d.ellipse((165,420,215,446), fill=(61,68,82,255))
    d.ellipse((228,420,278,446), fill=(61,68,82,255))
    return img, {"head":[150,92,118,118],"object_target":[350,280,135,135],"character_box":[110,85,250,370]}


def make_pose_standing_center():
    img=_canvas(); d=ImageDraw.Draw(img); skin=(224,169,125,255)
    d.rounded_rectangle((239,178,273,250), radius=12, fill=skin)
    d.line((238,240,190,320), fill=skin, width=24)
    d.ellipse((175,310,205,340), fill=skin)
    d.line((274,240,322,320), fill=skin, width=24)
    d.ellipse((307,310,337,340), fill=skin)
    d.ellipse((213,420,253,445), fill=(61,68,82,255))
    d.ellipse((265,420,305,445), fill=(61,68,82,255))
    return img, {"head":[197,82,118,118],"object_target":[330,280,140,140],"character_box":[165,80,180,365]}


def make_pose_holding_left():
    img=_canvas(); d=ImageDraw.Draw(img); skin=(224,169,125,255)
    d.rounded_rectangle((285,180,319,250), radius=12, fill=skin)
    d.line((290,240,240,300), fill=skin, width=24)
    d.line((318,240,365,295), fill=skin, width=24)
    d.ellipse((226,287,256,317), fill=skin)
    d.ellipse((350,283,380,313), fill=skin)
    d.ellipse((260,420,300,445), fill=(61,68,82,255))
    d.ellipse((310,420,350,445), fill=(61,68,82,255))
    return img, {"head":[257,85,118,118],"object_target":[215,265,120,120],"character_box":[205,85,195,360]}


def make_poses():
    specs=[("pointing_right",["apontando","aponta","indicando","direita"],make_pose_pointing_right),
           ("standing_center",["em pé","parado","frente","central"],make_pose_standing_center),
           ("holding_left",["segurando","segura","carregando"],make_pose_holding_left)]
    out=[]
    for name,tags,fn in specs:
        img,anchors=fn(); rel=_save(img,f"assets/poses/{name}.png")
        out.append({"id":f"pose_{name}","category":"pose","file":rel,"tags":tags,"anchors":anchors,"layer":20})
    return out


def make_face(expression: str):
    img=Image.new("RGBA",(160,160),(0,0,0,0)); d=ImageDraw.Draw(img)
    skin=(233,183,139,255)
    hair=(49,37,33,255)
    d.ellipse((20,18,140,145), fill=skin, outline=(119,80,60,255), width=3)
    d.pieslice((15,4,145,90),180,360,fill=hair)
    d.polygon([(30,50),(45,15),(60,50),(78,8),(91,48),(112,15),(125,55)],fill=hair)
    # eyes
    if expression == "happy":
        d.arc((45,65,70,88),0,180,fill=(40,40,45,255),width=4)
        d.arc((90,65,115,88),0,180,fill=(40,40,45,255),width=4)
        d.arc((58,88,106,125),0,180,fill=(125,50,47,255),width=5)
    elif expression == "surprised":
        d.ellipse((48,66,66,87),fill=(255,255,255,255),outline=(50,50,55,255),width=2)
        d.ellipse((94,66,112,87),fill=(255,255,255,255),outline=(50,50,55,255),width=2)
        d.ellipse((55,72,61,80),fill=(35,35,40,255)); d.ellipse((101,72,107,80),fill=(35,35,40,255))
        d.ellipse((70,99,92,126),fill=(102,44,40,255))
    elif expression == "angry":
        d.line((45,68,69,76),fill=(45,40,40,255),width=4); d.line((92,76,116,68),fill=(45,40,40,255),width=4)
        d.ellipse((52,78,64,91),fill=(35,35,40,255)); d.ellipse((98,78,110,91),fill=(35,35,40,255))
        d.arc((66,103,96,124),180,360,fill=(105,45,45,255),width=4)
    else:
        d.ellipse((52,72,64,84),fill=(35,35,40,255)); d.ellipse((98,72,110,84),fill=(35,35,40,255))
        d.line((70,108,92,108),fill=(105,65,60,255),width=4)
    return img


def make_faces():
    specs=[("neutral",["neutro","normal"]),("happy",["feliz","sorrindo","alegre"]),("surprised",["surpreso","assustado","espantado"]),("angry",["bravo","irritado","raiva"])]
    out=[]
    for name,tags in specs:
        rel=_save(make_face(name),f"assets/faces/{name}.png")
        out.append({"id":f"face_{name}","category":"face","file":rel,"tags":tags,"anchor":"head","layer":40})
    return out


def _draw_outfit(pose_name: str, outfit: str):
    img=_canvas(); d=ImageDraw.Draw(img)
    if pose_name=="pointing_right":
        torso=(150,205,260,350); leg1=(160,335,205,428); leg2=(216,335,262,428)
        sleeve1=[(155,220),(188,232),(160,307),(132,286)]
        sleeve2=[(236,215),(265,228),(328,258),(310,282)]
    elif pose_name=="standing_center":
        torso=(205,205,307,345); leg1=(215,335,255,428); leg2=(266,335,306,428)
        sleeve1=[(210,222),(232,238),(204,315),(178,299)]
        sleeve2=[(282,238),(304,222),(334,299),(308,315)]
    else:
        torso=(265,205,370,350); leg1=(270,338,310,428); leg2=(320,338,360,428)
        sleeve1=[(270,220),(294,235),(250,302),(228,282)]
        sleeve2=[(346,235),(368,220),(382,280),(360,300)]
    if outfit=="ninja":
        c=(36,47,65,255); c2=(58,73,96,255)
        d.rounded_rectangle(torso,radius=20,fill=c,outline=(20,25,35,255),width=3)
        d.polygon(sleeve1,fill=c); d.polygon(sleeve2,fill=c)
        d.rectangle(leg1,fill=c2); d.rectangle(leg2,fill=c2)
        # belt
        d.rectangle((torso[0]+5,torso[3]-35,torso[2]-5,torso[3]-24),fill=(150,46,50,255))
    elif outfit=="chef":
        c=(245,246,248,255); c2=(45,55,72,255)
        d.rounded_rectangle(torso,radius=18,fill=c,outline=(155,160,170,255),width=3)
        d.polygon(sleeve1,fill=c); d.polygon(sleeve2,fill=c)
        d.rectangle(leg1,fill=c2); d.rectangle(leg2,fill=c2)
        d.line((torso[0]+20,torso[1]+10,torso[0]+20,torso[3]-15),fill=(110,115,125,255),width=3)
    else:
        c=(64,132,201,255); c2=(61,71,101,255)
        d.rounded_rectangle(torso,radius=18,fill=c,outline=(45,91,137,255),width=3)
        d.polygon(sleeve1,fill=c); d.polygon(sleeve2,fill=c)
        d.rectangle(leg1,fill=c2); d.rectangle(leg2,fill=c2)
    return img


def make_outfits():
    out=[]
    tags={"ninja":["ninja","shinobi","preto"],"chef":["chef","cozinheiro","cozinha"],"casual":["casual","camiseta","roupa comum"]}
    for pose in ["pointing_right","standing_center","holding_left"]:
        for outfit in ["ninja","chef","casual"]:
            rel=_save(_draw_outfit(pose,outfit),f"assets/outfits/{outfit}_{pose}.png")
            out.append({"id":f"outfit_{outfit}_{pose}","category":"outfit","file":rel,"tags":tags[outfit]+[pose],"compatible_pose":f"pose_{pose}","layer":30})
    return out


def _object_canvas(draw_fn: Callable[[ImageDraw.ImageDraw],None]):
    img=Image.new("RGBA",(200,200),(0,0,0,0)); d=ImageDraw.Draw(img); draw_fn(d); return img


def obj_fork(d):
    metal=(170,177,185,255); outline=(100,105,112,255)
    d.rounded_rectangle((92,65,108,178),radius=7,fill=metal,outline=outline,width=2)
    for x in [72,84,96,108,120]: d.rounded_rectangle((x,22,x+8,86),radius=4,fill=metal,outline=outline,width=1)
    d.rectangle((76,58,124,80),fill=metal)

def obj_spoon(d):
    metal=(175,181,190,255); outline=(100,105,112,255)
    d.ellipse((58,18,142,104),fill=metal,outline=outline,width=3); d.rounded_rectangle((92,88,108,180),radius=7,fill=metal,outline=outline,width=2)

def obj_knife(d):
    d.polygon([(45,45),(130,58),(125,92),(50,90)],fill=(185,190,198,255),outline=(105,110,118,255))
    d.rounded_rectangle((120,65,172,92),radius=9,fill=(95,62,43,255))

def obj_box(d):
    d.polygon([(42,70),(100,42),(158,70),(100,102)],fill=(201,149,78,255),outline=(120,85,45,255))
    d.polygon([(42,70),(100,102),(100,164),(42,130)],fill=(181,125,60,255),outline=(120,85,45,255))
    d.polygon([(100,102),(158,70),(158,130),(100,164)],fill=(222,165,87,255),outline=(120,85,45,255))

def obj_ball(d):
    d.ellipse((34,34,166,166),fill=(244,244,244,255),outline=(45,45,50,255),width=4)
    d.polygon([(100,62),(124,80),(116,108),(84,108),(76,80)],fill=(45,45,50,255))
    for p in [(50,75),(135,70),(135,127),(60,135)]: d.ellipse((p[0]-11,p[1]-11,p[0]+11,p[1]+11),fill=(45,45,50,255))

def obj_apple(d):
    d.ellipse((44,52,108,155),fill=(222,53,62,255)); d.ellipse((91,52,155,155),fill=(231,62,66,255))
    d.rectangle((96,28,104,64),fill=(95,64,39,255)); d.ellipse((104,28,139,50),fill=(72,148,68,255))

def obj_car(d):
    d.rounded_rectangle((28,80,170,138),radius=18,fill=(58,129,211,255),outline=(35,74,120,255),width=3)
    d.polygon([(62,80),(82,50),(130,50),(151,80)],fill=(67,143,219,255),outline=(35,74,120,255))
    d.rectangle((86,57,108,78),fill=(186,225,242,255)); d.rectangle((112,57,132,78),fill=(186,225,242,255))
    d.ellipse((48,125,82,159),fill=(45,48,55,255)); d.ellipse((126,125,160,159),fill=(45,48,55,255))

def obj_book(d):
    d.polygon([(36,48),(98,60),(98,160),(36,148)],fill=(223,90,72,255),outline=(120,55,45,255))
    d.polygon([(102,60),(164,48),(164,148),(102,160)],fill=(237,113,85,255),outline=(120,55,45,255))
    d.line((100,60,100,160),fill=(255,235,215,255),width=4)

def obj_toy(d):
    d.rounded_rectangle((45,70,155,145),radius=18,fill=(245,178,55,255),outline=(150,95,25,255),width=3)
    d.ellipse((65,45,98,78),fill=(76,154,222,255)); d.ellipse((105,45,138,78),fill=(76,154,222,255))
    d.ellipse((60,132,88,160),fill=(65,68,75,255)); d.ellipse((118,132,146,160),fill=(65,68,75,255))

def obj_banana(d):
    d.arc((35,30,170,160),20,150,fill=(242,210,62,255),width=34)
    d.arc((45,40,160,150),20,150,fill=(255,227,80,255),width=18)


def make_objects():
    specs=[("fork",["garfo","comer","talher"],obj_fork),("spoon",["colher","comer","talher"],obj_spoon),("knife",["faca","cortar","talher"],obj_knife),("box",["caixa","pacote"],obj_box),("ball",["bola","futebol","esporte"],obj_ball),("apple",["maçã","maca","fruta","alimento"],obj_apple),("car",["carro","veículo","veiculo"],obj_car),("book",["livro","escola","leitura"],obj_book),("toy",["brinquedo","carrinho","brincar"],obj_toy),("banana",["banana","fruta","alimento"],obj_banana)]
    out=[]
    for name,tags,fn in specs:
        rel=_save(_object_canvas(fn),f"assets/objects/{name}.png")
        out.append({"id":f"obj_{name}","category":"object","file":rel,"tags":tags,"layer":50})
    return out


def build_bank(force: bool = False) -> dict:
    metadata_path = ROOT / "metadata.json"
    if metadata_path.exists() and not force:
        return json.loads(metadata_path.read_text(encoding="utf-8"))

    ROOT.mkdir(parents=True,exist_ok=True)
    assets=[]
    assets += make_backgrounds()
    assets += make_poses()
    assets += make_faces()
    assets += make_outfits()
    assets += make_objects()

    data={
        "version":"0.1",
        "description":"Banco visual manual inicial do Composer Engine. Assets demo substituíveis por PNGs reais mantendo os metadados.",
        "canvas_base":[SIZE,SIZE],
        "assets":assets,
        "license_notes":"Assets demo gerados proceduralmente pelo próprio MVP. Para assets externos, registrar origem/licença nos metadados.",
    }
    metadata_path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    return data


if __name__ == "__main__":
    data=build_bank(force=True)
    print(f"Banco criado: {len(data['assets'])} assets em {ROOT}")
