"""Run independent comparison methods on original and matched-helper inputs."""
from pathlib import Path
import re
from vendor import engine as G
def build_baselines(session,methods):
    # Matched helper preparation as an explicit control, then original-kernel controls.
    d=session.out/'baselines';d.mkdir();base=session.assemble(session.initial);text=(Path(base['dir'])/'linked.ll').read_text();fn=G.function(text,session.case.helper);aid=re.search(r' #(\d+)',fn.splitlines()[0])[1];attrs=re.search(r'^attributes #'+aid+r' = \{ (.*?) \}',text,re.M)[1];attrs=re.sub(r'\b(?:alwaysinline|noinline|optnone)\b','',attrs);nid=max(map(int,re.findall(r'^attributes #(\d+)',text,re.M)))+1;text=text.replace(fn,re.sub(r' #'+aid+r'\b',' #'+str(nid),fn,count=1),1)+f'\nattributes #{nid} = {{ noinline '+attrs+' }\n';(d/'helper-input.ll').write_text(text)
    G.command(d,'prep',[G.T/'opt',d/'helper-input.ll','-always-inline','-simplifycfg','-verify','-S','-o',d/'helper.ll'])
    specs=[]
    for method in methods:
        specs.extend([(method.name,session.out/'original/source.ll',session.case.kernel,method),('helper_'+method.name,d/'helper.ll',session.case.helper,method)])
    for name,source,target,method in specs:
        out=d/name;out.mkdir()
        try:
            p=method.transform(session.out/'engine/opt-adjacent',source,target,out)
            text=(out/'meld.ll').read_text()
            if target==session.case.helper:text=G.inline(text,target)
            (out/'inline.ll').write_text(text);session.artifacts[name]=dict(session.ctx['finish'](out,out/'inline.ll'),melds=p.stderr.count('Melding entry blocks'),target=target,engine='vendored local repaired DaRM',threshold=.2)
        except Exception as e:G.dump(out/'failure.json',{'status':'failed','error':str(e)})
