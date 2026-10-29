"""Branch Fusion comparison method using the engine's BF-only mode."""
from .darm import DARM

class BranchFusion(DARM):
    name='bf'
    extra_flags=('-run-branch-fusion-only',)
