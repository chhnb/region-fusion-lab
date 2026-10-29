"""Check whether BF/DaRM realize select(code) -> shift -> add for a two-way pair.
Explicit invocation only; not an extra dependency of the default lightweight tests.
"""
from pathlib import Path
import argparse,ctypes as C,json,re,random
from vendor import engine as G
from experiments.ir_pipeline import transform_all

def source(a,b,elide_zero=False):
    right=(f'  %rs = shl i32 {b}, %shift\n  %rv = add i32 %rs, %accum\n  store i32 %rv, i32* %out\n' if not elide_zero else '  store i32 %accum, i32* %out\n')
    return f'''target triple = "nvptx64-nvidia-cuda"
define void @test(i1 %p, i32 %accum, i32 %shift, i32* %out) {{
entry:
  br i1 %p, label %left, label %right
left:
  %ls = shl i32 {a}, %shift
  %lv = add i32 %ls, %accum
  store i32 %lv, i32* %out
  br label %exit
right:
{right}  br label %exit
exit:
  ret void
}}
'''

def template(a,b):
    return f'''target triple = "nvptx64-nvidia-cuda"
define void @test(i1 %p, i32 %accum, i32 %shift, i32* %out) {{
entry:
  %code = select i1 %p, i32 {a}, i32 {b}
  %delta = shl i32 %code, %shift
  %value = add i32 %delta, %accum
  store i32 %value, i32* %out, align 4
  ret void
}}
'''

def features(p):
    f=G.function(p.read_text(),'test');ops=re.findall(r'^\s*(?:%[^=]+ = )?(shl|add|select|store|br)\b',f,re.M)
    return {op:ops.count(op) for op in ['shl','add','select','store','br']}

def canonical_body(p):
    f=G.function(p.read_text(),'test');lines=[];mapping={}
    def rename(m):
        name=m[0]
        if name not in mapping:mapping[name]='%v'+str(len(mapping))
        return mapping[name]
    # Register arguments first, independent of naming in the body.
    re.sub(r'%[-a-zA-Z$._0-9]+',rename,f.splitlines()[0])
    for line in f.splitlines()[1:-1]:
        line=line.split(';',1)[0].strip()
        if not line or line.endswith(':'):continue
        lines.append(re.sub(r'%[-a-zA-Z$._0-9]+',rename,line))
    return lines

def check_cpu(d,path,tag,a,b,values):
    text=re.sub(r'^target (?:triple|datalayout) = .*\n','',path.read_text(),flags=re.M)
    host=d/(tag+'-host.ll');host.write_text(text)
    G.command(d,tag+'-host',[G.T/'clang','-target','x86_64-pc-linux-gnu','-shared','-fPIC','-O0','-Wno-override-module',host,'-o',d/(tag+'.so')])
    lib=C.CDLL(str(d/(tag+'.so')));fn=lib.test;fn.argtypes=[C.c_bool,C.c_uint32,C.c_uint32,C.POINTER(C.c_uint32)];fn.restype=None
    out=C.c_uint32();count=0
    for p in [False,True]:
        for shift in range(32):
            for accum in values:
                fn(p,accum,shift,C.byref(out));expected=(accum+((a if p else b)<<shift))&0xffffffff
                assert out.value==expected,(tag,p,shift,accum,out.value,expected)
                count+=1
    return count

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);args=ap.parse_args();out=args.out.resolve();out.mkdir(parents=True,exist_ok=False)
    rng=random.Random(20261029);values=[0,1,0x7fffffff,0x80000000,0xffffffff]+[rng.getrandbits(32) for _ in range(64)];results={}
    for name,a,b,elide in [('124-120',124,120,False),('4-0-explicit',4,0,False),('4-0-folded',4,0,True)]:
        d=out/name;d.mkdir();inp=d/'input.ll';inp.write_text(source(a,b,elide));rows=transform_all(inp,d/'methods','test')
        assert all(r['status']=='success' for r in rows.values()),rows
        t=d/'template.ll';t.write_text(template(a,b));G.command(d,'template-post',[G.T/'opt',t,'-O3','-verify','-S','-o',d/'template-final.ll'])
        variants={'template-raw':t,'template-final':d/'template-final.ll'}
        for method in ['original','bf','darm']:
            variants[method+'-raw']=d/'methods'/method/'meld.ll';variants[method+'-final']=d/'methods'/method/'final.ll'
        counts={};struct={}
        for tag,path in variants.items():counts[tag]=check_cpu(d,path,tag,a,b,values);struct[tag]=features(path)
        same={method:canonical_body(variants[method+'-final'])==canonical_body(d/'template-final.ll') for method in ['original','bf','darm']}
        if name=='124-120':
            for method in ['bf','darm']:
                f=struct[method+'-raw'];assert rows[method]['melds']==1 and f==dict(shl=1,add=1,select=1,store=1,br=0),f
                assert canonical_body(variants[method+'-raw'])==canonical_body(t)
        results[name]=dict(melds={m:rows[m]['melds'] for m in rows},features=struct,CPU_cases_per_variant=counts,normalized_final_body_equals_template=same)
        G.dump(out/'summary.json',results);print(name,results[name]['melds'],same,flush=True)
if __name__=='__main__':main()
