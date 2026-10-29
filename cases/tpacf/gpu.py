"""Original TPACF launch geometry, packed-output oracle and deterministic inputs."""
from pathlib import Path
import ctypes as C,json
import numpy as np
from vendor.cuda_driver import CUDA
from .conditions import pair_bounds
N=16384
OUT_BYTES=N*N
class Cartesian(C.Structure):
    _fields_=[('x',C.c_uint64),('y',C.c_uint64),('z',C.c_uint64),('jk',C.c_uint64)]

def bounds():
    b=np.zeros(63,np.float64);b[:10]=-5.;b[10:31]=np.cos(10.**(np.arange(21)/5)*np.pi/(60*180));b[30]=-5.;return b

def inputs(kind='isotropic',seed=20261021):
    rng=np.random.default_rng(seed)
    def sphere():
        x=rng.normal(size=(N,3));return x/np.linalg.norm(x,axis=1)[:,None]
    x,y=sphere(),sphere();b=bounds()
    if kind=='edges':
        values=np.concatenate([b[:31],np.nextafter(b[:31],-np.inf),np.nextafter(b[:31],np.inf),[np.nan,-np.inf,np.inf,0.,-6.,1.]])
        x=np.zeros((N,3));x[:,0]=np.resize(values,N);y=np.zeros((N,3));y[:,0]=1.
    elif kind=='wide':
        b[:31]=np.linspace(.98,-.98,31)
        values=np.concatenate([[-1.1,1.1],(b[:30]+b[1:31])/2,b[:31]])
        x=np.zeros((N,3));x[:,0]=np.resize(values,N);y=np.zeros((N,3));y[:,0]=1.
    elif kind=='unordered':b[:31]=rng.uniform(-1,1,31)
    elif kind=='nonfinite_bounds':
        b[:31]=np.linspace(.98,-.98,31)
        b[[30,29,28,25,0]]=np.nan;b[24]=np.inf;b[23]=-np.inf;b[12]=-0.;b[11]=0.
        values=np.concatenate([b[:31],np.nextafter(b[:31],-np.inf),np.nextafter(b[:31],np.inf),[np.nan,-np.inf,np.inf,0.,-0.,-6.,1.]])
        x=np.zeros((N,3));x[:,0]=np.resize(values,N);y=np.zeros((N,3));y[:,0]=1.
    elif kind!='isotropic':raise ValueError(kind)
    return x,y,b

def oracle(x,y,b,symm=False):
    # Rows are the first argument's points; columns the second argument's points.
    with np.errstate(invalid='ignore',over='ignore'):
        dot=(x[:,0,None]*y[None,:,0]+x[:,1,None]*y[None,:,1])+x[:,2,None]*y[None,:,2]
    codes=np.zeros(dot.shape,np.uint32);pending=np.ones(dot.shape,bool)
    for i in range(30,-1,-1):
        take=pending&(dot<b[i]);codes[take]=(i+1)*4;pending[take]=False
    if symm:codes[np.arange(len(x))[:,None]>=np.arange(len(y))[None,:]]=124
    return np.bitwise_or.reduce(codes.reshape(len(x)//4,4,len(y))<<(np.arange(4,dtype=np.uint32)[None,:,None]*8),axis=1)

class GPU:
    def __init__(self,run,names):
        self.g=CUDA();g=self.g;self.mods={};self.fn={};self.constants={};self.aux_constants={};self.buffers=[]
        g.lib.cuModuleGetGlobal_v2.argtypes=[C.POINTER(C.c_uint64),C.POINTER(C.c_size_t),C.c_void_p,C.c_char_p];g.lib.cuModuleGetGlobal_v2.restype=C.c_int
        g.lib.cuMemsetD32_v2.argtypes=[C.c_uint64,C.c_uint,C.c_size_t];g.lib.cuMemsetD32_v2.restype=C.c_int
        arts=json.loads((Path(run)/'artifacts.json').read_text())
        for name in dict.fromkeys(['native',*names]):
            m=g.handle('cuModuleLoad',arts[name]['path'].encode());self.mods[name]=m;self.fn[name]={k:g.handle('cuModuleGetFunction',m,k.encode()) for k in ['ACFKernel','ACFKernelSymm']}
            ptr=C.c_uint64();size=C.c_size_t();g.call('cuModuleGetGlobal_v2',C.byref(ptr),C.byref(size),m,b'binbounds');assert size.value==63*8;self.constants[name]=ptr
            self.aux_constants[name]={}
            for symbol,kind in arts[name].get('aux_constants',{}).items():
                if kind!='tpacf_pair_max':raise ValueError('unsupported auxiliary constant: '+kind)
                aux=C.c_uint64();length=C.c_size_t();g.call('cuModuleGetGlobal_v2',C.byref(aux),C.byref(length),m,symbol.encode());assert length.value==15*8
                self.aux_constants[name][symbol]=aux
        self.raw=g.alloc(OUT_BYTES+128);self.buffers.append(self.raw);self.out=C.c_uint64(self.raw.value+64);g.call('cuMemsetD8_v2',self.raw,0xA5,OUT_BYTES+128)
        self.arrays=[g.alloc(N*8) for _ in range(6)];self.buffers.extend(self.arrays)
        self.a=Cartesian(*[p.value for p in self.arrays[:3]],0);self.b=Cartesian(*[p.value for p in self.arrays[3:]],0)
        self.events=[g.handle('cuEventCreate',0) for _ in range(2)]
        self.args={}
        for k,vals in [('ACFKernel',[self.a,self.b,self.out]),('ACFKernelSymm',[self.a,self.out])]:self.args[k]=(C.c_void_p*len(vals))(*[C.cast(C.pointer(v),C.c_void_p) for v in vals])
    def configure(self,x,y,b):
        for ptr,a in zip(self.arrays,[*x.T,*y.T]):
            a=np.ascontiguousarray(a,np.float64);self.g.call('cuMemcpyHtoD_v2',ptr,a.ctypes.data,a.nbytes)
        for ptr in self.constants.values():self.g.call('cuMemcpyHtoD_v2',ptr,b.ctypes.data,b.nbytes)
        if any(self.aux_constants.values()):
            pairs=np.asarray(pair_bounds(b),np.float64)
            for symbols in self.aux_constants.values():
                for ptr in symbols.values():self.g.call('cuMemcpyHtoD_v2',ptr,pairs.ctypes.data,pairs.nbytes)
    def clear(self):self.g.call('cuMemsetD32_v2',self.out,0xdeadbeef,OUT_BYTES//4)
    def launch(self,name,kernel,grid=128):
        g=self.g;g.call('cuEventRecord',self.events[0],None);g.call('cuLaunchKernel',self.fn[name][kernel],grid,grid,1,128,1,1,3072,None,self.args[kernel],None);g.call('cuEventRecord',self.events[1],None);g.call('cuEventSynchronize',self.events[1]);ms=C.c_float();g.call('cuEventElapsedTime',C.byref(ms),*self.events);return ms.value
    def read(self):
        host=np.empty(OUT_BYTES//4+32,np.uint32);self.g.call('cuMemcpyDtoH_v2',host.ctypes.data,self.raw,host.nbytes)
        assert np.all(host[:16]==0xa5a5a5a5) and np.all(host[-16:]==0xa5a5a5a5),'device output canary'
        return host[16:-16].reshape(N//4,N)
    def close(self):
        for ptr in self.buffers:self.g.call('cuMemFree_v2',ptr)
        for e in self.events:self.g.call('cuEventDestroy_v2',e)
        for m in self.mods.values():self.g.call('cuModuleUnload',m)
        self.g.call('cuCtxDestroy_v2',self.g.context)
