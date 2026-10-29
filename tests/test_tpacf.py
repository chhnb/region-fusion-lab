import unittest,re,subprocess,sys,tempfile
from pathlib import Path
from cases.registry import load
from cases.tpacf.prepare import classification_source,PATTERN,interval_predicate
from fusion.search import MergeHistory,partitions,histories
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
    def test_interval_guards_do_not_repeat_excluded_prefix(self):
        self.assertEqual(interval_predicate(4,4),'(temp < binbounds[26])')
        self.assertEqual(interval_predicate(6,6),'(temp < binbounds[24])')
        self.assertEqual(interval_predicate(4,5),'(temp < binbounds[26]) || (temp < binbounds[25])')
        self.assertIsNone(interval_predicate(30,31))
    def test_guard_semantics_for_all_scoped_forests_and_overlapping_predicates(self):
        # Arbitrary Boolean assignments, not monotone thresholds. Earlier true
        # paths must win; helpers are only entered under their interval contract.
        def shifted(t):
            return MergeHistory(t.lo+4,t.hi+4,shifted(t.left),shifted(t.right)) if t.left else MergeHistory(t.lo+4,t.hi+4)
        def pred(t,bits):
            expr=interval_predicate(t.lo,t.hi)
            return True if expr is None else any(bits[30-int(k)] for k in re.findall(r'binbounds\[(\d+)\]',expr))
        def execute(t,bits):
            if not t.left:return t.lo
            return execute(t.left if pred(t.left,bits) else t.right,bits)
        forests={}
        for _,intervals in partitions(4):
            for forest,_ in histories(intervals):forests[tuple(t.key for t in forest)]=tuple(shifted(t) for t in forest)
        for mask in range(256):
            for suffix in [False,True]:
                bits=[bool(mask&(1<<i)) for i in range(8)]+[suffix]+[False]*22
                expected=next((i for i,b in enumerate(bits) if b),31)
                for forest in forests.values():
                    groups=tuple(MergeHistory(i,i) for i in range(4))+forest+tuple(MergeHistory(i,i) for i in range(8,32))
                    chosen=next(t for t in groups if pred(t,bits))
                    self.assertEqual(execute(chosen,bits),expected)
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
