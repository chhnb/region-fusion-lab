"""TPACF source adapter. Preserve all three classifier sites and original unroll policy."""
from pathlib import Path
import re
from vendor import engine as G

HERE=Path(__file__).resolve().parent
PATTERN=r'if\(temp < binbounds\[30\]\).*?else temp2 \+= \(0<<\(j<<3\)\);'
HP='''#define __device__ __attribute__((device))
#define __constant__ __attribute__((constant))
extern "C" { extern __device__ __constant__ double binbounds[63]; }
'''
PREFIX='''#define __global__ __attribute__((global))
#define __device__ __attribute__((device))
#define __constant__ __attribute__((constant))
#define __shared__ __attribute__((shared))
#define NUMBINS 64
struct cartesian {double *x,*y,*z;int *jk;};
struct double3 {double x,y,z;};
struct dim {unsigned x,y,z;};
extern "C" __device__ int __nvvm_read_ptx_sreg_tid_x();
extern "C" __device__ int __nvvm_read_ptx_sreg_ctaid_x();
extern "C" __device__ int __nvvm_read_ptx_sreg_ctaid_y();
extern "C" __device__ void __syncthreads();
#define threadIdx (dim{(unsigned)__nvvm_read_ptx_sreg_tid_x(),0,0})
#define blockIdx (dim{(unsigned)__nvvm_read_ptx_sreg_ctaid_x(),(unsigned)__nvvm_read_ptx_sreg_ctaid_y(),0})
'''
ARGS='double temp,unsigned accum,unsigned shift,unsigned* out'
PASSED='temp,accum,shift,out'

def classification_source():
    return '\n'.join((('if' if i==0 else 'else if')+f' (temp < binbounds[{30-i}])' if i<31 else 'else')+f' {{ *out = accum + ({(31-i)*4}u << shift); }}' for i in range(32))

def prepare(out):
    D=Path(out);raw=(HERE/'ACF_kernel.cu').read_text();matches=list(re.finditer(PATTERN,raw,re.S));assert len(matches)==3
    # Assert all sites have the same ordered predicates and payload, not merely matching endpoints.
    canonical=re.sub(r'\s+','',matches[0][0])
    assert all(re.sub(r'\s+','',m[0])==canonical for m in matches)
    for i in range(31):assert f'binbounds[{30-i}]' in matches[0][0]
    chain=classification_source();(D/'original-chain.cu').write_text(chain)
    hp=HP
    conds=[' || '.join(f'(temp < binbounds[{30-j}])' for j in range(i+1)) for i in range(31)]+[None]
    schema=dict(n=32,total=32,arg='temp',guard_args='double temp',args=ARGS,passed=PASSED,ret='void',target='tpacf_decide')
    case=D/'tpacf';case.mkdir();(case/'leaves').mkdir();(case/'guards').mkdir();(D/'trees').mkdir();(D/'build').mkdir()
    replacement='tpacf_decide(temp, temp2, (unsigned)(j<<3), &temp2);'
    prepared=PREFIX+f'extern "C" __device__ void tpacf_decide({ARGS});\nextern "C" {{\n'+re.sub(PATTERN,replacement,raw,flags=re.S)+'\n}\n'
    kernel_ir=G.compile_src(D,'prepared',prepared,'tpacf')
    def finish(out,module):
        G.command(out,'post',[G.T/'opt',module,'-always-inline','-O3','-internalize','-internalize-public-api-list=ACFKernel,ACFKernelSymm,binbounds','-globaldce','-verify','-S','-o',out/'post.ll'])
        assert not re.search(r'\bcall\b[^\n]*@(?:tpacf_decide|g_)',(out/'post.ll').read_text())
        G.command(out,'llc',[G.T/'llc',out/'post.ll','-O3','-march=nvptx64','-mcpu=sm_80','-o',out/'kernel.ptx'])
        G.command(out,'ptxas',[G.CUDA/'ptxas','-O3','--fmad=false','-arch=sm_86','-v',out/'kernel.ptx','-o',out/'kernel.cubin'])
        return dict(path=str(out/'kernel.cubin'),sha256=G.sha(out/'kernel.cubin'))
    artifacts={};d=D/'original';d.mkdir();ir=G.compile_src(d,'source',PREFIX+'extern "C" {\n'+raw+'\n}\n','tpacf');artifacts['source_original']=finish(d,ir)
    d=D/'native';d.mkdir();(d/'source.cu').write_text('#include <cuda_runtime.h>\n#define NUMBINS 64\nstruct cartesian {double *x,*y,*z;int *jk;};\nextern "C" {\n'+raw+'\n}\n')
    G.command(d,'nvcc',[G.CUDA/'nvcc','-cubin','-O3','--fmad=false','-arch=sm_86',d/'source.cu','-o',d/'kernel.cubin']);artifacts['native']=dict(path=str(d/'kernel.cubin'),sha256=G.sha(d/'kernel.cubin'))
    for i in range(32):
        d=case/'leaves'/str(i);d.mkdir();name=f'g_{i}_{i}'
        ir=G.compile_src(d,'leaf',HP+f'extern "C" __device__ __attribute__((noinline)) void {name}({ARGS}) {{ *out = accum + ({(31-i)*4}u << shift); }}\n','tpacf')
        after=G.cleanup(d,ir,name);G.dump(d/'group.json',G.record(i,i,after))
    for i in range(31):
        d=case/'guards'/str(i);d.mkdir();G.compile_src(d,'guard',HP+f'extern "C" __device__ __attribute__((noinline)) bool guard_{i}(double temp) {{ return {conds[i]}; }}\n','tpacf')
    G.dump(D/'case.json',dict(case='tpacf',options=32,classifier_sites=3,kernels=['ACFKernel','ACFKernelSymm'],grid=[128,128],block=128,shared_bytes=3072,points=16384,unroll='original pragmas retained',input='synthetic seeded isotropic points + source default boundaries; NOT official catalog data',main_comparison='common unmerged helper input; source_original is a separate source-preparation diagnostic',scope='classifier only; preserve loops/barriers/packed-output',bounds='arbitrary, including unordered; cumulative predicates preserve first-match semantics'))
    return dict(hp=hp,ARGS=ARGS,PASSED=PASSED,conds=conds,schema=schema,kernel_ir=kernel_ir,finish=finish,artifacts=artifacts)
