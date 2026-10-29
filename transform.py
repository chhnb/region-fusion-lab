#!/usr/bin/env python3
"""Run BF/DaRM from one commonly prepared input IR, without a case adapter."""
from pathlib import Path
import argparse,json,resource
from experiments.ir_pipeline import transform_all

def main():
 resource.setrlimit(resource.RLIMIT_CORE,(0,0))
 p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--function',required=True);p.add_argument('--methods',default='bf,darm');p.add_argument('--out',type=Path,required=True);p.add_argument('--lower-switch',action='store_true');a=p.parse_args()
 names=tuple(a.methods.split(','));assert len(set(names))==len(names) and all(n in ['bf','darm'] for n in names)
 rows=transform_all(a.input,a.out,a.function,names,a.lower_switch);print(json.dumps(rows,indent=2))
 if any(r['status']=='failed' for r in rows.values()):raise SystemExit(2)
if __name__=='__main__':main()
