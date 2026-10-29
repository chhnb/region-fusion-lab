"""Compositional single-Choice session connecting case, generator, scorer and search.
Compositional helper backend: cached pair result is a function of child IR hashes.
Explicit limitation: full-function contextual generation is not implemented here.
"""
from pathlib import Path
import hashlib,json,re
from vendor import engine as G
from .search import MergeHistory
from .scoring import ScoreInput
from .cost import Program,subset_scenarios,UnsupportedCost
from .tree import parse_choices

class CompositionalSession:
    def __init__(self,out,scorer,case,generator,first=0,last=None):
        self.first=first;self.last=case.option_count-1 if last is None else last
        self.out=Path(out);self.scorer=scorer;self.case=case;self.generator=generator
        self.ctx=case.prepare(out);generator.configure(out,case,self.ctx);self.groups={};self.trials={};self.states={}
        self.initial=tuple(MergeHistory(i,i) for i in range(case.option_count))
        self.scenarios=case.scenarios()
        for t in self.initial:self.groups[t.key]=json.loads((self.out/case.case_key/'leaves'/str(t.lo)/'group.json').read_text())
        G.dump(self.out/'region-tree.json',case.region_tree(out))
        G.dump(self.out/'scenarios.json',dict(origin='static case-defined scenarios; NOT measured profile',scenarios=self.scenarios))
        self.artifacts=self.ctx['artifacts'];self.attempts=[]
    def key(self,state):return '|'.join(t.key for t in state)
    def pairs(self,state):return [('choice.0',i) for i,(a,b) in enumerate(zip(state,state[1:])) if self.first<=a.lo and b.hi<=self.last]
    def group(self,t):
        if t.key in self.groups:return self.groups[t.key]
        left,right=self.group(t.left),self.group(t.right)
        if left is None or right is None:self.groups[t.key]=None;return None
        d=self.out/'trees'/hashlib.sha256(t.key.encode()).hexdigest()[:16]
        record={'history':t.key,'left_sha':left['sha256'],'right_sha':right['sha256'],'generation_similarity_threshold':0.0,'merge_cleanup':getattr(self.generator,'cleanup','unspecified')}
        try:
            result=self.generator.merge(self.case.case_key,left,right,d);record['status']='accepted' if result else 'rejected_no_meld'
        except Exception as e:
            result=None;record.update(status='generation_failed',error=str(e))
        d.mkdir(exist_ok=True);G.dump(d/'status.json',record);self.attempts.append(record);self.groups[t.key]=result;return result
    def assemble(self,state):
        key=self.key(state)
        if key in self.states:return self.states[key]
        groups=[self.group(t) for t in state]
        if any(g is None for g in groups):raise ValueError('cannot assemble partially fused interval')
        c=self.ctx;args=c['ARGS'];passed=c['PASSED'];conds=c['conds'];d=self.out/'states'/hashlib.sha256(key.encode()).hexdigest()[:16];d.mkdir(parents=True)
        src=c['hp']
        for g in groups:src+=f'extern "C" __device__ void {g["name"]}({args});\n'
        src+=f'extern "C" __device__ __attribute__((always_inline)) void {self.case.helper}({args}) {{\n'
        for i,g in enumerate(groups):
            condition=self.case.interval_predicate(g['lo'],g['hi']) if hasattr(self.case,'interval_predicate') else conds[g['hi']]
            src+=(('if' if i==0 else 'else if')+' ('+condition+') ' if condition else '')+f'{{{g["name"]}({passed});return;}}\n'
        src+='}\n';ir=G.compile_src(d,'dispatch',src,self.case.case_key)
        G.command(d,'link',[G.T/'llvm-link',c['kernel_ir'],ir,*[g['module'] for g in groups],'-S','-o',d/'linked.ll'])
        # Same ordinary optimization for before/after cost scope. Preserve helper as root.
        G.command(d,'cost',[G.T/'opt',d/'linked.ll','-internalize','-internalize-public-api-list='+self.case.helper,'-globaldce','-always-inline','-O3','-verify','-S','-o',d/'cost.ll'])
        row={'key':key,'dir':str(d),'groups':[[t.lo,t.hi] for t in state]};self.states[key]=row;return row
    def evaluate(self,state,pair,version):
        owner,i=pair;a,b=state[i:i+2];t=a.join(b);row={'id':f'{owner}:{a.key}+{b.key}','owner':owner,'index':i,'version':version,'state_key':self.key(state),'history':t.key,'dependencies':[self.key(state)],'status':'generation_failed'}
        g=self.group(t)
        if g is None:return row
        new=state[:i]+(t,)+state[i+2:]
        f=ScoreInput(self.group(a),self.group(b))
        if self.scorer.name=='experimental-ir-net-cost-v0':
            if not self.scenarios:
                row.update(status='unsupported_cost',reason='case provides no supported static scenarios');return row
            try:
                before=self.assemble(state);after=self.assemble(new)
                programs=[Program((Path(x['dir'])/'cost.ll').read_text(),self.case.helper) for x in [before,after]]
                f.before_costs=[programs[0].estimate(s['lanes'])[0] for s in self.scenarios];f.after_costs=[programs[1].estimate(s['lanes'])[0] for s in self.scenarios];f.scenario_ids=[s['id'] for s in self.scenarios]
            except UnsupportedCost as e:row.update(status='unsupported_cost',reason=str(e));return row
        result=self.scorer.score(f);row.update(status='valid' if result.value is not None else 'unsupported_cost',score=result.value,scoring=self.scorer.name,reason=result.reason,details=result.details)
        return row
    def commit(self,state,candidate):
        if candidate['state_key']!=self.key(state):raise ValueError('stale patch')
        i=candidate['index'];t=state[i].join(state[i+1]);assert t.key==candidate['history'] and self.group(t) is not None
        return state[:i]+(t,)+state[i+2:]
    def emit(self,state,name):
        row=self.assemble(state);d=Path(row['dir'])
        if 'artifact' not in row:row['artifact']=self.ctx['finish'](d,d/'linked.ll')
        self.artifacts[name]=dict(row['artifact'],history=self.key(state),groups=row['groups']);return self.artifacts[name]
    def save(self):
        G.dump(self.out/'artifacts.json',self.artifacts);G.dump(self.out/'generation.json',self.attempts)
