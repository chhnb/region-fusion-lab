#!/usr/bin/env python3
"""Recompile migrated CFMelder and link against local LLVM12 bootstrap libraries.
No original checkout paths, Ninja invocation, or hash stamps are needed.
"""
from pathlib import Path
import json,subprocess,concurrent.futures,shutil
D=Path(__file__).resolve().parent;OUT=D/'build';BOOT=D/'bootstrap';SOURCE=D.parents[1]/'third_party/darm'
def run(label,cmd):
 p=subprocess.run(list(map(str,cmd)),cwd=BOOT,capture_output=True,text=True,timeout=600)
 (OUT/(label+'.json')).write_text(json.dumps(dict(command=list(map(str,cmd)),returncode=p.returncode,stdout=p.stdout,stderr=p.stderr),indent=2))
 if p.returncode:raise RuntimeError(label+'\n'+p.stderr[-3000:])
def main():
 if not (SOURCE/'llvm/lib/Transforms/CFMelder').is_dir():raise RuntimeError('Initialize submodule: git submodule update --init --recursive')
 OUT.mkdir(exist_ok=True)
 recipe=json.loads((D/'build-recipe.json').read_text().replace(str(D/'source'),str(SOURCE)))
 def compile_one(ent):
  cmd=ent['command'].copy();name=Path(ent['file']).name;cmd[cmd.index('-o')+1]=str(OUT/(name+'.o'));run('compile-'+name,cmd);return OUT/(name+'.o')
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:objects=list(pool.map(compile_one,recipe['compile']))
 archive=OUT/'libLLVMCFMelder.a'
 if archive.exists():archive.unlink()
 run('archive',['ar','rcs',archive,*objects]);cmd=recipe['link'].copy();cmd[cmd.index('-o')+1]=str(OUT/'opt-darm');cmd=[str(archive) if c=='lib/libLLVMCFMelder.a' else c for c in cmd];run('link',cmd)
 active=D/'bin/opt-darm';active.parent.mkdir(exist_ok=True);shutil.copy2(OUT/'opt-darm',active)
 opt=BOOT/'bin/opt'
 if opt.is_symlink() or opt.exists():opt.unlink()
 opt.symlink_to('../../bin/opt-darm')
 (OUT/'opt-darm').unlink()
 run('version',[D/'bin/opt-darm','--version']);print(D/'bin/opt-darm',flush=True)
if __name__=='__main__':main()
