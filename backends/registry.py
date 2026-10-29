from .darm import DARM,DARMGenerator
from .bf import BranchFusion

def generator(name,cleanup='minimal'):
    if name=='darm':return DARMGenerator(cleanup=cleanup)
    raise ValueError('unknown pair generator: '+name)

def method(name):
    if name=='darm':return DARM()
    if name=='bf':return BranchFusion()
    raise ValueError('unknown comparison method: '+name)
