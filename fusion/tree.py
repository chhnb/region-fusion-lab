"""Conservative source structure reader. Does not rewrite predicates or prove legality.
Braced if/else-if/else chains form one Choice; nested choices belong to arms.
Unbraced chains are rejected rather than silently misrepresented.
"""
from dataclasses import dataclass, field, asdict
import re

def masked(s):
    return re.sub(r'/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'',lambda m:' '*len(m[0]),s,flags=re.S)

def close(s,p,left='{',right='}'):
    if s[p]!=left: raise ValueError('expected '+left)
    depth=1
    for i in range(p+1,len(s)):
        depth+=(s[i]==left)-(s[i]==right)
        if depth==0:return i
    raise ValueError('unbalanced source')

@dataclass
class Arm:
    id:str
    condition:str|None
    start:int
    end:int
    children:list=field(default_factory=list)

@dataclass
class Choice:
    id:str
    depth:int
    start:int
    end:int
    arms:list
    uniformity:str='unknown'
    def to_dict(self):return asdict(self)

def parse_choices(source, start=0, end=None, depth=0, prefix='choice'):
    m=masked(source);end=len(source) if end is None else end;result=[];pos=start
    while pos<end:
        match=re.search(r'\bif\s*\(',m[pos:end])
        if not match:break
        begin=pos+match.start();cursor=begin;arms=[];cid=f'{prefix}.{len(result)}'
        while True:
            cond=None
            if m.startswith('if',cursor):
                op=m.index('(',cursor);cp=close(m,op,'(',')');cond=source[op+1:cp];cursor=cp+1
            while cursor<end and m[cursor].isspace():cursor+=1
            if cursor>=end or m[cursor]!='{':raise ValueError(f'unbraced if/else unsupported at offset {cursor}')
            stop=close(m,cursor);aid=f'{cid}.arm{len(arms)}'
            arms.append(Arm(aid,cond,cursor+1,stop,parse_choices(source,cursor+1,stop,depth+1,aid)))
            cursor=stop+1;tail=re.match(r'\s*else\b\s*',m[cursor:end])
            if not tail:break
            cursor+=tail.end()
            if not m.startswith('if',cursor):
                while cursor<end and m[cursor].isspace():cursor+=1
                if m[cursor]!='{':raise ValueError('unbraced else unsupported')
                stop=close(m,cursor);aid=f'{cid}.arm{len(arms)}';arms.append(Arm(aid,None,cursor+1,stop,parse_choices(source,cursor+1,stop,depth+1,aid)));cursor=stop+1;break
        result.append(Choice(cid,depth,begin,cursor,arms));pos=cursor
    return result

def walk(choices):
    for c in choices:
        yield c
        for a in c.arms:yield from walk(a.children)


def adjacent_pairs(choices):
    """Enumerate same-owner adjacent options globally; depth is metadata only.
    Proven-uniform excludes only THIS choice, never its nested choices.
    A compiler adapter must separately establish semantic legality.
    """
    for choice in walk(choices):
        if choice.uniformity=='proven_uniform':continue
        for a,b in zip(choice.arms,choice.arms[1:]):
            yield {'owner':choice.id,'left':a.id,'right':b.id,'depth':choice.depth}
