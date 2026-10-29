"""Backend contract for the global, depth-independent scheduler.

A state contains the WHOLE current choice/region structure, not just one pair.
Pairs MUST carry owner Choice identity and stable original-path provenance.
The generator owns semantic legality; LLVM verifier alone is insufficient.
Full-refresh reference mode evaluates every supported pair at each version.
A future incremental backend must match this reference trace exactly.
"""
from typing import Protocol,Any

class Backend(Protocol):
    def pairs(self,state:Any):
        """All supported adjacent options in every Choice, at ALL depths.
        Skip cross-arm fusion for proven-uniform choices, but visit children.
        Unknown uniformity is not proof of actual runtime divergence.
        """
        ...
    def evaluate(self,state,pair,version:int)->dict:
        """Generate/check a trial then score; statuses remain distinct:
        valid, uniform, illegal, generation_failed, unsupported_cost, resource.
        Return id, version, status, score (only if valid), diagnostics.
        Candidate id must break score ties deterministically, without depth.
        """
        ...
    def commit(self,state,candidate)->Any:
        """Apply against current state/version, preserving unrelated work.
        Return a new state. Never replace it with a stale whole-function clone.
        """
        ...
    def key(self,state)->str:...
