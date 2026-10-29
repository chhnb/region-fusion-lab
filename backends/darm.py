"""DaRM transformation engine, independent of benchmark identity and search policy."""
from vendor import engine as G
from pathlib import Path
import shutil

class DARMGenerator:
    name='darm-pair-generator'
    def configure(self,out,case,prepared):
        # Legacy engine bindings are process-global: one session per process.
        out=Path(out);(out/'engine').mkdir(exist_ok=True)
        shutil.copy2(G.OPT,out/'engine/opt-adjacent')
        self.bindings=(out,case.case_key,prepared['schema'],prepared['hp'])
    def merge(self,case_key,left,right,out):
        root,key,schema,prefix=self.bindings
        if case_key!=key:raise ValueError('generator/case mismatch')
        G.O=root;G.SPECS={key:schema};G.prefix=lambda _:prefix
        return G.merge(case_key,left,right,out)

class DARM:
    name='darm'
    extra_flags=()
    def transform(self,engine,source,target,out):
        return G.command(out,'meld',[engine,source,'-cfmelder',
            '-cf-merging-similarity-threshold=0.2',
            '-run-cfmelding-on-function='+target,*self.extra_flags,
            '-verify','-S','-o',out/'meld.ll'])
