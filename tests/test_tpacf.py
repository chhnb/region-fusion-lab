import unittest,re,subprocess,sys,tempfile
from pathlib import Path
from cases.registry import load
from cases.tpacf.prepare import classification_source,PATTERN
from fusion.search import MergeHistory
from fusion.enumeration import exhaustive

class TPACFTests(unittest.TestCase):
    def test_32way_structure_and_three_sites(self):
        case=load('tpacf');tree=case.region_tree(None)
        self.assertEqual(len(tree),1);self.assertEqual(len(tree[0]['arms']),32)
        raw=(Path(__file__).resolve().parents[1]/'cases/tpacf/ACF_kernel.cu').read_text()
        chains=re.findall(PATTERN,raw,re.S);self.assertEqual(len(chains),3)
        for text in chains:
            matches=re.findall(r'binbounds\[(\d+)\]\)\s*temp2\s*\+=\s*\((\d+)<<',text)
            self.assertEqual([(int(a),int(b)) for a,b in matches],[(i,(i+1)*4) for i in range(30,-1,-1)])
    def test_full_enumeration_rejected_before_build(self):
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'not-created'
            result=subprocess.run([sys.executable,str(root/'run.py'),'build','--case','tpacf','--out',str(out)],capture_output=True,text=True)
            self.assertEqual(result.returncode,2)
            self.assertIn('enumeration exceeds budget',result.stderr)
            self.assertFalse(out.exists())
    def test_scoped_enumeration_preserves_surrounding_options(self):
        class B:
            first=2;last=5;initial=tuple(MergeHistory(i,i) for i in range(8))
            def key(self,s):return '|'.join(t.key for t in s)
            def group(self,t):
                assert 2<=t.lo<=t.hi<=5
                return {}
            def emit(self,s,name):
                assert [t.key for t in s[:2]]==['0','1']
                assert [t.key for t in s[-2:]]==['6','7']
        report,_=exhaustive(B());self.assertEqual(report['scope'],[2,5]);self.assertEqual(report['distinct_feasible_forests'],14);self.assertEqual(len(report['records']),16)

if __name__=='__main__':unittest.main()
