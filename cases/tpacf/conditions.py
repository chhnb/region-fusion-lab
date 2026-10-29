"""Optional TPACF condition aggregation; no changes to within-group priority."""
import math
PAIR_INDICES=tuple((hi,hi-1) for hi in range(30,0,-2))

def pair_bounds(bounds):
    """Same number-preferring NaN behavior as the legacy np.fmax pair reduction.
    Signed-zero choice is immaterial for ordered '<'; values are only thresholds.
    Neither max-bound selection nor this preprocessing selects the winning leaf.
    """
    if len(bounds)!=63:raise ValueError('expected63 bin boundaries')
    result=[]
    for i,j in PAIR_INDICES:
        a,b=float(bounds[i]),float(bounds[j])
        if math.isnan(a):v=b
        elif math.isnan(b):v=a
        elif a==0. and b==0.:v=b  # match numpy.fmax's tie behavior for signed zero
        else:v=a if a>b else b
        result.append(v)
    return result
