"""SRAD four-option prototype adapter. Helper extraction is explicit and controlled.
Uses vendored generator; compiler/toolchain dependency recorded in provenance.json.
Not a general LLVM region recognizer. No original run-directory dependency.
"""
from pathlib import Path
import re,json,hashlib,shutil,itertools
from vendor import engine as G
from fusion.tree import masked,close
ROOT=Path(__file__).resolve().parents[2]

def prepare(out):
    D=Path(out);SRC=ROOT/'cases/srad/srad_kernel.cu';B=16
    raw=SRC.read_text();raw=re.sub(r'^#include[^\n]*\n','',raw,flags=re.M);(D/'original-kernels.txt').write_text(raw)
    start=raw.index('   if ( ty == BLOCK_SIZE -1 && tx == BLOCK_SIZE - 1)');mask=masked(raw);pos=mask.index('if',start);parts=[]
    while True:
     cond=None
     if mask.startswith('if',pos):
      opening=mask.index('(',pos);ending=close(mask,opening,'(',')');cond=raw[opening+1:ending];pos=ending+1
     opening=mask.index('{',pos);ending=close(mask,opening);parts.append((cond,raw[opening+1:ending]));pos=ending+1
     tail=re.match(r'\s*else\s*',mask[pos:])
     if not tail:break
     pos+=tail.end()
    assert len(parts)==4 and parts[-1][0] is None
    end=pos;original_chain=raw[start:end];assert 'd_sum =' not in original_chain
    (D/'original-fourway.txt').write_text(original_chain)
    baseprefix='''#define __device__ __attribute__((device))
    #define __global__ __attribute__((global))
    #define __shared__ __attribute__((shared))
    struct dim {unsigned x,y;};
    extern "C" __device__ void __syncthreads();
    '''
    for kind,reg in [('threadIdx','tid'),('blockIdx','ctaid'),('gridDim','nctaid')]:
     for axis in ['x','y']:baseprefix+=f'extern "C" __device__ int __nvvm_read_ptx_sreg_{reg}_{axis}();\n'
     baseprefix+=f'#define {kind} (dim{{(unsigned)__nvvm_read_ptx_sreg_{reg}_x(),(unsigned)__nvvm_read_ptx_sreg_{reg}_y()}})\n'
    prefix=baseprefix+f'#define BLOCK_SIZE {B}\n';hp='#define __device__ __attribute__((device))\n'+f'#define BLOCK_SIZE {B}\n'
    ARGS='int tx,int ty,float cc,float* tile,float* south,float* east,float* out';PASSED='tx,ty,cc,tile,south,east,out';conds=['ty == BLOCK_SIZE-1 && tx == BLOCK_SIZE-1','tx == BLOCK_SIZE-1','tx == BLOCK_SIZE-1 || ty == BLOCK_SIZE-1',None]
    bodies=[]
    for cond,body in parts:
     body=re.sub(r'\b(cn|cs|cw|ce)\b',lambda m:'out['+str(['cn','cs','cw','ce'].index(m[1]))+']',body)
     body=body.replace('south_c[ty][tx]','south[ty*BLOCK_SIZE+tx]').replace('east_c[ty][tx]','east[ty*BLOCK_SIZE+tx]').replace('c_cuda_temp[ty+1][tx]','tile[(ty+1)*BLOCK_SIZE+tx]').replace('c_cuda_temp[ty][tx+1]','tile[ty*BLOCK_SIZE+tx+1]');bodies.append(body)
    schema=dict(n=4,total=4,arg='tx,ty',guard_args='int tx,int ty',args=ARGS,passed=PASSED,ret='void',target='srad_decide')
    case=D/'srad2';case.mkdir(exist_ok=True)
    for n in ['leaves','guards']:(case/n).mkdir(exist_ok=True)
    (D/'trees').mkdir(exist_ok=True);(D/'build').mkdir(exist_ok=True)
    prepared=prefix+f'extern "C" __device__ void srad_decide({ARGS});\nextern "C" {{\n'+raw[:start]+'float vals[4];\nsrad_decide(tx,ty,cc,(float*)c_cuda_temp,(float*)south_c,(float*)east_c,vals);\ncn=vals[0];cs=vals[1];cw=vals[2];ce=vals[3];\n'+raw[end:]+'\n}\n'
    kernel_ir=G.compile_src(D,'prepared',prepared,'srad2')
    def finish(out,module):
     G.command(out,'post',[G.T/'opt',module,'-always-inline','-O3','-internalize','-internalize-public-api-list=srad_cuda_1,srad_cuda_2','-globaldce','-verify','-S','-o',out/'post.ll'])
     assert not re.search(r'\bcall\b[^\n]*@(?:srad_decide|g_)',(out/'post.ll').read_text())
     G.command(out,'llc',[G.T/'llc',out/'post.ll','-O3','-march=nvptx64','-mcpu=sm_80','-o',out/'kernel.ptx']);G.command(out,'ptxas',[G.CUDA/'ptxas','-O3','--fmad=false','-arch=sm_86','-v',out/'kernel.ptx','-o',out/'kernel.cubin']);return dict(path=str(out/'kernel.cubin'),sha256=G.sha(out/'kernel.cubin'))
    artifacts={};out=D/'original';out.mkdir(exist_ok=True);ir=G.compile_src(out,'source',prefix+'extern "C" {\n'+raw+'\n}\n','srad2');artifacts['original']=finish(out,ir)
    # Unchanged CUDA kernel compiled with NVCC supplies an independent compiler oracle.
    out=D/'native';out.mkdir(exist_ok=True);(out/'source.cu').write_text('#include <cuda_runtime.h>\n'+f'#define BLOCK_SIZE {B}\n'+'extern "C" {\n'+raw+'\n}\n');G.command(out,'nvcc',[G.CUDA/'nvcc','-cubin','-O3','--fmad=false','-arch=sm_86',out/'source.cu','-o',out/'kernel.cubin']);artifacts['native']=dict(path=str(out/'kernel.cubin'),sha256=G.sha(out/'kernel.cubin'))
    for i,body in enumerate(bodies):
     out=case/'leaves'/str(i);out.mkdir(exist_ok=True);name=f'g_{i}_{i}';ir=G.compile_src(out,'leaf',hp+f'extern "C" __device__ __attribute__((noinline)) void {name}({ARGS}) {{\n'+body+'\n}\n','srad2');after=G.cleanup(out,ir,name);G.dump(out/'group.json',G.record(i,i,after))
    for i in range(3):
     out=case/'guards'/str(i);out.mkdir(exist_ok=True);G.compile_src(out,'guard',hp+f'extern "C" __device__ __attribute__((noinline)) bool guard_{i}(int tx,int ty) {{return {conds[i]};}}\n','srad2')
    return locals()
