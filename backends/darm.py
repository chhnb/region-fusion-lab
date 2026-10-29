"""DaRM transformation engine, independent of benchmark identity and search policy."""
from vendor import engine as G
from pathlib import Path
import shutil

class DARMGenerator:
    name='darm-pair-generator'
    def __init__(self,cleanup='minimal'):
        if cleanup not in ('minimal','o3'):raise ValueError(cleanup)
        self.cleanup=cleanup
    def configure(self,out,case,prepared):
        # Legacy engine bindings are process-global: one session per process.
        out=Path(out);(out/'engine').mkdir(exist_ok=True)
        shutil.copy2(G.OPT,out/'engine/opt-adjacent')
        self.case=case
        self.bindings=(out,case.case_key,prepared['schema'],prepared['hp'])
    def merge(self,case_key,left,right,out):
        root,key,schema,prefix=self.bindings
        if case_key!=key:raise ValueError('generator/case mismatch')
        G.O=root;G.SPECS={key:schema};G.prefix=lambda _:prefix
        guard=None
        if hasattr(self.case,'interval_predicate'):
            lo,hi=left['lo'],left['hi'];condition=self.case.interval_predicate(lo,hi)
            if condition is None:raise ValueError('left group cannot contain unconditional fallback')
            name=f'guard_{lo}_{hi}';d=root/key/'guards'/f'{lo}_{hi}'
            if not (d/'guard.ll').exists():
                d.mkdir(parents=True,exist_ok=True)
                G.compile_src(d,'guard',prefix+f'extern "C" __device__ __attribute__((noinline)) bool {name}({schema["guard_args"]}) {{return {condition};}}\n',key)
                G.dump(d/'context.json',dict(interval=[lo,hi],condition=condition,entry_contract='enclosing first-match dispatch excludes all earlier original options'))
            guard=dict(name=name,module=d/'guard.ll')
        return G.merge(case_key,left,right,out,guard=guard,cleanup_mode=self.cleanup)

class DARM:
    name='darm'
    extra_flags=()
    def transform(self,engine,source,target,out):
        return G.command(out,'meld',[engine,source,'-cfmelder',
            '-cf-merging-similarity-threshold=0.2',
            '-run-cfmelding-on-function='+target,*self.extra_flags,
            '-verify','-S','-o',out/'meld.ll'])
