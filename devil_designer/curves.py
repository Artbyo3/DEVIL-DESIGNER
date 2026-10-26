"""Cubic Bezier evaluation, arc-length sampling, and planar operations in metres."""
import math
from functools import lru_cache
import bisect

TOLERANCE=.00005


def mix(a,b,t): return tuple(x+(y-x)*t for x,y in zip(a,b))
def add(a,b): return tuple(x+y for x,y in zip(a,b))
def sub(a,b): return tuple(x-y for x,y in zip(a,b))
def mul(a,s): return tuple(x*s for x in a)


def controls(a,b):
    p=(a.x,a.y); q=(b.x,b.y)
    return p,add(p,a.outgoing) if a.outgoing is not None else mix(p,q,1/3),add(q,b.incoming) if b.incoming is not None else mix(p,q,2/3),q


def evaluate(control,t):
    a,b,c,d=control
    return add(add(mul(a,(1-t)**3),mul(b,3*(1-t)**2*t)),add(mul(c,3*(1-t)*t*t),mul(d,t**3)))


def split(control,t):
    a,b,c,d=control
    ab,bc,cd=mix(a,b,t),mix(b,c,t),mix(c,d,t)
    abc,bcd=mix(ab,bc,t),mix(bc,cd,t)
    center=mix(abc,bcd,t)
    return (a,ab,abc,center),(center,bcd,cd,d)


@lru_cache(maxsize=2048)
def table(control,tolerance=TOLERANCE):
    result=[(0,control[0])]
    def visit(c,lo,hi,depth):
        polygon=sum(math.dist(c[i],c[i+1]) for i in range(3))
        chord=math.dist(c[0],c[3])
        # Both curvature and the control polygon's deviation are bounded.
        if depth>=16 or polygon-chord<tolerance:
            result.append((hi,c[3])); return
        left,right=split(c,.5)
        middle=(lo+hi)/2
        visit(left,lo,middle,depth+1)
        visit(right,middle,hi,depth+1)
    visit(control,0,1,0)
    return tuple(result)


def speed(control,t):
    a,b,c,d=control
    derivative=[3*((1-t)**2*(b[j]-a[j])+2*(1-t)*t*(c[j]-b[j])+t*t*(d[j]-c[j])) for j in (0,1)]
    return math.hypot(*derivative)


def integral(control,lo,hi):
    # Five-point Gauss-Legendre integration on each adaptively flattened interval.
    nodes=(0,-.5384693101056831,.5384693101056831,-.906179845938664,.906179845938664)
    weights=(.5688888888888889,.4786286704993665,.4786286704993665,.2369268850561891,.2369268850561891)
    middle,half=(lo+hi)/2,(hi-lo)/2
    return half*sum(w*speed(control,middle+half*x) for x,w in zip(nodes,weights))


@lru_cache(maxsize=2048)
def arc_table(control):
    data=table(control)
    cumulative=[0.0]
    for (lo,_),(hi,_) in zip(data,data[1:]):cumulative.append(cumulative[-1]+integral(control,lo,hi))
    return data,tuple(cumulative)


def length(control):return arc_table(control)[1][-1]


def parameter(control,fraction):
    fraction=max(0,min(1,fraction))
    data,cumulative=arc_table(control)
    if cumulative[-1]<1e-12:return fraction
    target=fraction*cumulative[-1]
    i=max(1,min(len(data)-1,bisect.bisect_left(cumulative,target)))
    lo,hi=data[i-1][0],data[i][0]
    t=lo+(hi-lo)*(target-cumulative[i-1])/max(1e-15,cumulative[i]-cumulative[i-1])
    for _ in range(3):
        error=cumulative[i-1]+integral(control,lo,t)-target
        t=max(lo,min(hi,t-error/max(1e-12,speed(control,t))))
    return t


def at_length(control,fraction): return evaluate(control,parameter(control,fraction))


def closest_fraction(control,point):
    data,cumulative=arc_table(control)
    best=(float('inf'),0)
    for i in range(1,len(data)):
        a,b=data[i-1][1],data[i][1]
        delta=sub(b,a); squared=sum(x*x for x in delta)
        weight=max(0,min(1,sum((point[j]-a[j])*delta[j] for j in (0,1))/squared)) if squared else 0
        distance=math.dist(point,mix(a,b,weight))
        if distance<best[0]: best=(distance,(cumulative[i-1]+weight*(cumulative[i]-cumulative[i-1]))/max(1e-15,cumulative[-1]))
    return best[1],best[0]


def reflect(point,a,b,vector=False):
    direction=sub(b,a)
    size=sum(x*x for x in direction)
    if size<1e-15: raise ValueError('A mirror edge needs two distinct endpoints.')
    local=point if vector else sub(point,a)
    result=sub(mul(direction,2*sum(x*y for x,y in zip(local,direction))/size),local)
    return result if vector else add(a,result)


def offset_polygon(points,distance):
    from .core import area, validate_polygon
    validate_polygon(points)
    sign=1 if area(points)>0 else -1
    shifted=[]
    count=len(points)
    for i,p in enumerate(points):
        previous,nxt=points[i-1],points[(i+1)%count]
        u,v=sub(p,previous),sub(nxt,p)
        lu,lv=math.hypot(*u),math.hypot(*v)
        u,v=mul(u,1/lu),mul(v,1/lv)
        n1,n2=(sign*u[1],-sign*u[0]),(sign*v[1],-sign*v[0])
        a,b=add(p,mul(n1,distance)),add(p,mul(n2,distance))
        determinant=u[0]*v[1]-u[1]*v[0]
        if abs(determinant)<1e-10:
            shifted.append(mix(a,b,.5)); continue
        delta=sub(b,a)
        t=(delta[0]*v[1]-delta[1]*v[0])/determinant
        candidate=add(a,mul(u,t))
        if math.dist(candidate,p)>max(abs(distance)*8,.001):
            shifted.extend([a,b])
        else: shifted.append(candidate)
    validate_polygon(shifted)
    return shifted
