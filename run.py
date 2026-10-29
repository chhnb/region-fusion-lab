#!/usr/bin/env python3
"""CLI; outputs must be new directories. No original experiment outputs imported."""
from pathlib import Path
import argparse,json,shutil,sys
from fusion.search import greedy
from fusion.scoring import make_scorer
from fusion.enumeration import exhaustive,counts
from fusion.tree import parse_choices
ROOT=Path(__file__).resolve().parent

def dump(path,obj):path.write_text(json.dumps(obj,indent=2)+'\n')
def main():
    ap=argparse.ArgumentParser();sub=ap.add_subparsers(dest='command',required=True)
    p=sub.add_parser('tree');p.add_argument('source');p.add_argument('--out',required=True)
    p=sub.add_parser('count');p.add_argument('n',type=int)
    p=sub.add_parser('build');p.add_argument('--case',default='srad4',help='case name or module:factory');p.add_argument('--out',required=True);p.add_argument('--score',default='similarity',help='similarity, net-cost, or module:factory');p.add_argument('--max-merges',type=int,default=32);p.add_argument('--threshold',type=float,default=0.);p.add_argument('--max-histories',type=int,default=10000);p.add_argument('--skip-enumeration',action='store_true')
    p.add_argument('--merge-cleanup',choices=['minimal','o3'],default='minimal');p.add_argument('--first',type=int,default=0);p.add_argument('--last',type=int);p.add_argument('--generator',default='darm');p.add_argument('--baselines',default='bf,darm')
    args=ap.parse_args()
    if args.command=='count':print(json.dumps(counts(args.n),indent=2));return
    out=Path(args.out).resolve()
    if args.command=='tree':
        if out.exists():raise ValueError('output already exists')
        dump(out,[c.to_dict() for c in parse_choices(Path(args.source).read_text())]);return
    from cases.registry import load
    case=load(args.case);last=case.option_count-1 if args.last is None else args.last
    if not 0<=args.first<=last<case.option_count:ap.error('invalid region interval')
    if not args.skip_enumeration and counts(last-args.first+1)['chronological_histories']>args.max_histories:ap.error('enumeration exceeds budget; restrict --first/--last or use --skip-enumeration')
    out.mkdir(parents=True,exist_ok=False)
    dump(out/'plan.json',dict(case=args.case,merge_cleanup=args.merge_cleanup,interval=[args.first,last],generator=args.generator,baselines=args.baselines.split(',') if args.baselines else [],scorer=args.score,threshold=args.threshold,max_merges=args.max_merges,queue='global score-first; no depth priority; full refresh',enumeration='strict required interval completion; all adjacent chronological schedules; no score pruning',generation='compositional outlined case adapter; full-function contextual adapter remains future work',measure='separate GPU command validates first; independent seeded balanced contexts',source_provenance=json.loads((ROOT/'provenance.json').read_text())))
    from backends.registry import generator,method
    from fusion.session import CompositionalSession
    from experiments.baselines import build_baselines
    backend=CompositionalSession(out,make_scorer(args.score),case,generator(args.generator,cleanup=args.merge_cleanup),args.first,last);backend.emit(backend.initial,'unmerged')
    if getattr(case,'baseline_scope','kernel')=='helper':backend.artifacts['original']=dict(backend.artifacts['unmerged'],role='matched common helper control')
    state,trace=greedy(backend,backend.initial,args.max_merges,args.threshold);backend.emit(state,'greedy');dump(out/'greedy-trace.json',trace)
    print('GREEDY',backend.key(state),flush=True)
    if not args.skip_enumeration:
        report,states=exhaustive(backend,args.max_histories);dump(out/'enumeration.json',report)
        assert backend.key(state) in states,'greedy state missing from exhaustive feasible set'
        print('ENUMERATION',report['expected'],report['distinct_feasible_forests'],flush=True)
    if args.baselines:build_baselines(backend,[method(n) for n in args.baselines.split(',')])
    backend.save();dump(out/'completion.json',dict(build_complete=True,gpu_validated=False,greedy=backend.key(state),artifacts=len(backend.artifacts)))
if __name__=='__main__':main()
