"""Cases can be built-ins or module:factory plugins; no search changes required."""
import importlib
BUILTINS={'srad4':'cases.srad.case:SRAD4','tpacf':'cases.tpacf.case:TPACF'}
def load(name):
    spec=BUILTINS.get(name,name)
    if ':' not in spec:raise ValueError('unknown case: '+name)
    module,factory=spec.split(':',1)
    return getattr(importlib.import_module(module),factory)()
