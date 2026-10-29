#!/usr/bin/env python3
"""Validate first, then randomized balanced GPU comparison, separate from search.
No timed score feedback: algorithm scoring never reads performance samples.
"""
from pathlib import Path
import argparse,json,random,math,statistics,subprocess
import numpy as np

def dump(p,o):p.write_text(json.dumps(o,indent=2)+'\n')
def compare(run,options,drv,stage):
    args=options
    d=Path(run).resolve();out=d/'comparison';out.mkdir(exist_ok=False);drv.D=d
    artifacts=json.loads((d/'artifacts.json').read_text());seen={};aliases={};names=[]
    # Keep baseline names if duplicate with enumerated outputs; map ALL aliases.
    ordered=[n for n in ['original','unmerged','greedy','bf','darm','helper_bf','helper_darm'] if n in artifacts]+[n for n in artifacts if n not in ['original','unmerged','greedy','bf','darm','helper_bf','helper_darm','native']]
    for n in ordered:
        sha=artifacts[n]['sha256']
        if sha in seen:aliases[n]=seen[sha]
        else:seen[sha]=n;names.append(n)
    dump(out/'plan.json',dict(names=names,aliases=aliases,input=f'artifact{args.size},seed7,ROI0..127,lambda0.5',contexts=args.contexts,blocks=args.blocks,seed=20261029,mode='single case-selected kernel; reset input outside timing; not end-to-end',scoring_independent=True,statistics='paired geometric ratios per round; all samples retained; screening comparison, not independent confirmation of fastest enumerated variant'))
    samples=[];checks=[];telemetry=[]
    for context in range(args.contexts):
        k=drv.GPU()
        try:
            fixtures=[(32,48,'default'),(64,64,'gradient'),(32,32,'constant'),(args.size,args.size,'default')] if context==0 else [(args.size,args.size,'default')]
            for nr,nc,kind in fixtures:
                j,q=drv.image(nr,nc,kind);ref,data=k.prepare(j,q)
                for n in names:k.launch(n,stage,ref)
                checks.append(dict(context=context,rows=nr,cols=nc,kind=kind,variants=names,CPU_NVCC_bitexact=True));dump(out/'validation.json',checks)
            if getattr(args,'validate_only',False):continue
            # Current state is the declared timing fixture. All variants revalidated above.
            for n in names:k.launch(n,stage,ref)
            for block in range(args.blocks):
                telemetry.append(dict(context=context,block=block,value=subprocess.check_output(['nvidia-smi','--query-gpu=clocks.sm,clocks.mem,temperature.gpu','--format=csv,noheader'],text=True).strip()));order=names.copy();random.Random(20261029+context*100+block).shuffle(order)
                for rotation in range(len(names)):
                    for position,n in enumerate(order[rotation:]+order[:rotation]):
                        ms,_=k.launch(n,stage,ref);samples.append(dict(context=context,block=block,rotation=rotation,position=position,name=n,ms=ms))
                dump(out/'samples.json',samples);dump(out/'telemetry.json',telemetry);print('MEASURED',context,block,flush=True)
        finally:k.close()
    if getattr(args,'validate_only',False):
        dump(out/'completion.json',dict(validated=True,timing_performed=False,fixtures=len(checks)))
        completion=json.loads((d/'completion.json').read_text());completion.update(gpu_validated=True,gpu_validation_receipt=str(out/'completion.json'));dump(d/'completion.json',completion)
        print('VALIDATION_PASS',len(names),'variants',len(checks),'fixtures');return
    result={}
    for name in names:
        rr=[r for r in samples if r['name']==name];record={'median_ms':statistics.median(r['ms'] for r in rr),'samples':len(rr)}
        for control in ['original','unmerged']:
            control=aliases.get(control,control);cs={(r['context'],r['block'],r['rotation']):r['ms'] for r in samples if r['name']==control};z=[(r['context'],math.log(cs[r['context'],r['block'],r['rotation']]/r['ms'])) for r in rr]
            record['vs_'+control]={'speedup':math.exp(statistics.mean(v for c,v in z)),'contexts':[math.exp(statistics.mean(v for c,v in z if c==ctx)) for ctx in range(args.contexts)]}
        result[name]=record
    dump(out/'results.json',dict(measured=result,aliases=aliases));dump(out/'completion.json',dict(validated=True,samples=len(samples),timing_scope='case-selected kernel only'))
    completion=json.loads((d/'completion.json').read_text());completion.update(gpu_validated=True,gpu_validation_receipt=str(out/'completion.json'));dump(d/'completion.json',completion)
    print(json.dumps({n:r['vs_original'] for n,r in result.items()},indent=2))
