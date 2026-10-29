"""Controlled per-merge-cleanup audit; fixed balanced schedule + fixed final partition.
Run as python3 -m cases.tpacf.audit_cleanup --base ... --o3-base ... --out NEW.
Leaves/prepared kernel are reused from a validated interval-local run, not regenerated.
"""
from pathlib import Path
import argparse,json
from vendor import engine as G
from backends.darm import DARMGenerator
from .case import TPACF
from .prepare import HP,ARGS,PASSED,interval_predicate

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base',type=Path,required=True);ap.add_argument('--o3-base',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);args=ap.parse_args()
    base=args.base.resolve();old=args.o3_base.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=False)
    a=json.loads((base/'artifacts.json').read_text());b=json.loads((old/'artifacts.json').read_text())
    assert Path(a['original']['path']).read_bytes()==Path(b['original']['path']).read_bytes(),'baseline preparation differs'
    for run in [base,old]:assert 'local interval' in json.loads((run/'case.json').read_text())['guard_policy']
    assert json.loads((base/'plan.json').read_text())['merge_cleanup']=='minimal'
    assert json.loads((old/'plan.json').read_text()).get('merge_cleanup','o3')=='o3'
    fixed=[(0,7),(8,15),(16,23),(24,27),(28,31)]
    G.dump(out/'plan.json',dict(case='tpacf',purpose='per-merge O3 audit',base=str(base),o3_base=str(old),schedule='balanced adjacent bottom-up; identical in both replays until failure',fixed_partition=fixed,final_optimization='identical O3 for all arms',timing='predeclared arms; no performance-based selection'))
    artifacts={'native':a['native'],'original':a['original'],'greedy_o3':b['greedy'],'greedy_minimal':a['greedy']};summaries={}
    def emit(mode,groups,name):
        d=out/name;d.mkdir();src=HP
        for g in groups:src+=f'extern "C" __device__ void {g["name"]}({ARGS});\n'
        src+=f'extern "C" __device__ __attribute__((always_inline)) void tpacf_decide({ARGS}) {{\n'
        for i,g in enumerate(groups):
            pred=interval_predicate(g['lo'],g['hi'])
            src+=(('if' if i==0 else 'else if')+' ('+pred+') ' if pred else '')+f'{{{g["name"]}({PASSED});return;}}\n'
        src+='}\n';dispatch=G.compile_src(d,'dispatch',src,'tpacf')
        G.command(d,'link',[G.T/'llvm-link',base/'prepared.ll',dispatch,*[g['module'] for g in groups],'-S','-o',d/'linked.ll'])
        G.command(d,'post',[G.T/'opt',d/'linked.ll','-always-inline','-O3','-internalize','-internalize-public-api-list=ACFKernel,ACFKernelSymm,binbounds','-globaldce','-verify','-S','-o',d/'post.ll'])
        G.command(d,'llc',[G.T/'llc',d/'post.ll','-O3','-march=nvptx64','-mcpu=sm_80','-o',d/'kernel.ptx'])
        G.command(d,'ptxas',[G.CUDA/'ptxas','-O3','--fmad=false','-arch=sm_86','-v',d/'kernel.ptx','-o',d/'kernel.cubin'])
        artifacts[name]=dict(path=str(d/'kernel.cubin'),sha256=G.sha(d/'kernel.cubin'),cleanup=mode,groups=[[g['lo'],g['hi']] for g in groups])
    for mode in ['o3','minimal']:
        d=out/mode;d.mkdir();gen=DARMGenerator(cleanup=mode);gen.configure(d,TPACF(),dict(hp=HP,schema=dict(n=32,total=32,arg='temp',guard_args='double temp',args=ARGS,passed=PASSED,ret='void',target='tpacf_decide')))
        active=[json.loads((base/'tpacf/leaves'/str(i)/'group.json').read_text()) for i in range(32)];known={(g['lo'],g['hi']):g for g in active};records=[];failed=False
        while len(active)>1 and not failed:
            new=[]
            for left,right in zip(active[::2],active[1::2]):
                node=d/f'group-{left["lo"]}-{right["hi"]}';score=float(G.score(left,right));g=gen.merge('tpacf',left,right,node)
                records.append(dict(left=[left['lo'],left['hi']],right=[right['lo'],right['hi']],score=score,accepted=g is not None))
                if g is None:failed=True;break
                known[g['lo'],g['hi']]=g;new.append(g)
            active=new
        summaries[mode]=dict(full_merge=not failed,attempts=records)
        emit(mode,[known[span] for span in fixed],'fixed_'+mode)
        if not failed:emit(mode,[known[0,31]],'balanced_full_'+mode)
        G.dump(out/'audit.json',summaries);G.dump(out/'artifacts.json',artifacts)
    G.dump(out/'completion.json',dict(build_complete=True,gpu_validated=False))
if __name__=='__main__':main()
