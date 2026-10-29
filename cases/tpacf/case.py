from pathlib import Path
from .prepare import prepare,classification_source
from fusion.tree import parse_choices

class TPACF:
    name='tpacf'
    case_key='tpacf'
    helper='tpacf_decide'
    kernel='ACFKernel'
    default_size=16384
    option_count=32
    baseline_scope='helper'
    def prepare(self,out):return prepare(out)
    def region_tree(self,out):
        choice=parse_choices(classification_source());assert len(choice)==1 and len(choice[0].arms)==32
        return [c.to_dict() for c in choice]
    def scenarios(self):return []  # No exponential static subset enumeration or fabricated profile.
    def compare(self,run,options):
        from .benchmark import compare
        return compare(run,options)
