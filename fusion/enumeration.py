"""Strict interval partition + chronological adjacent merge enumeration."""
import math
from .search import partitions,histories

def counts(n):
    return {'partitions':1<<(n-1),'chronological_histories':sum(math.comb(n-1,k)*math.factorial(k) for k in range(n)), 'distinct_history_forests':math.comb(2*n,n)//(n+1)}

def exhaustive(backend,max_histories=10000):
    first=getattr(backend,'first',0);last=getattr(backend,'last',len(backend.initial)-1)
    n=last-first+1;expected=counts(n)
    if expected['chronological_histories']>max_histories:raise ValueError(f'enumeration budget exceeded before execution: {expected}; increase explicitly')
    records=[];finals={};states_by_key={}
    for mask,local_intervals in partitions(n):
        intervals=[(a+first,b+first) for a,b in local_intervals]
        for target,steps in histories(intervals):
            target=backend.initial[:first]+target+backend.initial[last+1:]
            state=backend.initial;status='complete';failed=None
            for left,right,joined in steps:
                i=next(i for i,t in enumerate(state) if t.key==left)
                assert state[i+1].key==right
                trial=state[i].join(state[i+1]);assert trial.key==joined
                if backend.group(trial) is None:status='infeasible';failed=joined;break
                state=state[:i]+(trial,)+state[i+2:]
            row={'partition_mask':mask,'requested_intervals':intervals,'target_history':backend.key(target),'steps':steps,'status':status,'failed_merge':failed}
            if status=='complete':
                assert [(t.lo,t.hi) for t in state]==[(i,i) for i in range(first)]+intervals+[(i,i) for i in range(last+1,len(backend.initial))]
                key=backend.key(state)
                if key not in finals:
                    name=f'enum{len(finals):04d}';backend.emit(state,name);finals[key]=name;states_by_key[key]=state
                row['artifact']=finals[key]
            records.append(row)
    assert len(records)==expected['chronological_histories']
    return {'expected':expected,'scope':[first,last],'records':records,'feasible_histories':sum(r['status']=='complete' for r in records),'distinct_feasible_forests':len(finals)},states_by_key
