"""One common IR preparation, independent method copies, one common cleanup.
No input hashes. Equality is enforced by construction and direct byte checks.
"""
from pathlib import Path
import shutil,json
from vendor import engine as G
from backends.registry import method

def transform_all(source,out,function,methods=('bf','darm'),lower_switch=False):
 out=Path(out);out.mkdir(parents=True,exist_ok=False)
 shutil.copyfile(source,out/'source.ll')
 G.command(out,'prepare',[G.T/'opt',out/'source.ll',*(['-lowerswitch'] if lower_switch else []),'-verify','-S','-o',out/'initial.ll'])
 initial=(out/'initial.ll').read_bytes();(out/'initial.ll').chmod(0o444)
 rows={}
 for name in ('original',*methods):
  d=out/name;d.mkdir();shutil.copyfile(out/'initial.ll',d/'input.ll');assert (d/'input.ll').read_bytes()==initial
  try:
   if name=='original':shutil.copyfile(d/'input.ll',d/'meld.ll');melds=0
   else:
    p=method(name).transform(G.OPT,d/'input.ll',function,d);melds=p.stderr.count('Melding entry blocks')
   assert (d/'input.ll').read_bytes()==initial and (out/'initial.ll').read_bytes()==initial,'method modified shared starting IR'
   G.command(d,'post',[G.T/'opt',d/'meld.ll','-O3','-verify','-S','-o',d/'final.ll'])
   rows[name]=dict(status='success',melds=melds,output=str(d/'final.ll'))
  except Exception as e:
   # Do not publish fallback under a successful method name.
   rows[name]=dict(status='failed',error=str(e))
  G.dump(out/'results.json',dict(function=function,common_prepare=['lowerswitch'] if lower_switch else [],common_post=['O3','verify'],methods=rows))
 return rows
