"""Map-disjoint, memory-mapped depth shards and deterministic main-distribution states."""
from pathlib import Path
import json
import cv2
import numpy as np
from scipy.spatial.transform import Rotation
from torch.utils.data import Dataset


class ForestDataset(Dataset):
    def __init__(self,root,split,cfg,seed=0):
        self.root=Path(root);self.split=split;self.cfg=cfg;self.seed=seed;self.epoch=0
        self.index=json.loads((self.root/'dataset.json').read_text(encoding='utf-8'))
        if self.index['status']!='complete':raise ValueError('Dataset preparation is incomplete')
        self.shards=[x for x in self.index['shards'] if x['split']==split]
        if not self.shards:raise ValueError('Empty split')
        self.ends=np.cumsum([x['samples'] for x in self.shards])
        self.arrays={};self.poses={}
        for shard in self.shards:
            folder=self.root/shard['path']
            self.arrays[shard['id']]=np.load(folder/'depth_m.npy',mmap_mode='r')
            self.poses[shard['id']]=dict(np.load(folder/'poses.npz'))

    def __len__(self):return int(self.ends[-1])

    def __getitem__(self,index):
        index=int(index);shard_index=int(np.searchsorted(self.ends,index,side='right'))
        local=index-(int(self.ends[shard_index-1]) if shard_index else 0)
        shard=self.shards[shard_index];identifier=shard['id']
        raw=np.asarray(self.arrays[identifier][local],dtype=np.float32)
        image=cv2.resize(np.minimum(raw,20.)/20.,(160,96),interpolation=cv2.INTER_LINEAR)[None]
        labels=self.poses[identifier];p=labels['positions'][local];q=labels['quaternions'][local]
        rotation=Rotation.from_quat(q[[1,2,3,0]])
        # Epoch-varying training augmentation; validation/test stay frozen.
        epoch=self.epoch if self.split=='train' else 0
        rng=np.random.default_rng(np.random.SeedSequence([self.seed,epoch,identifier,local]))
        cfg=self.cfg;multiple=.5*cfg['vel_max'];v_des=multiple*cfg['vx_mean_unit']
        v_mean=multiple*np.array([cfg['vx_mean_unit'],cfg['vy_mean_unit'],cfg['vz_mean_unit']])
        v_var=multiple**2*np.array([cfg['vx_var_unit'],cfg['vy_var_unit'],cfg['vz_var_unit']])
        a_mean=multiple**2*np.array([cfg['ax_mean_unit'],cfg['ay_mean_unit'],cfg['az_mean_unit']])
        a_var=multiple**4*np.array([cfg['ax_var_unit'],cfg['ay_var_unit'],cfg['az_var_unit']])
        velocity=v_mean+np.sqrt(v_var)*rng.normal(size=3)
        acceleration=a_mean+np.sqrt(a_var)*rng.normal(size=3)
        vx=-1.
        while vx<0:
            vx=cfg['vel_max']+.2-rng.lognormal(np.log(cfg['vel_max']-v_des),np.log(np.sqrt(v_des)))
        velocity[0]=vx
        yaw,pitch,roll=rotation.as_euler('ZYX')
        goal=Rotation.from_euler('ZYX',[0,pitch,roll]).inv().apply(rng.normal(size=3)+[2,0,0])
        goal/=np.linalg.norm(goal)
        obs=np.r_[velocity,acceleration,goal].astype(np.float32)
        return image.astype(np.float32),p.astype(np.float64),rotation.as_matrix(),obs,np.int64(identifier)


def stack_batch(dataset,indices):
    columns=list(zip(*(dataset[int(i)] for i in indices)))
    return tuple(np.stack(column) for column in columns)
