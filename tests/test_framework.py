import unittest
from fusion.tree import parse_choices,walk,adjacent_pairs
from fusion.search import histories,partitions,greedy,risk_score,MergeHistory
from fusion.enumeration import counts,exhaustive
from fusion.scoring import Similarity,ScoreInput,TrialNetCost
from fusion.cost import Program,UnsupportedCost

class Structure(unittest.TestCase):
    def test_else_if_is_same_level(self):
        s='if(a){A();} else if(b){if(c){B();} else {C();}} else {D();} if(e){E();}'
        cs=parse_choices(s);self.assertEqual(len(cs),2);self.assertEqual(len(cs[0].arms),3)
        inner=cs[0].arms[1].children[0];self.assertEqual(inner.depth,1);self.assertEqual(len(inner.arms),2)
    def test_32_way_not_binary(self):
        s=' '.join(('if' if i==0 else 'else if')+f'(x=={i}){{ f{i}(); }}' for i in range(31))+' else { rest(); }'
        tree=parse_choices(s);self.assertEqual(len(tree[0].arms),32);self.assertEqual(len(list(walk(tree))),1)
    def test_uniform_parent_does_not_hide_inner(self):
        cs=parse_choices('if(a){if(b){x();}else{y();}}else{z();}')
        cs[0].uniformity='proven_uniform';pairs=list(adjacent_pairs(cs))
        self.assertEqual(len(pairs),1);self.assertEqual(pairs[0]['depth'],1)
    def test_adjacent_not_arbitrary(self):
        cs=parse_choices('if(a){x();}else if(b){y();}else{z();}')
        self.assertEqual(len(list(adjacent_pairs(cs))),2)
    def test_unbraced_rejected(self):
        with self.assertRaises(ValueError):parse_choices('if(a) f(); else {g();}')

class Enumeration(unittest.TestCase):
    def test_partition_completion_and_orders(self):
        total=[]
        for _,intervals in partitions(4):
            hs=list(histories(intervals));total+=hs
            for forest,steps in hs:
                self.assertEqual([(t.lo,t.hi) for t in forest],intervals)
                self.assertEqual(len(steps),4-len(intervals))
        self.assertEqual(len(total),16);self.assertEqual(len({tuple(t.key for t in f) for f,s in total}),14)
        full=list(histories([(0,3)]));self.assertEqual(len(full),6);self.assertEqual(len({f[0].key for f,s in full}),5)
    def test_forbidden_partial_success(self):
        class B:
            from fusion.search import MergeHistory
            initial=tuple(MergeHistory(i,i) for i in range(3))
            def key(self,s):return '|'.join(t.key for t in s)
            def group(self,t):return None if t.hi-t.lo==2 else {}
            def emit(self,state,name):pass
        report,_=exhaustive(B());full=[r for r in report['records'] if r['partition_mask']==0]
        self.assertTrue(all(r['status']=='infeasible' and 'artifact' not in r for r in full))
    def test_budget(self):
        self.assertEqual(counts(9)['distinct_history_forests'],4862)
        self.assertEqual(counts(9)['chronological_histories'],109601)

class Queue(unittest.TestCase):
    def test_depth_does_not_override_score_and_negative_refreshed(self):
        class B:
            def pairs(self,state):return [x for x in ['outer','inner','other'] if x not in state]
            def key(self,state):return ','.join(state)
            def evaluate(self,state,pair,version):
                score={'outer':10,'inner':8,'other':-1 if not state else 15}[pair]
                return dict(id=pair,version=version,status='valid',score=score,depth={'outer':0,'inner':2,'other':1}[pair])
            def commit(self,state,c):return state+[c['id']]
        state,trace=greedy(B(),[]);self.assertEqual(state,['outer','other','inner'])
    def test_budget_not_optimum(self):
        class B:
            def pairs(self,s):return [0]
            def key(self,s):return str(s)
            def evaluate(self,s,p,v):return dict(id='p',version=v,status='valid',score=1)
            def commit(self,s,c):return s+1
        state,trace=greedy(B(),0,max_merges=2);self.assertEqual(state,2);self.assertEqual(trace[-1]['stop'],'budget')

class Scoring(unittest.TestCase):
    def test_risk_formula(self):self.assertEqual(risk_score([-2,-2,20]),3.5)
    def test_unavailable_is_not_zero(self):self.assertIsNone(TrialNetCost().score(ScoreInput({},{})).value)
    def test_ir_path_union(self):
        ir='''define void @f(i32 %tx, i32 %ty) {
entry:
 %c = icmp eq i32 %tx, 0
 br i1 %c, label %left, label %right
left:
 %a = add i32 %ty, 1
 br label %end
right:
 %b = mul i32 %ty, 2
 br label %end
end:
 ret void
}'''
        p=Program(ir,'f');self.assertEqual(p.estimate([(0,0)])[0],4);self.assertEqual(p.estimate([(0,0),(1,0)])[0],6)

if __name__=='__main__':unittest.main()
