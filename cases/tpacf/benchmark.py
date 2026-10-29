"""TPACF validation and optional balanced timings. No official catalog claim."""
from pathlib import Path
import json,random,math,statistics,subprocess
import numpy as np
from .gpu import GPU,inputs,oracle,N

def dump(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def compare(run,args):
    if args.size!=N:raise ValueError('TPACF preserves LOG2_GRID_SIZE14: --size must be16384; small grids are included in validation')
    d=Path(run);out=d/'comparison';out.mkdir(exist_ok=False);arts=json.loads((d/'artifacts.json').read_text())
    names=[];aliases={};seen={}
    for name in ['original','unmerged','greedy','bf','darm','source_original']+[n for n in arts if n.startswith('enum')]:
        if name not in arts:continue
        identity=arts[name]['sha256']
        if identity in seen:aliases[name]=seen[identity]
        else:seen[identity]=name;names.append(name)
    kernels=['ACFKernel','ACFKernelSymm'];validate_only=getattr(args,'validate_only',False)
    dump(out/'plan.json',dict(names=names,aliases=aliases,input='seed20261021 synthetic isotropic points, source-style boundary configuration; NOT official catalog',roles={'original':'common prepared unmerged control','source_original':'different preparation diagnostic, not the primary algorithm baseline'},points=N,grid=[128,128],block=128,shared=3072,kernels=kernels,scope='kernel only; no histogram/end-to-end timing',mode='validation' if validate_only else 'single-launch screening',contexts=args.contexts,blocks=args.blocks,all_samples_retained=True))
    checks=[];samples=[];telemetry=[]
    for ctx in range(1 if validate_only else args.contexts):
        gpu=GPU(d,names)
        try:
            if ctx==0:
                for fixture in ['isotropic','edges','wide','unordered']:
                    x,y,b=inputs(fixture);gpu.configure(x,y,b)
                    for kernel in kernels:
                        expected=oracle(x[:128],x[:128] if kernel.endswith('Symm') else y[:128],b,kernel.endswith('Symm'))
                        for name in ['native',*names]:
                            gpu.clear();gpu.launch(name,kernel,1);actual=gpu.read()
                            assert np.array_equal(actual[:32,:128],expected),(fixture,name,kernel,'CPU mismatch')
                            assert np.all(actual[32:]==0xdeadbeef) and np.all(actual[:32,128:]==0xdeadbeef),(fixture,name,kernel,'unlaunched output overwritten')
                        checks.append(dict(fixture=fixture,kernel=kernel,CPU_exact=True,guards=True,variants=['native',*names]));dump(out/'validation.json',checks)
                    print('VALIDATED',fixture,flush=True)
            x,y,b=inputs();gpu.configure(x,y,b)
            for kernel in kernels:
                gpu.launch('native',kernel);reference=gpu.read()
                for name in names:
                    gpu.launch(name,kernel);assert np.array_equal(gpu.read(),reference),(name,kernel,'full-grid NVCC mismatch')
                checks.append(dict(context=ctx,fixture='full16384',kernel=kernel,NVCC_exact=True,variants=names));dump(out/'validation.json',checks)
                if validate_only:continue
                for block in range(args.blocks):
                    telemetry.append(dict(context=ctx,kernel=kernel,block=block,value=subprocess.check_output(['nvidia-smi','--query-gpu=clocks.sm,clocks.mem,temperature.gpu','--format=csv,noheader'],text=True).strip()))
                    order=names.copy();random.Random(20261029+ctx*100+block).shuffle(order)
                    for rotation in range(len(names)):
                        for position,name in enumerate(order[rotation:]+order[:rotation]):samples.append(dict(context=ctx,kernel=kernel,block=block,rotation=rotation,position=position,name=name,ms=gpu.launch(name,kernel)))
                    for name in names:
                        gpu.launch(name,kernel);assert np.array_equal(gpu.read(),reference),(name,kernel,'post-measure mismatch')
                    dump(out/'samples.json',samples);dump(out/'telemetry.json',telemetry)
        finally:gpu.close()
    if samples:
        rows={}
        for kernel in kernels:
            rr=[r for r in samples if r['kernel']==kernel];ctrl={(r['context'],r['block'],r['rotation']):r['ms'] for r in rr if r['name']=='original'};rows[kernel]={}
            for name in names:
                z=[r for r in rr if r['name']==name];ratios=[math.log(ctrl[r['context'],r['block'],r['rotation']]/r['ms']) for r in z]
                rows[kernel][name]=dict(median_ms=statistics.median(r['ms'] for r in z),speedup=math.exp(statistics.mean(ratios)),samples=len(z))
        dump(out/'results.json',dict(measured=rows,aliases=aliases))
    dump(out/'completion.json',dict(validated=True,records=len(checks),samples=len(samples),timing_performed=bool(samples)))
    receipt=json.loads((d/'completion.json').read_text());receipt.update(gpu_validated=True,gpu_validation_receipt=str(out/'completion.json'));dump(d/'completion.json',receipt)
    print('TPACF_PASS',len(names),'distinct variants',len(checks),'checks',len(samples),'samples')
