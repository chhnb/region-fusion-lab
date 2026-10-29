#!/usr/bin/env python3
"""Case-independent comparison entry point; case owns inputs and correctness oracle."""
from pathlib import Path
import argparse,json
from cases.registry import load

def main():
    ap=argparse.ArgumentParser();ap.add_argument('run');ap.add_argument('--size',type=int,default=4096);ap.add_argument('--contexts',type=int,default=2);ap.add_argument('--blocks',type=int,default=1);ap.add_argument('--validate-only',action='store_true');args=ap.parse_args()
    run=Path(args.run).resolve();plan=json.loads((run/'plan.json').read_text())
    load(plan['case']).compare(run,args)
if __name__=='__main__':main()
