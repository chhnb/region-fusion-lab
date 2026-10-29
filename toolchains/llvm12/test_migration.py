#!/usr/bin/env python3
"""Local-only migration regression: both BF/DaRM, same initial IR, CPU differentials."""
from pathlib import Path
import argparse,sys,ctypes as C,random,math,re,resource,json
D0=Path(__file__).resolve().parent;ROOT=D0.parents[1];sys.path.insert(0,str(ROOT))
from vendor import engine as G
from experiments.ir_pipeline import transform_all
resource.setrlimit(resource.RLIMIT_CORE,(0,0))
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);args=p.parse_args();D=args.out.resolve();D.mkdir(parents=True,exist_ok=False)
def run(label,cmd):return G.command(D,label,cmd)
run('alignment-build',['g++','-std=c++17','-O2','-I'+str(ROOT/'third_party/darm/llvm/lib/Transforms/CFMelder'),ROOT/'third_party/darm/cfm_benchmarks/fusion-regressions/alignment.cpp','-o',D/'alignment'])
run('alignment',[D/'alignment'])
def host(ir,tag):
 text=Path(ir).read_text();text=re.sub(r'^target (?:triple|datalayout) = .*\n','',text,flags=re.M);p=D/(tag+'.ll');p.write_text(text)
 run(tag+'-cpu',[G.T/'clang','-target','x86_64-pc-linux-gnu','-shared','-fPIC','-O0','-ffp-contract=off','-Wno-override-module',p,'-o',D/(tag+'.so')]);return C.CDLL(str(D/(tag+'.so'))).test
counts={};melds={}
for label,filename,lower in [('nested','switch-regions.ll',False),('entry','entry-switch.ll',True),('alias','switch-alias-edges.ll',False)]:
 inp=ROOT/'third_party/darm/cfm_benchmarks/fusion-regressions'/filename;rows=transform_all(inp,D/label,'test',lower_switch=lower);assert all(v['status']=='success' for v in rows.values()),rows;assert rows['darm']['melds']>0
 for mode in ['bf','darm']:
  a=host(inp,label+'-'+mode+'-before');b=host(rows[mode]['output'],label+'-'+mode+'-after');total=0
  if label=='nested':
   for f in [a,b]:f.argtypes=[C.c_bool,C.c_int,C.c_float,C.POINTER(C.c_float)];f.restype=None
   rng=random.Random(20261027);xs=[0.,-0.,1.,-1.,math.inf,-math.inf,math.nan]+[rng.uniform(-1e6,1e6) for _ in range(128)]
   for left in [False,True]:
    for n in [-2147483648,-1,0,1,2,3,2147483647]:
     for x in xs:
      x0=C.c_float(12345.);x1=C.c_float(12345.);a(left,n,x,C.byref(x0));b(left,n,x,C.byref(x1));assert (math.isnan(x0.value) and math.isnan(x1.value)) or bytes(x0)==bytes(x1);total+=1
  elif label=='alias':
   for f in [a,b]:f.argtypes=[C.c_bool,C.c_int,C.c_int,C.c_float,C.POINTER(C.c_float)];f.restype=None
   for left in [False,True]:
    for n in [-1,0,1,2,3]:
     for m in [-1,0,1,2,3]:
      for x in [0.,-0.,1.,-1.,math.inf,-math.inf,math.nan]:
       x0=C.c_float(12345.);x1=C.c_float(12345.);a(left,n,m,x,C.byref(x0));b(left,n,m,x,C.byref(x1));assert (math.isnan(x0.value) and math.isnan(x1.value)) or bytes(x0)==bytes(x1);total+=1
  else:
   for f in [a,b]:f.argtypes=[C.c_uint8,C.c_int,C.c_int,C.POINTER(C.c_int)];f.restype=None
   for tag in range(256):
    for x in [-2147483648,-1,0,1,2147483647]:
     for y in [-2147483648,-1,0,1,2147483647]:
      x0=C.c_int(0x12345678);x1=C.c_int(0x12345678);a(tag,x,y,C.byref(x0));b(tag,x,y,C.byref(x1));assert x0.value==x1.value;total+=1
  counts[label+'-'+mode]=total;melds[label+'-'+mode]=rows[mode]['melds']
rows=transform_all(ROOT/'third_party/darm/cfm_benchmarks/fusion-regressions/convergent.ll',D/'convergent','test');assert all(v['status']=='success' and v['melds']==0 for v in rows.values())
G.dump(D/'summary.json',dict(alignment_pairs=14641,differential_cases=counts,melds=melds,convergent_rejected=True,shared_input_enforced=True));print('PASS',counts,melds,flush=True)
