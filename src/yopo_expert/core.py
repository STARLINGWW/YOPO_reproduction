from pathlib import Path
import ctypes,json
import numpy as np
ROOT=Path(__file__).resolve().parents[2]


class ExpertMap:
    """Owns a single-threaded unchanged-main C++ cost instance and original field."""
    def __init__(self,folder,config=None):
        folder=Path(folder);meta=json.loads((folder/'map.json').read_text())
        if meta['backend']!='original_main_bucket':raise ValueError('Expert requires original main field backend')
        values=np.load(folder/'sdf.npy',mmap_mode='r')
        self._initialize(values,meta['origin'],meta['upper'],meta['resolution'],config)

    @classmethod
    def from_array(cls,values,origin,upper,resolution,config):
        obj=cls.__new__(cls);obj._initialize(values,origin,upper,resolution,config);return obj

    def _initialize(self,values,origin,upper,resolution,config):
        self.lib=ctypes.CDLL(str(ROOT/'ros2_ws/install/yopo_expert_core/lib/libyopo_expert.so'))
        fp=np.ctypeslib.ndpointer(dtype=np.float32,flags='C_CONTIGUOUS')
        dp=np.ctypeslib.ndpointer(dtype=np.float64,flags='C_CONTIGUOUS')
        ip=np.ctypeslib.ndpointer(dtype=np.int64,flags='C_CONTIGUOUS')
        self.lib.expert_error.restype=ctypes.c_char_p
        self.lib.expert_create.argtypes=[ctypes.c_char_p,fp,ip,dp,dp,ctypes.c_double];self.lib.expert_create.restype=ctypes.c_void_p
        self.lib.expert_destroy.argtypes=[ctypes.c_void_p];self.lib.expert_destroy.restype=None
        self.lib.expert_evaluate.argtypes=[ctypes.c_void_p,dp,dp,dp,ctypes.c_int,dp,dp];self.lib.expert_evaluate.restype=ctypes.c_int
        self.lib.expert_optimize.argtypes=[ctypes.c_void_p,dp,dp,dp,ctypes.c_int,ctypes.c_int,ctypes.c_int,dp,dp,dp];self.lib.expert_optimize.restype=ctypes.c_int
        config=Path(config or ROOT/'external/audit_sources/main/flightlib/configs/traj_opt.yaml')
        self.handle=self.lib.expert_create(str(config).encode(),np.ascontiguousarray(values,np.float32),
            np.array(values.shape,np.int64),np.array(origin,float),np.array(upper,float),resolution)
        if not self.handle:raise RuntimeError(self.lib.expert_error().decode())

    def close(self):
        if self.handle:self.lib.expert_destroy(self.handle);self.handle=None

    def evaluate(self,starts,ends,goals):
        starts,ends,goals=[np.ascontiguousarray(v,dtype=np.float64) for v in (starts,ends,goals)]
        if starts.shape!=ends.shape or starts.shape[1:]!=(3,3) or goals.shape!=(len(starts),3):raise ValueError('Expected batched world-frame p/v/a')
        costs=np.empty(len(starts));gradient=np.empty_like(ends)
        if self.lib.expert_evaluate(self.handle,starts,ends,goals,len(starts),costs,gradient):raise RuntimeError(self.lib.expert_error().decode())
        return costs,gradient

    def optimize(self,starts,initials,goals,variant='scaled_gd50'):
        mode={'scaled_gd50':0,'mma50_evaluations':1}[variant]
        starts,initials,goals=[np.ascontiguousarray(v,dtype=np.float64) for v in (starts,initials,goals)]
        if starts.shape!=initials.shape or starts.shape[1:]!=(3,3) or goals.shape!=(len(starts),3):raise ValueError('Expected batched world-frame p/v/a')
        ends=np.empty_like(initials);costs=np.empty(len(starts));diagnostics=np.empty((len(starts),5))
        if self.lib.expert_optimize(self.handle,starts,initials,goals,len(starts),mode,50,ends,costs,diagnostics):raise RuntimeError(self.lib.expert_error().decode())
        return ends,costs,diagnostics


def world_problem(positions,rotations,observations,end_body,goal_length=10.):
    batch,candidates=end_body.shape[:2]
    start=np.empty((batch,3,3));start[:,:,0]=positions
    start[:,:,1]=np.einsum('bij,bj->bi',rotations,observations[:,:3])
    start[:,:,2]=np.einsum('bij,bj->bi',rotations,observations[:,3:6])
    goals=positions+np.einsum('bij,bj->bi',rotations,goal_length*observations[:,6:9])
    end=np.einsum('bij,bmjk->bmik',rotations,end_body.reshape(batch,candidates,3,3))
    end[:,:,:,0]+=positions[:,None,:]
    return np.repeat(start,candidates,axis=0),end.reshape(-1,3,3),np.repeat(goals,candidates,axis=0)
