"""Case contract. New benchmarks provide program metadata and their own oracle.
Current CompositionalSession requires typed void helpers and a single multiway Choice;
a future contextual/nested session may use a richer PreparedProgram contract.
"""
from typing import Protocol

# Optional interval_predicate(lo, hi) hook:
# A case may return a predicate for exactly that contiguous original-path span,
# evaluated under enclosing first-match entry conditions; None means fallback.
# The same hook is used by dispatch and the pair generator. Predicates with side
# effects or unknown context require a different, explicitly legal adapter.
class Case(Protocol):
    name:str
    case_key:str
    helper:str
    kernel:str
    option_count:int
    def prepare(self,out)->dict:
        """Compile input/leaves/guards. Return typed schema, source prefix, args,
        predicates, kernel IR, initial artifacts and final compiler callback.
        Does not run a fusion policy or select BF/DaRM.
        """
        ...
    def region_tree(self,out)->list:...
    def scenarios(self)->list:...
    def compare(self,run,options):...
