from pathlib import Path
from fractions import Fraction
from collections import Counter
import re,json,subprocess,hashlib,os
_root=Path(__file__).resolve().parents[1]
_config=json.loads((_root/'config.json' if (_root/'config.json').exists() else _root/'config.example.json').read_text())
def _tool_path(env,key):
    p=Path(os.environ.get(env,_config[key])).expanduser()
    return p if p.is_absolute() else _root/p
T=_tool_path('FUSION_LLVM_BIN','llvm_bin')
CUDA=_tool_path('FUSION_CUDA_BIN','cuda_bin')
OPT=_tool_path('FUSION_OPT','fusion_opt')
COST=dict(add=5,fadd=5,mul=10,fmul=10,sdiv=20,udiv=20,fdiv=20,load=100,store=100)

sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

def dump(p,d):p.write_text(json.dumps(d,indent=2,default=str)+'\n')

def command(d,label,cmd):
    cmd=list(map(str,cmd));p=subprocess.run(cmd,capture_output=True,text=True,timeout=180)
    dump(d/(label+'.json'),dict(command=cmd,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr))
    if p.returncode:raise RuntimeError(label+': '+p.stderr[-1800:])
    return p

def function(text,name):
    m=re.search(r'^define[^\n]*@'+re.escape(name)+r'\([^\n]*\{\n.*?^\}',text,re.M|re.S);assert m,name;return m[0]

def inline(text,name):
    f=function(text,name);m=re.search(r' #(\d+)(?: [^\n{]+)? \{',f.splitlines()[0])
    if not m:
        return text.replace(f,f.replace(' {',' alwaysinline {',1),1)
    aid=m[1];attrs=re.search(r'^attributes #'+aid+r' = \{ (.*?) \}',text,re.M)[1]
    attrs=re.sub(r'\b(?:noinline|optnone|alwaysinline)\b','',attrs)
    nid=max(map(int,re.findall(r'^attributes #(\d+) =',text,re.M)))+1
    return text.replace(f,re.sub(r' #'+aid+r'\b',' #'+str(nid),f,count=1),1)+'\nattributes #'+str(nid)+' = { alwaysinline '+attrs+' }\n'

def costs(module,name):
    counts=Counter()
    for line in function(Path(module).read_text(),name).splitlines()[1:-1]:
        line=line.split(';',1)[0].strip()
        if not line or line.endswith(':'):continue
        op=line.split(' = ')[-1].split()[0]
        if op in ('tail','musttail','notail'):op='call'
        counts[op]+=COST.get(op,3)
    return dict(counts)

def score(a,b):
    ca,cb=a['costs'],b['costs'];return Fraction(sum(min(v,cb.get(k,0)) for k,v in ca.items() if k!='phi'),sum(ca.values())+sum(cb.values()))

def compile_src(d,label,src,case):
    p=d/(label+'.cu');p.write_text(src);low=case in ['ced','minimap2','segsort']
    command(d,label+'-clang',[T/'clang','-x','cuda','-std=c++17','--cuda-device-only','-nocudainc','-nocudalib','--cuda-gpu-arch=sm_80',('-O0' if low else '-O3'),*(['-Xclang','-disable-O0-optnone'] if low else []),'-ffp-contract=off','-fno-discard-value-names','-Xclang','-mlink-builtin-bitcode','-Xclang',CUDA.parent/'nvvm/libdevice/libdevice.10.bc','-S','-emit-llvm',p,'-o',d/(label+'-front.ll')])
    command(d,label+'-prep',[T/'opt',d/(label+'-front.ll'),*(['-mem2reg','-instcombine'] if low else []),'-verify','-S','-o',d/(label+'.ll')])
    return d/(label+'.ll')

def cleanup(d,source,name,label='after',mode='o3'):
    # Default O3 is for initial leaf preparation. merge() explicitly supplies
    # its separate cleanup policy, which defaults to minimal.
    text=Path(source).read_text()
    for f in re.findall(r'^define[^\n]*@([^ (]+)\(',text,re.M):
        if f==name or f.startswith('guard_'):text=inline(text,f)
    p=d/(label+'-inline.ll');p.write_text(text)
    if mode not in ('minimal','o3'):raise ValueError('unknown cleanup mode: '+mode)
    passes=['-simplifycfg'] if mode=='minimal' else ['-O3']
    command(d,label,[T/'opt',p,'-always-inline',*passes,'-internalize','-internalize-public-api-list='+name,'-globaldce','-verify','-S','-o',d/(label+'.ll')])
    return d/(label+'.ll')

def record(a,b,p):
    name=f'g_{a}_{b}';return dict(lo=a,hi=b,module=str(p),name=name,sha256=sha(p),costs=costs(p,name))

def merge(case,a,b,d,guard=None,cleanup_mode='minimal'):
    s=SPECS[case];assert a['hi']+1==b['lo'];d.mkdir()
    name=f'g_{a["lo"]}_{b["hi"]}';g=guard['name'] if guard else f'guard_{a["hi"]}';argtype=s.get('guard_args',s['args'].split(',')[0])
    src=prefix(case)+f'extern "C" __device__ {s["ret"]} {a["name"]}({s["args"]});\nextern "C" __device__ {s["ret"]} {b["name"]}({s["args"]});\nextern "C" __device__ bool {g}({argtype});\n'
    def invoke(n):return (f'{n}({s["passed"]});return;' if s['ret']=='void' else f'return {n}({s["passed"]});')
    src+=f'extern "C" __device__ {s["ret"]} {name}({s["args"]}) {{if ({g}({s["arg"]})) {{{invoke(a["name"])}}} else {{{invoke(b["name"])}}}}}\n'
    wrapper=compile_src(d,'parent',src,case)
    command(d,'link',[T/'llvm-link',wrapper,a['module'],b['module'],guard['module'] if guard else O/case/'guards'/str(a['hi'])/'guard.ll','-S','-o',d/'linked.ll'])
    command(d,'inline',[T/'opt',d/'linked.ll','-always-inline','-simplifycfg','-verify','-S','-o',d/'before.ll'])
    p=command(d,'meld',[O/'engine/opt-adjacent',d/'before.ll','-cfmelder','-cfmelder-entry-only','-run-cfmelding-once','-run-cfmelding-on-function='+name,'-cf-merging-similarity-threshold=0.0','-verify','-S','-o',d/'meld.ll'])
    if 'ADJACENT_ENTRY_MELD_SUCCESS' not in p.stderr:return None
    assert p.stderr.count('ADJACENT_ENTRY_MELD_SUCCESS')==1
    after=cleanup(d,d/'meld.ll',name,mode=cleanup_mode)
    assert not re.search(r'\bcall\b[^\n]*@guard_',function(after.read_text(),name))
    return record(a['lo'],b['hi'],after)
