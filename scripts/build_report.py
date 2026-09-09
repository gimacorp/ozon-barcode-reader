"""Сборка русского отчёта и иллюстраций из фактических результатов эксперимента."""
from pathlib import Path
import json
import re
import sys
import html
import os
os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parents[1]/".cache/matplotlib"))
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak,Image,KeepTogether
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_LEFT

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.report_content import make_pages, SOURCES

BLUE="#005BFF"; DARK="#122441"; CYAN="#00A6B8"


def figures(calc,benchmark):
    dest=ROOT/"docs/figures";dest.mkdir(parents=True,exist_ok=True)
    plt.rcParams.update({"font.family":"DejaVu Sans","font.size":10,"axes.spines.top":False,
                         "axes.spines.right":False,"axes.labelcolor":DARK,"text.color":DARK})
    fig,axes=plt.subplots(2,1,figsize=(10,7.7),gridspec_kw={"height_ratios":[1.3,1]},layout="constrained")
    ax=axes[0]
    for x,w in [(0,890),(910,2090)]:ax.add_patch(Rectangle((x,-30),w,30,color="#526783"))
    ax.add_patch(Rectangle((1415,0),600,400,fc="#EEDBC4",ec="#826A4F",lw=1.4))
    ax.text(1715,200,"Коробка\n600 × 400 мм",ha="center",va="center")
    for x,z,name in [(0,550,"Задний торец"),(2513,550,"Передний торец"),(650,1112,"Верх"),(900,-712,"Дно")]:
        ax.scatter(x,z,s=100,marker="s",color=BLUE,zorder=4)
        ax.text(x+35,z+45,name,fontsize=10)
    ax.plot([0,1256],[550,200],"--",color=CYAN)
    ax.plot([2513,1256],[550,200],"--",color=CYAN)
    ax.plot([650,650],[1112,400],"--",color=CYAN)
    ax.plot([900,900],[-712,0],"--",color=CYAN)
    ax.axvline(3000,color="#EF6C4D",lw=2)
    ax.text(2980,800,"Сортировка\nx = 3000",ha="right")
    ax.annotate("Движение 1 м/с",xy=(2300,1000),xytext=(1800,1000),arrowprops={"arrowstyle":"->","color":DARK})
    ax.set(xlim=(-160,3100),ylim=(-900,1320),xlabel="x, мм вдоль конвейера",ylabel="z, мм от ленты",title="Размещение по высоте и длине")
    ax.grid(alpha=.15)
    ax=axes[1]
    ax.add_patch(Rectangle((0,-325),3000,650,fc="#E7EDF6",ec="#526783"))
    ax.add_patch(Rectangle((1415,-200),600,400,fc="#EEDBC4",ec="#826A4F"))
    for y,name in [(-667,"Правая"),(667,"Левая")]:
        ax.scatter(750,y,marker="s",s=100,color=BLUE)
        ax.plot([750,750],[y,np.sign(y)*200],"--",color=CYAN)
        ax.text(820,y,name,va="center")
    ax.plot([890,890],[-325,325],color="#EF6C4D")
    ax.plot([910,910],[-325,325],color="#EF6C4D")
    ax.annotate("Зазор 20 мм для чтения дна",xy=(900,-100),xytext=(1450,-650),arrowprops={"arrowstyle":"->"})
    ax.set(xlim=(-160,3100),ylim=(-850,850),xlabel="x, мм",ylabel="y, мм от оси ленты",title="Вид сверху: ширина ленты 650 мм")
    ax.grid(alpha=.15)
    fig.savefig(dest/"layout.png",dpi=180);plt.close(fig)

    e=calc["engineering"]
    fig,ax=plt.subplots(figsize=(10,3.3),layout="constrained")
    left=0
    values=[.4,.05,e["budget_slack_s"],.25,.1]
    names=["Обработка\n400 мс","Доставка\n50 мс",f"Запас\n{e['budget_slack_s']*1000:.0f} мс","Резерв\n250 мс","ПЛК\n100 мс"]
    for val,name,color in zip(values,names,[BLUE,CYAN,"#B2D4FF","#DDE6F4","#EEDBC4"]):
        ax.barh(0,val,left=left,color=color,height=.5,edgecolor="white")
        if val < .08:
            ax.annotate(name,xy=(left+val/2,.24),xytext=(left+val/2,.37),ha="center",va="bottom",
                        fontsize=9,color=DARK,arrowprops={"arrowstyle":"-","color":DARK})
        else:
            ax.text(left+val/2,0,name,ha="center",va="center",fontsize=9,color="white" if color==BLUE else DARK)
        left+=val
    ax.set(xlim=(0,left),ylim=(-.55,.8),yticks=[],xlabel="Секунды после последнего наблюдения задней грани",title="Проектный бюджет: до сортировки остаётся 985 мс")
    fig.savefig(dest/"deadline.png",dpi=180);plt.close(fig)

    metrics=[m for m in benchmark["metrics"] if m["level"]=="all"]
    names=["Один кадр","Три кадра","Три кадра +\nобработка"]
    fig,axes=plt.subplots(1,2,figsize=(10,4.0),layout="constrained")
    x=np.arange(3)
    axes[0].bar(x-.17,[m["exact_set_rate"]*100 for m in metrics],width=.34,color=BLUE,label="Всё множество коробки")
    axes[0].bar(x+.17,[m["code_recall"]*100 for m in metrics],width=.34,color=CYAN,label="Полнота кодов")
    axes[0].set(ylim=(0,115),xticks=x,xticklabels=names,ylabel="%",title="60 синтетических коробок / 140 кодов")
    axes[0].legend(fontsize=8,loc="upper left")
    bars=axes[1].bar(x,[m["latency_p95_ms"] for m in metrics],color=[BLUE,CYAN,"#EF6C4D"])
    for b in bars:axes[1].text(b.get_x()+b.get_width()/2,b.get_height()+8,f"{b.get_height():.0f}",ha="center")
    axes[1].set(ylim=(0,max(m["latency_p95_ms"] for m in metrics)*1.22),xticks=x,xticklabels=names,ylabel="мс",title="95-й перцентиль декодирования")
    fig.savefig(dest/"benchmark.png",dpi=180);plt.close(fig)

    fig,ax=plt.subplots(figsize=(10,3.5),layout="constrained")
    xs=np.linspace(.15,.5,100)
    ax.plot(xs,xs*8192/700,label="Линейные камеры: поперёк ленты",lw=2,color=BLUE)
    ax.plot(xs,xs*calc["end_face_geometry"]["min_best_px_per_mm"],label="Торец: худшая точка модели",lw=2,color=CYAN)
    ax.axhline(3,color="#EF6C4D",ls="--",label="Проектная цель 3 пикселя/модуль")
    ax.axvline(.33,color="#526783",ls=":")
    ax.set(xlabel="Минимальный модуль кода X, мм",ylabel="Пикселей на модуль",ylim=(0,6.2))
    ax.legend(fontsize=9,loc="upper left");ax.grid(alpha=.15)
    fig.savefig(dest/"sampling.png",dpi=180);plt.close(fig)


def build():
    calc=json.loads((ROOT/"results/calculations.json").read_text())
    bench=json.loads((ROOT/"results/benchmark.json").read_text())
    figures(calc,bench)
    fontroot=Path(matplotlib.get_data_path())/"fonts/ttf"
    for name,file in [("DV","DejaVuSans.ttf"),("DV-B","DejaVuSans-Bold.ttf")]:
        pdfmetrics.registerFont(TTFont(name,str(fontroot/file)))
    pdfmetrics.registerFontFamily("DV",normal="DV",bold="DV-B",italic="DV",boldItalic="DV-B")
    styles={
        "title":ParagraphStyle("title",fontName="DV-B",fontSize=27,leading=33,textColor=colors.HexColor(DARK),spaceAfter=20),
        "h1":ParagraphStyle("h1",fontName="DV-B",fontSize=19,leading=24,textColor=colors.HexColor(DARK),spaceAfter=15),
        "h2":ParagraphStyle("h2",fontName="DV-B",fontSize=11,leading=15,textColor=colors.HexColor(BLUE),spaceBefore=10,spaceAfter=7),
        "p":ParagraphStyle("p",fontName="DV",fontSize=10,leading=14.7,textColor=colors.HexColor(DARK),spaceAfter=9),
        "small":ParagraphStyle("small",fontName="DV",fontSize=8.1,leading=11.7,textColor=colors.HexColor(DARK),spaceAfter=7),
        "cell":ParagraphStyle("cell",fontName="DV",fontSize=8.2,leading=11.5,textColor=colors.HexColor(DARK)),
    }
    pages=make_pages(calc,bench)
    story=[];markdown=["# Шестистороннее чтение штрихкодов\n\nКарим Гимадиев · CV, вариант 2 · 9 сентября 2026\n"]
    for i,page in enumerate(pages):
        if i:story.append(PageBreak())
        if i==0:story.extend([Spacer(1,34),Paragraph("ТЕСТОВОЕ ЗАДАНИЕ · OZON · CV / 02",styles["h2"]),Spacer(1,20)])
        story.append(Paragraph(page["title"],styles["title"] if i==0 else styles["h1"]))
        markdown.append("\n## "+page["title"]+"\n")
        for block in page["blocks"]:
            kind=block[0]
            if kind in ("p","h2","small"):
                story.append(Paragraph(block[1],styles[kind]))
                raw=re.sub(r'<link href="([^"]+)">([^<]+)</link>',r'[\2](\1)',block[1])
                raw=raw.replace("<b>","**").replace("</b>","**").replace("<br/>","\n")
                markdown.append(("### " if kind=="h2" else "")+raw+"\n")
            elif kind=="figure":
                path=ROOT/"docs/figures"/block[1]
                from PIL import Image as PILImage
                w,h=PILImage.open(path).size
                width=475;story.append(Image(str(path),width=width,height=width*h/w))
                story.append(Spacer(1,7));markdown.append(f"![{block[2]}](figures/{block[1]})\n")
            elif kind=="table":
                rows,widths=block[1],block[2]
                cells=[[Paragraph(str(s),styles["cell"]) for s in row] for row in rows]
                table=Table(cells,colWidths=widths,repeatRows=1,hAlign="LEFT")
                table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#E3EDFF")),
                    ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#F5F7FB")]),
                    ("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),8),
                    ("RIGHTPADDING",(0,0),(-1,-1),8),("TOPPADDING",(0,0),(-1,-1),8),
                    ("BOTTOMPADDING",(0,0),(-1,-1),8),("LINEBELOW",(0,0),(-1,0),.6,colors.HexColor(BLUE))]))
                story.extend([table,Spacer(1,10)])
                markdown.append("| "+" | ".join(map(str,rows[0]))+" |\n|"+" --- |"*len(rows[0]))
                markdown.extend("| "+" | ".join(map(str,row))+" |" for row in rows[1:]);markdown.append("\n")
    out=ROOT/"output/pdf/ozon_cv2_report_ru.pdf";out.parent.mkdir(parents=True,exist_ok=True)
    def footer(c,doc):
        c.setStrokeColor(colors.HexColor(BLUE));c.setLineWidth(2);c.line(48,798,547,798)
        c.setFont("DV",8);c.setFillColor(colors.HexColor("#62728A"))
        c.drawString(48,29,"КАРИМ ГИМАДИЕВ  /  OZON · CV, ВАРИАНТ 2")
        c.drawRightString(547,29,f"{doc.page}")
    doc=SimpleDocTemplate(str(out),pagesize=(595.28,841.89),leftMargin=54,rightMargin=54,
                          topMargin=60,bottomMargin=55,title="Шестистороннее чтение штрихкодов | Ozon CV-2",
                          author="Карим Гимадиев",subject="Инженерное решение и воспроизводимый прототип")
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    (ROOT/"docs/report.md").write_text("\n".join(markdown)+"\n",encoding="utf-8")
    print(out)


if __name__=="__main__":build()
