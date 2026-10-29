"""Experimental IR warp-issue proxy, NOT a latency or memory-transaction model.
Acyclic CFG only. Concrete integer control; unknown branch predicates defer.
Each visited instruction charged once per scenario's union of lane paths.
No static phi charge. No occupancy or backend-predication claims.
"""
import re
from collections import Counter
WEIGHTS={'phi':0,'bitcast':0,'addrspacecast':0,'ret':0,'load':4,'store':4,'fdiv':10,'sdiv':10,'udiv':10,'select':1,'br':1}
class UnsupportedCost(Exception):pass

def function(text,name):
    m=re.search(r'^define[^\n]*@'+re.escape(name)+r'\([^\n]*\{\n.*?^\}',text,re.M|re.S)
    if not m:raise UnsupportedCost('missing function '+name)
    return m[0]

class Program:
    def __init__(self,text,name):
        self.blocks={};block=None
        for raw in function(text,name).splitlines()[1:-1]:
            line=raw.split(';',1)[0].strip()
            if not line:continue
            if line.endswith(':'):block=line[:-1];self.blocks[block]=[]
            else:
                if block is None:raise UnsupportedCost('implicit entry')
                self.blocks[block].append(line)
        self.ops={}
        for b,lines in self.blocks.items():
            for i,l in enumerate(lines):
                op=l.split(' = ')[-1].split()[0]
                if op in ['call','tail','invoke','switch','indirectbr','atomicrmw','cmpxchg','fence']:raise UnsupportedCost('unsupported operation '+op)
                self.ops[b,i]=op
    def path(self,tx,ty):
        env={'%tx':tx,'%ty':ty};block=next(iter(self.blocks));prev=None;seen=set();executed=set()
        def val(t):
            t=t.strip()
            if t=='true':return 1
            if t=='false':return 0
            if re.fullmatch(r'-?\d+',t):return int(t)
            return env.get(t)
        while True:
            if block in seen:raise UnsupportedCost('loops unsupported')
            seen.add(block);nxt=None
            for i,line in enumerate(self.blocks[block]):
                executed.add((block,i));name=None;rhs=line
                if ' = ' in line:name,rhs=line.split(' = ',1)
                op=rhs.split()[0];v=None
                if op=='ret':return executed
                if op=='unreachable':raise UnsupportedCost('reached unreachable')
                if op=='br':
                    m=re.fullmatch(r'br label %([^, ]+).*',rhs)
                    if m:nxt=m[1]
                    else:
                        m=re.match(r'br i1 ([^,]+), label %([^, ]+), label %([^, ]+)',rhs)
                        if not m:raise UnsupportedCost(rhs)
                        c=val(m[1])
                        if c is None:raise UnsupportedCost('unknown control '+m[1])
                        nxt=m[2] if c else m[3]
                    break
                if op=='phi':
                    for x,b in re.findall(r'\[\s*([^,]+),\s*%([^ ]+)\s*\]',rhs):
                        if b==prev:v=val(x);break
                elif op=='icmp':
                    m=re.match(r'icmp (\w+) i(\d+) ([^,]+), ([^,]+)',rhs)
                    if m:
                        pred,bits,x,y=m.groups();x,y=val(x),val(y)
                        if x is not None and y is not None:
                            if pred.startswith('u'):x%=1<<int(bits);y%=1<<int(bits)
                            v=int({'eq':x==y,'ne':x!=y,'sgt':x>y,'ugt':x>y,'sge':x>=y,'uge':x>=y,'slt':x<y,'ult':x<y,'sle':x<=y,'ule':x<=y}[pred])
                elif op in ['add','sub','mul','and','or','xor','shl','lshr','ashr']:
                    m=re.match(op+r'(?: nsw| nuw| exact)* i(\d+) ([^,]+), ([^,]+)',rhs)
                    if m:
                        bits,x,y=m.groups();x,y=val(x),val(y);bits=int(bits)
                        if x is not None and y is not None:
                            v={'add':lambda:x+y,'sub':lambda:x-y,'mul':lambda:x*y,'and':lambda:x&y,'or':lambda:x|y,'xor':lambda:x^y,'shl':lambda:x<<y,'lshr':lambda:(x%(1<<bits))>>y,'ashr':lambda:x>>y}[op]();v%=1<<bits
                            if v>=1<<(bits-1):v-=1<<bits
                elif op in ['zext','sext','trunc']:
                    m=re.match(op+r' i(\d+) ([^ ]+) to i(\d+)',rhs)
                    if m:
                        src,x,dst=m.groups();v=val(x)
                        if v is not None:
                            if op=='zext':v%=1<<int(src)
                            if op=='trunc':v%=1<<int(dst)
                elif op=='select':
                    m=re.match(r'select i1 ([^,]+), [^ ]+ ([^,]+), [^ ]+ ([^,]+)',rhs)
                    if m:
                        c=val(m[1]);v=val(m[2] if c else m[3]) if c is not None else None
                if name:env[name]=v
            if nxt is None:raise UnsupportedCost('missing terminator')
            prev,block=block,nxt
    def estimate(self,lanes):
        issued=set()
        for tx,ty in lanes:issued.update(self.path(tx,ty))
        counts=Counter(self.ops[x] for x in issued)
        return sum(WEIGHTS.get(op,1)*n for op,n in counts.items()),dict(counts)

def subset_scenarios(representatives):
    # Original leaf identity is fixed once, never regenerated after fusion.
    result=[]
    for mask in range(1,1<<len(representatives)):
        points=[v for i,v in enumerate(representatives) if mask&(1<<i)]
        result.append({'id':mask,'origins':[i for i in range(len(representatives)) if mask&(1<<i)],'lanes':[points[i%len(points)] for i in range(32)]})
    return result
