import os
class GPUUnavailable(RuntimeError): pass
import ctypes as C
class CUDA:
    def __init__(self):
        os.environ['CUDA_MODULE_LOADING'] = 'EAGER'
        self.lib = C.CDLL('/usr/lib/wsl/lib/libcuda.so.1')
        P, U, I, S = C.c_void_p, C.c_uint64, C.c_int, C.c_size_t
        signatures = {
            'cuInit': [C.c_uint], 'cuDeviceGet': [C.POINTER(I), I],
            'cuDeviceGetName': [P, I, I], 'cuDeviceGetUuid': [P, I],
            'cuDriverGetVersion': [C.POINTER(I)],
            'cuCtxCreate_v2': [C.POINTER(P), C.c_uint, I], 'cuCtxDestroy_v2': [P],
            'cuModuleLoad': [C.POINTER(P), C.c_char_p], 'cuModuleUnload': [P],
            'cuModuleGetFunction': [C.POINTER(P), P, C.c_char_p],
            'cuMemAlloc_v2': [C.POINTER(U), S], 'cuMemFree_v2': [U],
            'cuMemcpyHtoD_v2': [U, P, S], 'cuMemcpyDtoH_v2': [P, U, S],
            'cuMemsetD8_v2': [U, C.c_ubyte, S],
            'cuEventCreate': [C.POINTER(P), C.c_uint], 'cuEventDestroy_v2': [P],
            'cuEventRecord': [P, P], 'cuEventSynchronize': [P],
            'cuEventElapsedTime': [C.POINTER(C.c_float), P, P],
            'cuLaunchKernel': [P] + [C.c_uint] * 7 + [P, C.POINTER(P), P],
            'cuGetErrorString': [I, C.POINTER(C.c_char_p)],
        }
        for name, sig in signatures.items():
            getattr(self.lib, name).argtypes = sig
            getattr(self.lib, name).restype = I
        code = self.lib.cuInit(0)
        if code:
            raise GPUUnavailable('cuInit returned ' + str(code))
        device = I()
        self.call('cuDeviceGet', C.byref(device), 0)
        self.context = self.handle('cuCtxCreate_v2', 0, device)
        name, uuid, version = C.create_string_buffer(256), C.create_string_buffer(16), I()
        self.call('cuDeviceGetName', name, len(name), device)
        self.call('cuDeviceGetUuid', uuid, device)
        self.call('cuDriverGetVersion', C.byref(version))
        self.metadata = {'name': name.value.decode(), 'uuid_hex': uuid.raw.hex(), 'driver_version': version.value}

    def call(self, name, *arguments):
        result = getattr(self.lib, name)(*arguments)
        if result:
            error = C.c_char_p()
            self.lib.cuGetErrorString(result, C.byref(error))
            raise RuntimeError((name, result, error.value))

    def handle(self, name, *arguments):
        value = C.c_void_p()
        self.call(name, C.byref(value), *arguments)
        return value

    def alloc(self, n):
        ptr = C.c_uint64()
        self.call('cuMemAlloc_v2', C.byref(ptr), n)
        return ptr
