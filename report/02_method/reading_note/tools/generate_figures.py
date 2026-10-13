"""Generate original educational diagrams; no network or external image inputs."""
from pathlib import Path
import math
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'assets'
OUT.mkdir(exist_ok=True)
FONT = Path('C:/Windows/Fonts/msyh.ttc')
BOLD = Path('C:/Windows/Fonts/msyhbd.ttc')
INK = '#18304A'
MUTED = '#596C80'
BLUE = '#2377B8'
GREEN = '#14866E'
PURPLE = '#7961B3'
ORANGE = '#C77022'
GRAY = '#A4AFBB'

class Figure:
    def __init__(self, title, subtitle, height=1000):
        self.im = Image.new('RGB', (1800, height), '#F7F9FC')
        self.d = ImageDraw.Draw(self.im)
        self.text((70, 45), title, 45, bold=True)
        self.text((72, 112), subtitle, 25, MUTED)
        self.height = height

    def text(self, xy, text, size=28, color=INK, bold=False, anchor=None):
        f = ImageFont.truetype(str(BOLD if bold else FONT), size)
        self.d.multiline_text(xy, text, font=f, fill=color, spacing=10, anchor=anchor)

    def box(self, rect, title, body='', fill='#FFFFFF', edge='#D9E1EB', titlecolor=INK, size=28):
        x0,y0,x1,y1=rect
        self.d.rounded_rectangle(rect, radius=18, fill=fill, outline=edge, width=2)
        self.text((x0+23,y0+20),title,size,titlecolor,True)
        if body: self.text((x0+23,y0+65),body,25,MUTED)

    def arrow(self, points, color=BLUE, width=5, dashed=False):
        if dashed:
            for a,b in zip(points, points[1:]):
                dx,dy=b[0]-a[0],b[1]-a[1]
                n=max(1,int(math.hypot(dx,dy)/16))
                for k in range(0,n,2):
                    s=k/n; e=min((k+1)/n,1)
                    self.d.line((a[0]+dx*s,a[1]+dy*s,a[0]+dx*e,a[1]+dy*e),fill=color,width=width)
        else: self.d.line(points,fill=color,width=width,joint='curve')
        a,b=points[-2:]; ang=math.atan2(b[1]-a[1],b[0]-a[0])
        self.d.polygon([b,(b[0]-17*math.cos(ang-.45),b[1]-17*math.sin(ang-.45)),(b[0]-17*math.cos(ang+.45),b[1]-17*math.sin(ang+.45))],fill=color)

    def save(self,name,footer):
        self.text((72,self.height-58),footer,22,MUTED)
        self.im.save(OUT/name,optimize=True)

f=Figure('01  从深度图到飞行动作：在线规划链路','一次前向传播同时预测候选参数与评分；图中维度采用 NCHW，宽 × 高为 160 × 96。',1050)
f.box((70,200,460,365),'深度图 D','B × 1 × 96 × 160\n卷积提取空间特征',fill='#EAF3FC',titlecolor=BLUE)
f.box((70,410,460,610),'运动状态与目标','速度 v、加速度 a、方向 ĝ\n9 维；分别旋转到各基元系',fill='#EAF3FC',titlecolor=BLUE)
f.box((570,245,1040,545),'共享网络','ResNet-18 特征 + 局部状态\n共享 1 × 1 卷积预测头\n输出 B × 10 × 3 × 5',fill='#EDF0FC',titlecolor=PURPLE)
f.arrow([(460,283),(515,283),(515,330),(570,330)])
f.arrow([(460,505),(515,505),(515,460),(570,460)])
f.box((1160,205,1730,365),'15 组候选参数','每组 9 个：位置偏移 + 终端速度/加速度',fill='#EAF5F1',titlecolor=GREEN,size=29)
f.box((1160,410,1730,545),'15 个预测评分','每组 1 个：预测负代价 ŝ ≈ −J',fill='#FFF3E5',titlecolor=ORANGE)
f.arrow([(1040,330),(1100,330),(1100,285),(1160,285)])
f.arrow([(1040,460),(1160,460)])
f.box((1170,660,1720,830),'选择评分最高的候选','argmax ŝ → 解码终端状态 q*\n初始状态 + q* → 五次多项式',fill='#EAF5F1',titlecolor=GREEN)
f.arrow([(1435,365),(1770,365),(1770,630),(1580,630),(1580,660)],GREEN)
f.arrow([(1435,545),(1435,660)],ORANGE)
f.box((605,660,1045,830),'2 s 连续参考轨迹','位置、速度、加速度、航向\n以 50 Hz 提供参考状态')
f.arrow([(1170,745),(1045,745)],GREEN)
f.box((70,660,475,830),'几何控制器与执行器','跟踪参考轨迹\n产生实际飞行动作')
f.arrow([(605,745),(475,745)],GREEN)
f.text((80,890),'每 1/15 s 重新读取观测并规划；2 s 轨迹通常只执行开头约 1/30。',30,BLUE,True)
f.save('01_online_pipeline.png','依据原文 Fig. 3、式 (3)–(9) 重绘。此图描述 2024 年论文的在线流程。')

f=Figure('02  固定的是基元锚点，变化的是网络预测','左：相机视场内的 5 × 3 方向布局。右：同一横向切片中，预测终端状态改变曲线。',1000)
f.box((60,185,815,810),'15 个空间位置，共享同一预测头',fill='#FFFFFF')
for row in range(3):
    for col in range(5):
        x=110+col*132; y=335+row*135
        f.d.rounded_rectangle((x,y,x+108,y+105),12,fill='#EEF2F7',outline='#D6DFE9',width=2)
        f.d.ellipse((x+45,y+36,x+61,y+52),fill=GRAY)
        dx=[-19,10,15,-14,13][col]; dy=[14,-12,9][row]
        f.arrow([(x+53,y+44),(x+53+dx,y+44+dy)],GREEN,width=3)
        f.text((x+35,y+70),str(row*5+col+1),19,MUTED)
f.text((110,255),'灰点：预设锚点    绿箭头：本次预测的偏移',23,MUTED)
f.text((110,765),'候选对应不同区域，邻域允许适度重叠。',24,MUTED)
f.box((875,185,1740,810),'连续曲线由完整边界条件决定',fill='#FFFFFF')
origin=(945,710)
for i,end_y in enumerate([310,390,470,550,630]):
    end=(1660,end_y)
    f.arrow([origin,end],GRAY,width=2,dashed=True)
    f.d.ellipse((end[0]-7,end[1]-7,end[0]+7,end[1]+7),fill=GRAY)
    pts=[]
    delta=[-25,38,-42,22,-28][i]
    for k in range(101):
        u=k/100; smooth=10*u**3-15*u**4+6*u**5
        pts.append((origin[0]+(end[0]-origin[0]-35)*u,origin[1]+(end_y+delta-origin[1])*smooth))
    color=GREEN if i==2 else '#64ADD3'
    f.d.line(pts,fill=color,width=7 if i==2 else 4)
    f.d.ellipse((pts[-1][0]-8,pts[-1][1]-8,pts[-1][0]+8,pts[-1][1]+8),fill=color)
f.text((922,260),'虚线：锚点方向    曲线：示意候选',23,MUTED)
f.text((925,745),'终点位置、终端速度、终端加速度共同塑形。',23,MUTED)
f.box((70,845,1730,920),'预设：方向、半径、偏移上限。    每轮预测：实际偏移、终端导数、评分。',fill='#EAF5F1',titlecolor=GREEN,size=29)
f.save('02_primitive_anchors.png','教学示意：箭头、曲线及被强调的候选均为构造示例，并非论文数据或模型预测。')

f=Figure('03  Guidance Learning：同一代价，两种训练信号','蓝色实线表示前向数据；橙色虚线表示轨迹参数梯度；紫色虚线表示评分损失梯度。',1190)
f.box((70,195,500,365),'网络可见观测','深度图 + v + a + ĝ',fill='#EAF3FC',titlecolor=BLUE)
f.box((670,195,1160,365),'共享网络 f(w)','共享特征和权重',fill='#EDF0FC',titlecolor=PURPLE)
f.arrow([(500,280),(670,280)])
f.box((70,465,500,645),'轨迹输出 y（9 维/候选）','解码 → q = [pT, vT, aT]\n求解多项式 → 采样轨迹',fill='#EAF5F1',titlecolor=GREEN)
f.box((1270,465,1730,645),'评分输出 ŝ（1 维/候选）','当前候选的预测负代价',fill='#FFF3E5',titlecolor=ORANGE)
f.arrow([(760,365),(760,410),(290,410),(290,465)])
f.arrow([(1080,365),(1080,410),(1500,410),(1500,465)])
f.box((650,730,1160,960),'外部轨迹代价评价器','完整 ESDF + 训练位姿 + 轨迹\n计算 J = λs Js + λo Jo + λg Jg\n同时计算 ∂J/∂q',fill='#F1ECFA',titlecolor=PURPLE)
f.arrow([(290,645),(290,820),(650,820)])
f.box((1270,790,1730,960),'评分回归损失','Smooth L1(ŝ, target = −J)\n当前 −J 作为监督目标',fill='#FFF3E5',titlecolor=ORANGE)
f.arrow([(1500,645),(1500,790)])
f.arrow([(1160,870),(1270,870)])
f.arrow([(650,910),(555,910),(555,570),(500,570)],ORANGE,dashed=True)
f.text((80,885),'∂J/∂q → ∂J/∂y',26,ORANGE,True)
f.arrow([(115,465),(115,405),(590,405),(590,225),(670,225)],ORANGE,dashed=True)
f.arrow([(1730,870),(1760,870),(1760,335),(1160,335)],PURPLE,dashed=True)
f.text((1240,195),'两路梯度最终更新共享权重',24,PURPLE,True)
f.text((90,1030),'轨迹参数的学习梯度来自外部代价；评分输出学习估计该代价。',30,INK,True)
f.save('03_training_gradients.png','依据式 (10)–(21) 重绘。为清晰起见省略批次维度、候选筛选掩码与聚合系数。')

f=Figure('04  评分为什么能训练：一个完整的数值例子','教学设定：λs = λo = λg = 1；Smooth L1 的 β = 1；对两个候选取平均损失。',1050)
f.box((70,190,835,465),'候选 A：离障碍物更近','Js = 0.10    Jo = 0.70    Jg = 0.20\nJ = 1.00 → 目标评分 −1.00\n当前预测 −0.20；误差 +0.80',fill='#FFF3E5',titlecolor=ORANGE)
f.box((965,190,1730,465),'候选 B：总规划代价更低','Js = 0.20    Jo = 0.05    Jg = 0.15\nJ = 0.40 → 目标评分 −0.40\n当前预测 −0.90；误差 −0.50',fill='#EAF5F1',titlecolor=GREEN)
x=lambda s: int(205+(s+1.2)/1.2*1390)
for y,label,pred,target in [(565,'A',-.2,-1.0),(715,'B',-.9,-.4)]:
    f.text((100,y-17),label,34,INK,True)
    f.d.line((x(-1.2),y,x(0),y),fill='#CDD7E2',width=3)
    f.arrow([(x(pred),y),(x(target),y)],ORANGE if label=='A' else GREEN,width=6)
    f.d.ellipse((x(pred)-10,y-10,x(pred)+10,y+10),fill=BLUE)
    f.d.rounded_rectangle((x(target)-11,y-11,x(target)+11,y+11),3,fill=GREEN)
    f.text((x(pred),y-55),f'预测 {pred:.2f}',23,BLUE,anchor='mm')
    f.text((x(target),y+45),f'目标 {target:.2f}',23,GREEN,anchor='mm')
f.box((70,830,1730,955),'平均损失 = (0.320 + 0.125) / 2 = 0.2225','对平均损失求导：∂L/∂ŝA = +0.40，∂L/∂ŝB = −0.25；真实训练更新共享网络权重。',fill='#EAF3FC',titlecolor=BLUE,size=30)
f.save('04_score_learning.png','所有数值为教学示例。箭头表示输出应靠近目标的方向，不代表网络单步更新的精确位移。')
print('Created 4 figures in', OUT)
