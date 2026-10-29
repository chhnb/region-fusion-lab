"""Replaceable scoring policy. Scores order candidates; they NEVER establish legality."""
from dataclasses import dataclass,field
from typing import Protocol
from .search import risk_score

@dataclass
class ScoreInput:
    left:dict
    right:dict
    before_costs:list|None=None
    after_costs:list|None=None
    scenario_ids:list=field(default_factory=list)
    weights:list|None=None
    frequency:float=1.
    metadata:dict=field(default_factory=dict)

@dataclass
class ScoreResult:
    value:float|None
    reason:str
    details:dict=field(default_factory=dict)

class Scorer(Protocol):
    name:str
    def score(self,features:ScoreInput)->ScoreResult:...

class Similarity:
    name='opcode-similarity-v1'
    def score(self,f):
        a,b=f.left['costs'],f.right['costs'];den=sum(a.values())+sum(b.values())
        num=sum(min(v,b.get(k,0)) for k,v in a.items() if k!='phi')
        return ScoreResult(num/den if den else 0.,'weighted opcode overlap; not runtime gain',{'numerator':num,'denominator':den})

class TrialNetCost:
    name='experimental-ir-net-cost-v0'
    def __init__(self,risk=.25):self.risk=risk
    def score(self,f):
        if f.before_costs is None or f.after_costs is None:return ScoreResult(None,'scenario cost unavailable; defer')
        if len(f.before_costs)!=len(f.after_costs):raise ValueError('scenario mismatch')
        gains=[a-b for a,b in zip(f.before_costs,f.after_costs)]
        return ScoreResult(risk_score(gains,f.weights,self.risk,f.frequency),'uncalibrated weighted IR issue proxy',{'gains':gains,'scenario_ids':f.scenario_ids,'risk':self.risk,'weights':f.weights})

def make_scorer(name):
    if name=='similarity':return Similarity()
    if name=='net-cost':return TrialNetCost()
    if ':' in name:
        import importlib
        module,factory=name.split(':',1)
        scorer=getattr(importlib.import_module(module),factory)()
        if not callable(getattr(scorer,'score',None)) or not getattr(scorer,'name',None):raise TypeError('scorer requires name and score')
        return scorer
    raise ValueError(name)
