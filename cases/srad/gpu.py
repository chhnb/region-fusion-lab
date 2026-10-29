from pathlib import Path
import sys,ctypes as C,json
import numpy as np
D=Path(__file__).resolve().parent;from vendor.cuda_driver import CUDA
B=16
seed=C.CDLL(str(D/'seed.so'));seed.seed_image.argtypes=[C.c_void_p,C.c_int,C.c_int];seed.q0_image.argtypes=[C.c_void_p,C.c_int,C.c_int,C.c_int];seed.q0_image.restype=C.c_float

def image(rows,cols,kind='default'):
 if kind=='default':a=np.empty((rows,cols),np.float32);seed.seed_image(a.ctypes.data,rows,cols)
 elif kind=='gradient':a=(1+np.arange(rows,dtype=np.float32)[:,None]/max(1,rows)+np.arange(cols,dtype=np.float32)[None,:]/max(1,cols)).astype(np.float32)
 elif kind=='constant':a=np.full((rows,cols),2.,np.float32)
 else:raise ValueError(kind)
 q=float(seed.q0_image(a.ctypes.data,rows,cols,128));return a,q if q>0 else .1

def cpu2(j,c,e,w,n,s,lam=.5):
 cs=np.concatenate([c[1:],c[-1:]],axis=0);ce=np.concatenate([c[:,1:],c[:,-1:]],axis=1)
 d=(c*n).astype(np.float32);d=(d+(cs*s).astype(np.float32)).astype(np.float32);d=(d+(c*w).astype(np.float32)).astype(np.float32);d=(d+(ce*e).astype(np.float32)).astype(np.float32)
 return (j.astype(np.float64)+(.25*float(np.float32(lam)))*d.astype(np.float64)).astype(np.float32)
class GPU:
 def __init__(self):
  self.g=CUDA();self.mods={};self.fn={};self.buffers=[];self.events=[self.g.handle('cuEventCreate',0) for _ in range(2)]
  for n,r in json.loads((D/'artifacts.json').read_text()).items():
   m=self.g.handle('cuModuleLoad',r['path'].encode());self.mods[n]=m;self.fn[n]={i:self.g.handle('cuModuleGetFunction',m,f'srad_cuda_{i}'.encode()) for i in [1,2]}
 def configure(self,j,q,lam=.5):
  for raw in self.buffers:self.g.call('cuMemFree_v2',raw)
  self.buffers=[];self.rows,self.cols=j.shape;assert self.rows%B==0 and self.cols%B==0;self.j=j.copy();self.q=q;self.lam=lam;self.host=np.empty(j.size+32,np.float32);self.ptr={};self.raw={}
  for name in ['E','W','N','S','J','C']:
   raw=self.g.alloc(self.host.nbytes);self.buffers.append(raw);self.raw[name]=raw;self.ptr[name]=C.c_uint64(raw.value+64);self.g.call('cuMemsetD8_v2',raw,0xA5,self.host.nbytes)
  self.put('J',j)
 def put(self,name,a):
  a=np.ascontiguousarray(a,np.float32);self.g.call('cuMemcpyHtoD_v2',self.ptr[name],a.ctypes.data,a.nbytes)
 def get(self,name):
  self.g.call('cuMemcpyDtoH_v2',self.host.ctypes.data,self.raw[name],self.host.nbytes);assert np.all(self.host[:16].view(np.uint8)==0xA5) and np.all(self.host[-16:].view(np.uint8)==0xA5),('guard',name);return self.host[16:-16].reshape(self.rows,self.cols).copy()
 def launch(self,name,stage,expected=None,reset=True):
  if stage==2 and reset:self.put('J',self.j)
  vals=[self.ptr[x] for x in ['E','W','N','S','J','C']]+[C.c_int(self.cols),C.c_int(self.rows)]+([C.c_float(self.lam),C.c_float(self.q)] if stage==2 else [C.c_float(self.q)])
  args=(C.c_void_p*len(vals))(*[C.cast(C.pointer(v),C.c_void_p) for v in vals]);g=self.g;g.call('cuEventRecord',self.events[0],None);g.call('cuLaunchKernel',self.fn[name][stage],self.cols//B,self.rows//B,1,B,B,1,0,None,args,None);g.call('cuEventRecord',self.events[1],None);g.call('cuEventSynchronize',self.events[1]);ms=C.c_float();g.call('cuEventElapsedTime',C.byref(ms),*self.events)
  out=self.get('J') if stage==2 else None
  if expected is not None:assert np.array_equal(out.view(np.uint32),expected.view(np.uint32)),(name,stage,'matrix differs',int(np.count_nonzero(out.view(np.uint32)!=expected.view(np.uint32))))
  return ms.value,out
 def prepare(self,j,q):
  self.configure(j,q);self.launch('native',1);data={n:self.get(n) for n in ['C','E','W','N','S']};expected=cpu2(j,data['C'],data['E'],data['W'],data['N'],data['S']);self.launch('native',2,expected);return expected,data
 def close(self):
  for raw in self.buffers:self.g.call('cuMemFree_v2',raw)
  for e in self.events:self.g.call('cuEventDestroy_v2',e)
  for m in self.mods.values():self.g.call('cuModuleUnload',m)
  self.g.call('cuCtxDestroy_v2',self.g.context)
