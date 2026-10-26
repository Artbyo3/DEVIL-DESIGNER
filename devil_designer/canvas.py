"""Viewport-local layout shared by drawing and input handling."""
from dataclasses import dataclass
import math

@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    w: float
    h: float
    def contains(self,x,y):
        return self.x <= x <= self.x+self.w and self.y <= y <= self.y+self.h

class Layout:
    def __init__(self,width,height,scale=1.0,full=False,left=0,right=0,top=0,bottom=0):
        self.scale = s = scale
        height = max(1,height-top-bottom)
        available = max(1,width-left-right)
        margin = min(12*s,available/20,height/20)
        width = available-margin*2
        if not full:
            width = min(width*.78,max(390*s,width*.60))
        self.panel = p = Rect(left+available-margin-width,bottom+margin,width,max(1,height-margin*2))
        self.header = Rect(p.x,p.y+p.h-54*s,p.w,54*s)
        self.toolbar = Rect(p.x,self.header.y-42*s,p.w,42*s)
        self.workflow = Rect(p.x,self.toolbar.y-36*s,p.w,36*s)
        self.footer = Rect(p.x,p.y,p.w,48*s)
        self.canvas = Rect(p.x+25*s,self.footer.y+self.footer.h,
                           max(1,p.w-25*s),max(1,p.h-205*s))
        self.ruler_top = Rect(self.canvas.x,self.canvas.y+self.canvas.h,self.canvas.w,25*s)
        self.buttons = {}
        x = p.x+12*s
        compact = p.w < 440*s
        specs = ([("SELECT","V",30),("POLYGON","P",30),("RECTANGLE","R",30),
                  ("SEW","Sew J",48),("SNAP","Snap",49),("FIT","Fit",36)] if compact else
                 [("SELECT","Select  V",77),("POLYGON","Polygon  P",86),
                  ("RECTANGLE","Rect  R",68),("SEW","Sew J",55),("SNAP","Snap",49),("FIT","Fit",36)])
        if p.w >= 310*s:
            specs += [("UNDO","<",26),("REDO",">",26)]
        factor = min(1,max(.1,(p.w-24*s)/(sum(item[2]+5 for item in specs)*s)))
        for name,label,units in specs:
            self.buttons[name] = (Rect(x,self.toolbar.y+7*s,units*s*factor,28*s),label)
            x += (units+5)*s*factor
        flow = [("BUILD","Build 3D",70),("ARRANGE","Arrange",62),("SIMULATE","Simulate",65),
                ("STOP","Stop",39),("RESET","Reset",44),("KEEP","Keep mesh",74)]
        factor = min(1,max(.1,(p.w-24*s)/(sum(item[2]+5 for item in flow)*s)))
        x = p.x+12*s
        for name,label,units in flow:
            self.buttons[name] = (Rect(x,self.workflow.y+5*s,units*s*factor,26*s),label)
            x += (units+5)*s*factor
        self.buttons["CLOSE"] = (Rect(p.x+p.w-36*s,self.header.y+13*s,25*s,28*s),"X")
        self.buttons["FULL"] = (Rect(p.x+p.w-102*s,self.header.y+13*s,60*s,28*s),"Restore" if full else "Expand")

    def button(self,x,y):
        return next((name for name,(r,_) in self.buttons.items() if r.contains(x,y)),None)

class View:
    def __init__(self):
        self.cx = self.cy = 0.0
        self.zoom = 800.0
    def screen(self,point,rect):
        return (rect.x+rect.w/2+(point[0]-self.cx)*self.zoom,
                rect.y+rect.h/2+(point[1]-self.cy)*self.zoom)
    def world(self,point,rect):
        return ((point[0]-rect.x-rect.w/2)/self.zoom+self.cx,
                (point[1]-rect.y-rect.h/2)/self.zoom+self.cy)
    def pan(self,dx,dy):
        self.cx -= dx/self.zoom
        self.cy -= dy/self.zoom
    def zoom_at(self,point,rect,factor):
        before = self.world(point,rect)
        self.zoom = min(80000,max(20,self.zoom*factor))
        after = self.world(point,rect)
        self.cx += before[0]-after[0]
        self.cy += before[1]-after[1]
    def fit(self,points,rect):
        if not points:
            self.cx = self.cy = 0
            self.zoom = min(rect.w,rect.h)/.65
            return
        xs,ys = [p[0] for p in points],[p[1] for p in points]
        self.cx,self.cy = (min(xs)+max(xs))/2,(min(ys)+max(ys))/2
        self.zoom = min(80000,max(20,min(rect.w/max(.03,max(xs)-min(xs)),
                                       rect.h/max(.03,max(ys)-min(ys)))*.72))

def grid_step(zoom):
    target = 55/zoom
    power = 10**math.floor(math.log10(target))
    return next(v*power for v in (1,2,5,10) if v*power >= target)
