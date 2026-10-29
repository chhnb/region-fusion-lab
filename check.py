#!/usr/bin/env python3
"""Small default check; expensive compiler regressions require an explicit suite."""
from pathlib import Path
import argparse,subprocess,sys
ROOT=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('suite',nargs='?',choices=['unit','llvm'],default='unit');p.add_argument('--out',type=Path);a=p.parse_args()
if a.suite=='unit':
 if a.out:p.error('--out is only used by llvm')
 cmd=[sys.executable,'-m','unittest','discover','-s','tests','-q']
else:
 if a.out is None:p.error('llvm requires --out NEW_DIRECTORY')
 cmd=[sys.executable,str(ROOT/'toolchains/llvm12/test_migration.py'),'--out',str(a.out.resolve())]
raise SystemExit(subprocess.call(cmd,cwd=ROOT))
