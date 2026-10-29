"""Compare the historical unrolled group2/pairs-max against fixed-pair DaRM.
Legacy direct-source compilation is explicitly a preparation diagnostic.
The helper-template/DARM arms reuse one prepared kernel and one final pipeline.
"""
from pathlib import Path
import argparse,json,re,itertools,difflib
from vendor import engine as G
from backends.darm import DARMGenerator
from .case import TPACF
from .prepare import HP,PREFIX,ARGS,PASSED,PATTERN,interval_predicate
HERE=Path(__file__).resolve().parent
PAIR_DECL='extern "C" { __device__ __constant__ double pairbounds[15]; }\n'

def canonical_tail_diagnostic(base):
    """Diagnostic only. Uses TPACF's proven shift range0/8/16/24.
    This rewrite is NOT a generally legal shift/select transform for arbitrary shifts.
    It is not enabled in the production DARM generator.
    """
    base=Path(base).resolve();D=base/'tail-diagnostic';D.mkdir(exist_ok=False);d=D/'canonical_tail';d.mkdir()
    text=(base/'darm_helper_max/linked.ll').read_text();f=G.function(text,'g_30_31')
    assert 'shl i32 4, %shift' in f and f.count('= fcmp ')==1 and f.count('store i32 ')==1 and not re.search(r'^  br ',f,re.M),'unexpected tail shape'
    assert 'i64 0, i64 0)' in f and '@binbounds' in f,'unexpected tail boundary'
    lines=f.splitlines();k=next(i for i,l in enumerate(lines) if '= fcmp ' in l);pred=lines[k].split(' = ')[0].strip()
    store=next(l for l in lines if l.strip().startswith('store i32 '));store=re.sub(r'store i32 %[-a-zA-Z._0-9]+,','store i32 %value.canonical,',store)
    new='\n'.join(lines[:k+1]+[f'  %code.canonical = select i1 {pred}, i32 4, i32 0','  %delta.canonical = shl i32 %code.canonical, %shift','  %value.canonical = add i32 %delta.canonical, %accum',store,'  ret void','}'])
    (d/'linked.ll').write_text(text.replace(f,new,1));(d/'before-tail.ll').write_text(f);(d/'after-tail.ll').write_text(new)
    G.command(d,'helper',[G.T/'opt',d/'linked.ll','-internalize','-internalize-public-api-list=tpacf_decide,binbounds,pairbounds','-globaldce','-always-inline','-O3','-verify','-S','-o',d/'helper.ll'])
    G.command(d,'strip',[G.T/'opt',d/'helper.ll','-strip','-S','-o',d/'helper-normalized.ll'])
    G.command(d,'post',[G.T/'opt',d/'linked.ll','-always-inline','-O3','-internalize','-internalize-public-api-list=ACFKernel,ACFKernelSymm,binbounds,pairbounds','-globaldce','-verify','-S','-o',d/'post.ll'])
    G.command(d,'llc',[G.T/'llc',d/'post.ll','-O3','-march=nvptx64','-mcpu=sm_80','-o',d/'kernel.ptx'])
    G.command(d,'ptxas',[G.CUDA/'ptxas','-O3','--fmad=false','-arch=sm_86','-v',d/'kernel.ptx','-o',d/'kernel.cubin'])
    a=json.loads((base/'artifacts.json').read_text());a={n:a[n] for n in ['native','original','template_helper_max']};a['canonical_tail']=dict(path=str(d/'kernel.cubin'),sha256=G.sha(d/'kernel.cubin'),aux_constants={'pairbounds':'tpacf_pair_max'})
    G.dump(D/'artifacts.json',a);G.dump(D/'plan.json',dict(case='tpacf',diagnostic='only canonicalize last 4/0 pair, no other DARM changes',validation_fixtures=['isotropic','edges','wide','unordered','nonfinite_bounds']));G.dump(D/'completion.json',dict(build_complete=True,gpu_validated=False))
    after=G.function((d/'helper-normalized.ll').read_text(),'tpacf_decide');before=G.function((base/'template_helper_max/helper-normalized.ll').read_text(),'tpacf_decide')
    print('helper body same',after.splitlines()[1:]==before.splitlines()[1:]);print('cubin same', (d/'kernel.cubin').read_bytes()==(base/'template_helper_max/kernel.cubin').read_bytes())
    G.dump(D/'equivalence.json',dict(helper_body_same=after.splitlines()[1:]==before.splitlines()[1:],cubin_same=(d/'kernel.cubin').read_bytes()==(base/'template_helper_max/kernel.cubin').read_bytes()))

def compare_outputs(out):
    out=Path(out);dest=out/'analysis';dest.mkdir(exist_ok=False)
    arts=json.loads((out/'artifacts.json').read_text());names=['legacy_direct_max','template_helper_max','darm_helper_max','darm_helper_or'];sass={};stats={}
    for name in names:
        d=dest/name;d.mkdir();p=G.command(d,'sass',[G.CUDA/'cuobjdump','--dump-sass',arts[name]['path']]);(d/'sass.txt').write_text(p.stdout)
        parts=re.split(r'Function\s*:\s*(\S+)',p.stdout);sass[name]={parts[i]:re.findall(r'/\*\s*0x([0-9a-f]+)\s*\*/',parts[i+1]) for i in range(1,len(parts),2)}
        stats[name]={}
        for kernel in ['ACFKernel','ACFKernelSymm']:
            f=G.function((out/name/'post.ll').read_text(),kernel)
            stats[name][kernel]=dict(sass_instructions=len(sass[name][kernel])//2,static_fmul=len(re.findall(r'= fmul ',f)),loop_branches=[l.strip() for l in f.splitlines() if '!llvm.loop' in l],iteration_phis=[l.strip() for l in f.splitlines() if re.match(r'\s*%i[.0-9][^=]*= phi i32',l)])
    results=[]
    for a,b in itertools.combinations(names,2):
        row=dict(left=a,right=b,cubin_identical=Path(arts[a]['path']).read_bytes()==Path(arts[b]['path']).read_bytes(),sass_identical={k:sass[a][k]==sass[b][k] for k in ['ACFKernel','ACFKernelSymm']})
        if a!='legacy_direct_max':
            fa=G.function((out/a/'helper-normalized.ll').read_text(),'tpacf_decide');fb=G.function((out/b/'helper-normalized.ll').read_text(),'tpacf_decide');row['helper_body_identical']=fa.splitlines()[1:]==fb.splitlines()[1:]
        results.append(row)
    fa=G.function((out/'template_helper_max/helper-normalized.ll').read_text(),'tpacf_decide');fb=G.function((out/'darm_helper_max/helper-normalized.ll').read_text(),'tpacf_decide')
    (dest/'helper-diff.txt').write_text('\n'.join(difflib.unified_diff(fa.splitlines(),fb.splitlines(),fromfile='template',tofile='darm'))+'\n')
    G.dump(dest/'equivalence.json',results);G.dump(dest/'structure.json',stats)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--canonical-tail',action='store_true',help='also build a TPACF-only tail-normalization diagnostic');args=ap.parse_args();base=args.base.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=False)
    assert json.loads((base/'plan.json').read_text())['case']=='tpacf'
    base_arts=json.loads((base/'artifacts.json').read_text());arts={'native':base_arts['native'],'original':base_arts['original']}
    G.dump(out/'plan.json',dict(case='tpacf',base=str(base),study='legacy group2 vs DARM pair fusion + precomputed pairmax',partition=[[i,i+1] for i in range(0,32,2)],unroll='original pragmas',fmad=False,validation_fixtures=['isotropic','edges','wide','unordered','nonfinite_bounds'],primary_comparison=['template_helper_max','darm_helper_max'],diagnostics=['legacy_direct_max','darm_helper_or'],timing_scope='kernel-only; pair-bound preprocessing and upload excluded explicitly'))
    def finish(d,module,name,aux=False):
        G.command(d,'post',[G.T/'opt',module,'-always-inline','-O3','-internalize','-internalize-public-api-list=ACFKernel,ACFKernelSymm,binbounds,pairbounds','-globaldce','-verify','-S','-o',d/'post.ll'])
        G.command(d,'llc',[G.T/'llc',d/'post.ll','-O3','-march=nvptx64','-mcpu=sm_80','-o',d/'kernel.ptx'])
        G.command(d,'ptxas',[G.CUDA/'ptxas','-O3','--fmad=false','-arch=sm_86','-v',d/'kernel.ptx','-o',d/'kernel.cubin'])
        arts[name]=dict(path=str(d/'kernel.cubin'),sha256=G.sha(d/'kernel.cubin'),aux_constants={'pairbounds':'tpacf_pair_max'} if aux else {})
        G.dump(out/'artifacts.json',arts)
    # Reconstruct the legacy formula and verify it against the actual archived source.
    chain='\n'.join((('if' if i==0 else 'else if')+f'(temp < pairbounds[{i//2}])' if i<30 else 'else')+f' temp2 += ((temp < binbounds[{30-i}] ? {(31-i)*4}u : {(30-i)*4}u) << (j<<3));' for i in range(0,32,2))
    raw=(HERE/'ACF_kernel.cu').read_text();reconstructed=PREFIX+'extern "C" {\n'+re.sub(PATTERN,lambda _:chain,raw,flags=re.S).replace('__device__ __constant__ double binbounds[NUMBINS-1];','__device__ __constant__ double binbounds[NUMBINS-1];\n__device__ __constant__ double pairbounds[15];')+'\n}\n'
    legacy=(HERE/'legacy/group2_max.cu').read_text();normalize=lambda s:re.sub(r'\s+','',s)
    assert normalize(reconstructed)==normalize(legacy),'legacy source mismatch beyond whitespace'
    d=out/'legacy_direct_max';d.mkdir();ir=G.compile_src(d,'source',legacy,'tpacf');finish(d,ir,'legacy_direct_max',True)
    gen=DARMGenerator(cleanup='minimal');work=out/'pairs';work.mkdir();gen.configure(work,TPACF(),dict(hp=HP,schema=dict(n=32,total=32,arg='temp',guard_args='double temp',args=ARGS,passed=PASSED,ret='void',target='tpacf_decide')))
    groups=[];pairs=[]
    for i in range(0,32,2):
        a,b=[json.loads((base/'tpacf/leaves'/str(j)/'group.json').read_text()) for j in [i,i+1]]
        g=gen.merge('tpacf',a,b,work/f'pair-{i}-{i+1}');assert g is not None,(i,i+1);groups.append(g)
        f=G.function(Path(g['module']).read_text(),g['name']);pairs.append(dict(interval=[i,i+1],shifts=len(re.findall(r'= shl ',f)),adds=len(re.findall(r'= add ',f)),selects=len(re.findall(r'= select ',f))))
    G.dump(out/'pair-summary.json',pairs)
    for name,template,maxbound in [('template_helper_max',True,True),('darm_helper_max',False,True),('darm_helper_or',False,False)]:
        d=out/name;d.mkdir();s=HP+(PAIR_DECL if maxbound else '')
        if not template:
            for g in groups:s+=f'extern "C" __device__ void {g["name"]}({ARGS});\n'
        s+=f'extern "C" __device__ __attribute__((always_inline)) void tpacf_decide({ARGS}) {{\n'
        for i,g in enumerate(groups):
            lo,hi=g['lo'],g['hi'];cond=(f'temp < pairbounds[{i}]' if maxbound else interval_predicate(lo,hi)) if hi<31 else None
            s+=(('if' if i==0 else 'else if')+' ('+cond+') ' if cond else '')+'{\n'
            if template:s+=f'*out = accum + ((temp < binbounds[{30-lo}] ? {(31-lo)*4}u : {(31-hi)*4}u) << shift);\n'
            else:s+=f'{g["name"]}({PASSED});\n'
            s+='return; }\n'
        s+='}\n';ir=G.compile_src(d,'dispatch',s,'tpacf');modules=[] if template else [g['module'] for g in groups]
        G.command(d,'link',[G.T/'llvm-link',base/'prepared.ll',ir,*modules,'-S','-o',d/'linked.ll'])
        G.command(d,'helper',[G.T/'opt',d/'linked.ll','-internalize','-internalize-public-api-list=tpacf_decide,binbounds,pairbounds','-globaldce','-always-inline','-O3','-verify','-S','-o',d/'helper.ll'])
        G.command(d,'helper-strip',[G.T/'opt',d/'helper.ll','-strip','-S','-o',d/'helper-normalized.ll'])
        finish(d,d/'linked.ll',name,maxbound)
    G.dump(out/'completion.json',dict(build_complete=True,gpu_validated=False))
    compare_outputs(out)
    if args.canonical_tail:canonical_tail_diagnostic(out)

if __name__=='__main__':main()
