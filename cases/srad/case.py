"""SRAD program description. No scheduling or BF/DaRM policy here."""
from pathlib import Path
from .prepare import prepare
from fusion.tree import parse_choices
from fusion.cost import subset_scenarios

class SRAD4:
    name='srad4'
    case_key='srad2'
    helper='srad_decide'
    kernel='srad_cuda_2'
    default_size=4096
    option_count=4
    gpu_module='cases.srad.gpu'
    def prepare(self,out):return prepare(out)
    def scenarios(self):return subset_scenarios([(15,15),(15,0),(0,15),(0,0)])
    def region_tree(self,out):
        choices=parse_choices((Path(out)/'original-fourway.txt').read_text())
        assert len(choices)==1 and len(choices[0].arms)==self.option_count
        return [c.to_dict() for c in choices]
    def compare(self,run,options):
        from experiments.measurement import compare
        from . import gpu
        return compare(run,options,gpu,stage=2)
