"""State-independent search policies. Backend owns semantics, versions and legality."""
from dataclasses import dataclass
from itertools import product
import heapq

@dataclass(frozen=True)
class MergeHistory:
    """Binary pair-operation HISTORY; never the source multiway region tree."""
    lo:int
    hi:int
    left:object=None
    right:object=None
    @property
    def key(self):return str(self.lo) if self.left is None else f'({self.left.key},{self.right.key})'
    def join(self,other):
        assert self.hi+1==other.lo
        return MergeHistory(self.lo,other.hi,self,other)

def partitions(n):
    if n<1:raise ValueError('n must be positive')
    for mask in range(1<<(n-1)):
        start=0;groups=[]
        for i in range(n-1):
            if mask&(1<<i):groups.append((start,i));start=i+1
        yield mask,groups+[(start,n-1)]

def trees(lo,hi):
    if lo==hi:yield MergeHistory(lo,hi);return
    for k in range(lo,hi):
        for a,b in product(trees(lo,k),trees(k+1,hi)):yield a.join(b)

def histories(intervals):
    """Every adjacent chronological merge schedule; NEVER stop partially merged.
    Disjoint operation permutations remain distinct histories.
    """
    active=tuple(MergeHistory(i,i) for a,b in intervals for i in range(a,b+1))
    def visit(state,steps):
        if len(state)==len(intervals):
            assert [(t.lo,t.hi) for t in state]==list(intervals)
            yield state,steps;return
        for i,(a,b) in enumerate(zip(state,state[1:])):
            if any(lo<=a.lo and b.hi<=hi for lo,hi in intervals):
                t=a.join(b)
                yield from visit(state[:i]+(t,)+state[i+2:],steps+((a.key,b.key,t.key),))
    yield from visit(active,())

def risk_score(gains,weights=None,risk=.25,frequency=1.):
    if not gains:raise ValueError('empty scenarios')
    if not 0<=risk<=1 or frequency<0:raise ValueError('invalid risk/frequency')
    weights=[1/len(gains)]*len(gains) if weights is None else weights
    if len(weights)!=len(gains) or any(x<0 for x in weights) or abs(sum(weights)-1)>1e-9:raise ValueError('invalid weights')
    return frequency*((1-risk)*sum(w*g for w,g in zip(weights,gains))+risk*min(gains))

def greedy(backend,state,max_merges=32,threshold=0.):
    """Reference mode: rebuild ALL candidates (including rejected/negative) every round.
    Candidate identity includes owner Choice: adapters may expose nested choices.
    Full refresh is the conservative dependency invalidation strategy.
    """
    trace=[]
    for version in range(max_merges+1):
        candidates=[backend.evaluate(state,pair,version) for pair in backend.pairs(state)]
        heap=[]
        for index,c in enumerate(candidates):
            if c['status']=='valid' and c['score']>threshold:
                heapq.heappush(heap,(-c['score'],c['id'],index))
        row={'version':version,'state':backend.key(state),'candidates':candidates};trace.append(row)
        if not heap:row['stop']='no_positive_candidate';break
        if version==max_merges:row['stop']='budget';break
        _,_,index=heapq.heappop(heap);chosen=candidates[index]
        assert chosen['version']==version
        state=backend.commit(state,chosen);row['chosen']=chosen['id']
    return state,trace
