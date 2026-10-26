"""GPU overlay rendering, clipped to the owning WINDOW region only."""
import math
import blf
import gpu
from gpu_extras.batch import batch_for_shader
from .canvas import Rect, grid_step
from .core import area, triangulate

BG = (.065,.078,.10,1)
CHROME = (.088,.103,.13,1)
TEXT = (.88,.91,.96,1)
MUTED = (.46,.53,.63,1)
ACCENT = (.37,.84,.77,1)
PALETTE = [(.35,.69,.83),(.66,.54,.84),(.83,.66,.39),(.43,.74,.59)]

class Renderer:
    def __init__(self):
        self.shader = None
        self.line_shader = None
        self.s = 1
        self.offset = (0,0)
        self.triangle_cache = {}

    def triangles(self,points,color,indices=None):
        if not points:
            return
        if self.shader is None:
            self.shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        gpu.state.blend_set('ALPHA')
        batch = batch_for_shader(self.shader,'TRIS',{"pos":points},indices=indices)
        self.shader.bind()
        self.shader.uniform_float("color",color)
        batch.draw(self.shader)

    def rect(self,r,color):
        self.triangles([(r.x,r.y),(r.x+r.w,r.y),(r.x+r.w,r.y+r.h),(r.x,r.y+r.h)],
                       color,[(0,1,2),(0,2,3)])

    def lines(self,points,color,width=1,strip=False):
        if len(points)<2:
            return
        if self.line_shader is None:
            self.line_shader = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')
        gpu.state.blend_set('ALPHA')
        sh = self.line_shader
        batch = batch_for_shader(sh,'LINE_STRIP' if strip else 'LINES',{"pos":points})
        sh.bind()
        sh.uniform_float("viewportSize",gpu.state.viewport_get()[2:])
        sh.uniform_float("lineWidth",width*self.s)
        sh.uniform_float("color",color)
        batch.draw(sh)

    def dot(self,point,radius,color):
        x,y = point
        n = 16
        pts = [(x,y)]+[(x+math.cos(i*math.tau/n)*radius*self.s,
                       y+math.sin(i*math.tau/n)*radius*self.s) for i in range(n)]
        self.triangles(pts,color,[(0,i+1,(i+1)%n+1) for i in range(n)])

    def text(self,x,y,label,size=11,color=TEXT,center=False,max_width=None):
        blf.size(0,size*self.s)
        if max_width is not None:
            original = label
            while label and blf.dimensions(0,label)[0]>max_width:
                original = original[:-1]
                label = original+"..." if original else ""
        if center:
            x -= blf.dimensions(0,label)[0]/2
        blf.color(0,*color)
        blf.position(0,x,y,0)
        blf.draw(0,label)

    def clip(self,r):
        gpu.state.scissor_set(int(self.offset[0]+r.x),int(self.offset[1]+r.y),max(1,int(r.w)),max(1,int(r.h)))
        # BLF can rebind state during text drawing, so explicitly clip text too.
        blf.enable(0,blf.CLIPPING)
        blf.clipping(0,r.x,r.y,r.x+r.w,r.y+r.h)

    def fill_pattern(self,identity,world,screen,color):
        key = (identity,tuple(world))
        if key not in self.triangle_cache:
            try:
                self.triangle_cache[key] = triangulate(world)
            except ValueError:
                return False
        self.triangles(screen,color,self.triangle_cache[key])
        return True

    def draw(self,ed):
        self.s = s = ed.canvas_layout.scale
        l,view = ed.canvas_layout,ed.view
        p,c = l.panel,l.canvas
        blend = gpu.state.blend_get()
        depth = gpu.state.depth_test_get()
        scissor = gpu.state.scissor_get()
        viewport = gpu.state.viewport_get()
        # POST_PIXEL vertices are WINDOW-local; scissors use framebuffer coordinates.
        self.offset = viewport[:2]
        gpu.state.blend_set('ALPHA')
        gpu.state.depth_test_set('NONE')
        gpu.state.scissor_test_set(True)
        try:
            self.clip(p)
            self.rect(p,CHROME)
            self.rect(Rect(p.x,p.y+p.h-2*s,p.w,2*s),ACCENT)
            self.rect(c,BG)
            self.clip(c)
            self.grid(view,c)
            if not ed.session.document.patterns and not ed.draft and not ed.gesture:
                midx,midy = c.x+c.w/2,c.y+c.h/2
                self.text(midx,midy+25*s,"Start with a silhouette",18,TEXT,True,max_width=c.w-32*s)
                self.text(midx,midy-2*s,"P  Draw a polygon    /    R  Drag a rectangle",11,MUTED,True,max_width=c.w-24*s)
                self.text(midx,midy-24*s,"Real dimensions. Your own pattern pieces.",10,MUTED,True,max_width=c.w-24*s)
            for index,pat in enumerate(ed.session.document.patterns):
                world = pat.points
                selected = ed.session.selected == pat.id
                if selected and ed.gesture and ed.gesture['mode']=='MOVE' and ed.preview:
                    world = ed.preview
                pts = [view.screen(point,c) for point in world]
                color = PALETTE[index%len(PALETTE)]
                self.fill_pattern(pat.id,world,pts,(*color,.24 if selected else .12))
                self.lines(pts+pts[:1],ACCENT if selected else (*color,.85),2 if selected else 1.3,True)
                for i,point in enumerate(pts):
                    active = selected and ed.session.corner == i
                    self.dot(point,5.5 if active else 3.5,ACCENT if active else (*color,1))
                    if active:
                        self.dot(point,2,BG)
                xs,ys = [pt[0] for pt in pts],[pt[1] for pt in pts]
                self.text((min(xs)+max(xs))/2,max(ys)+15*s,pat.name,11,TEXT if selected else MUTED,True)
                if selected:
                    # Position inside the first ear, so concave pieces get a readable area label.
                    try:
                        tri = self.triangle_cache[(pat.id,tuple(world))][0]
                        center = tuple(sum(pts[i][axis] for i in tri)/3 for axis in (0,1))
                        self.text(*center,f"{abs(area(world))*10000:.0f} cm2",10,MUTED,True)
                    except KeyError:
                        pass
            self.seams(ed)
            if len(self.triangle_cache)>250:
                self.triangle_cache.clear()
            if ed.draft:
                pts = [view.screen(point,c) for point in ed.draft]
                self.lines(pts,ACCENT,2,True)
                if ed.preview:
                    end = view.screen(ed.preview[-1],c)
                    self.lines([pts[-1],end],(*ACCENT[:3],.5),1.3)
                    length = math.dist(ed.draft[-1],ed.preview[-1])*100
                    self.text(end[0]+10*s,end[1]+10*s,f"{length:.1f} cm",10,ACCENT)
                for point in pts:
                    self.dot(point,4,ACCENT)
                self.dot(pts[0],7,(*ACCENT[:3],.25))
                self.dot(pts[0],3.5,ACCENT)
            elif ed.gesture and ed.gesture['mode']=='RECT' and ed.preview:
                pts = [view.screen(point,c) for point in ed.preview]
                self.lines(pts+pts[:1],ACCENT,2,True)
                a,b = ed.preview[0],ed.preview[2]
                self.text(pts[2][0]+10*s,pts[2][1]+10*s,
                          f"{abs(b[0]-a[0])*100:.1f} x {abs(b[1]-a[1])*100:.1f} cm",11,ACCENT)
            self.clip(p)
            self.rulers(ed)
            self.rect(l.header,CHROME)
            self.rect(l.toolbar,CHROME)
            self.rect(l.workflow,CHROME)
            self.rect(l.footer,CHROME)
            self.text(p.x+14*s,l.header.y+28*s,"DEVIL DESIGNER",13,TEXT,max_width=p.w-130*s)
            self.text(p.x+14*s,l.header.y+11*s,"2D PATTERN WORKSPACE",9,MUTED,max_width=p.w-130*s)
            for name,(r,label) in l.buttons.items():
                active = name == ed.tool or name == 'SNAP' and ed.snap
                hover = r.contains(*ed.pointer)
                self.rect(r,(.17,.30,.31,1) if active else (.16,.19,.24,1) if hover else (.12,.14,.18,1))
                if active:
                    self.rect(Rect(r.x,r.y,r.w,2*s),ACCENT)
                self.text(r.x+r.w/2,r.y+9*s,label,10,ACCENT if active else TEXT,True,max_width=r.w-6*s)
            self.lines([(p.x,l.footer.y+l.footer.h),(p.x+p.w,l.footer.y+l.footer.h)],(.19,.23,.28,1))
            self.text(p.x+12*s,p.y+29*s,ed.message,10,TEXT,max_width=p.w-24*s)
            world = view.world(ed.pointer,c)
            count = len(ed.session.document.patterns)
            self.text(p.x+12*s,p.y+10*s,
                      f"{count} piece{'s' if count!=1 else ''}   |   X {world[0]*100:.1f}  Y {world[1]*100:.1f} cm",9,MUTED,max_width=p.w*.60)
            nav = "MMB pan  /  Wheel zoom" if p.w>480*s else "F: fit"
            blf.size(0,9*s)
            self.text(p.x+p.w-12*s-blf.dimensions(0,nav)[0],p.y+10*s,nav,9,MUTED)
        finally:
            blf.disable(0,blf.CLIPPING)
            gpu.state.scissor_set(*scissor)
            gpu.state.scissor_test_set(False)
            gpu.state.depth_test_set(depth)
            gpu.state.blend_set(blend)

    def grid(self,view,c):
        step = grid_step(view.zoom)
        low,high = view.world((c.x,c.y),c),view.world((c.x+c.w,c.y+c.h),c)
        minor,major = [],[]
        for axis in (0,1):
            for i in range(math.floor(low[axis]/step),math.ceil(high[axis]/step)+1):
                val = i*step
                if axis == 0:
                    x = view.screen((val,0),c)[0]
                    pts = [(x,c.y),(x,c.y+c.h)]
                else:
                    y = view.screen((0,val),c)[1]
                    pts = [(c.x,y),(c.x+c.w,y)]
                (major if i%5==0 else minor).extend(pts)
        self.lines(minor,(.15,.18,.23,.55))
        self.lines(major,(.20,.24,.30,.7))
        origin = view.screen((0,0),c)
        self.lines([(origin[0],c.y),(origin[0],c.y+c.h),
                    (c.x,origin[1]),(c.x+c.w,origin[1])],(.29,.39,.43,.55))

    def rulers(self,ed):
        l,v = ed.canvas_layout,ed.view
        c,p,s = l.canvas,l.panel,self.s
        self.rect(l.ruler_top,(.10,.12,.15,1))
        self.rect(Rect(p.x,c.y,25*s,c.h),(.10,.12,.15,1))
        step = grid_step(v.zoom)
        low,high = v.world((c.x,c.y),c),v.world((c.x+c.w,c.y+c.h),c)
        self.clip(l.ruler_top)
        for i in range(math.floor(low[0]/step),math.ceil(high[0]/step)+1):
            x = v.screen((i*step,0),c)[0]
            self.lines([(x,l.ruler_top.y),(x,l.ruler_top.y+5*s)],MUTED)
            self.text(x+4*s,l.ruler_top.y+9*s,f"{i*step*100:g}",9,MUTED)
        self.clip(Rect(p.x,c.y,25*s,c.h))
        for i in range(math.floor(low[1]/step),math.ceil(high[1]/step)+1):
            y = v.screen((0,i*step),c)[1]
            self.text(p.x+3*s,y+3*s,f"{i*step*100:g}",8,MUTED,max_width=22*s)
        self.clip(p)
        self.text(p.x+4*s,l.ruler_top.y+9*s,"cm",8,ACCENT)

    def seams(self,ed):
        doc = ed.session.document
        c = ed.canvas_layout.canvas
        for index,seam in enumerate(doc.seams):
            mids = []
            selected = ed.seam_selected==seam.id
            color = (1,.67,.31,1) if selected else (.83,.48,.75,.85)
            for side,edge in enumerate((seam.a,seam.b)):
                a,b = [ed.view.screen(p,c) for p in doc.edge_points(edge)]
                self.lines([a,b],color,3)
                # Large matching dots identify the first endpoints of each sewing pair.
                first = b if side==1 and seam.reverse else a
                self.dot(first,5,color)
                mid = ((a[0]+b[0])/2,(a[1]+b[1])/2)
                mids.append(mid)
                if ed.tool=='SEW':
                    self.text(mid[0]+8*self.s,mid[1]+8*self.s,str(index+1),11,color)
            if ed.tool=='SEW':
                a,b = mids
                steps = max(2,int(math.dist(a,b)/(10*self.s)))
                for i in range(0,steps,2):
                    start = tuple(a[j]+(b[j]-a[j])*i/steps for j in (0,1))
                    end = tuple(a[j]+(b[j]-a[j])*min(i+1,steps)/steps for j in (0,1))
                    self.lines([start,end],(*color[:3],.35))
        if ed.pending_edge:
            try:
                pts = [ed.view.screen(p,c) for p in doc.edge_points(ed.pending_edge)]
                self.lines(pts,(1,.82,.3,1),4)
            except ValueError:
                pass
