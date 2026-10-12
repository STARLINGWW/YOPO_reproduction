"""Unmodified original-main network plus batched guidance-gradient integration."""
from pathlib import Path
import json
import sys
import numpy as np
import torch
import yaml

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'external/audit_sources/main'))
from flightpolicy.yopo.yopo_policy import YopoPolicy
from flightpolicy.yopo.primitive_utils import LatticeParam,LatticePrimitive
from .main_cost import CostConfig,cost_and_gradient,upstream_network_gradient
from .maps import VoxelSDF


def load_config():
    profile=json.loads((ROOT/'configs/paper_aligned.json').read_text(encoding='utf-8'))
    cfg=yaml.safe_load((ROOT/profile['trajectory_yaml']).read_text(encoding='utf-8'))
    return profile,cfg


def build_policy(device='cuda'):
    profile,cfg=load_config()
    lattice_space=LatticeParam(cfg);lattice=LatticePrimitive(lattice_space)
    policy=YopoPolicy(observation_dim=9,action_dim=9,hidden_state=64,lattice_space=lattice_space,
                      lattice_primitive=lattice,lr_schedule=lambda _:profile['optimizer']['learning_rate'],
                      net_arch=[256,256],device=torch.device(device))
    return policy.to(device),profile,cfg


def prepare_observation(obs,policy):
    """Original body-to-primitive order, preserving reversed image-grid indices."""
    values=np.asarray(obs,dtype=np.float32).copy()
    values[:,:3]/=policy.lattice_space.vel_max
    values[:,3:6]/=policy.lattice_space.acc_max
    rotations=np.asarray(policy.lattice_primitive.lattice_Rbp_list)[::-1]
    transformed=np.matmul(values.reshape(-1,1,3,3),rotations)
    return np.ascontiguousarray(transformed.reshape(len(values),15,9).transpose(0,2,1).reshape(-1,9,3,5))


def decode_all(policy,output):
    """Reuse the original differentiable decoder; only concatenate calls."""
    prediction=output[:,:9].reshape(len(output),9,15)
    return torch.stack([policy.pred_to_endstate(prediction[:,:,i],14-i) for i in range(15)],dim=1)


class MapBank:
    def __init__(self,dataset_root,shards,cfg):
        self.maps={}
        for shard in shards:
            folder=Path(dataset_root)/shard['path']
            meta=json.loads((folder/'map.json').read_text(encoding='utf-8'))
            if meta['backend']!='original_main_bucket':raise ValueError('Primary profile requires original bucket SDF')
            values=np.load(folder/'sdf.npy',mmap_mode='r')
            self.maps[shard['id']]=(VoxelSDF(values,meta['origin'],meta['resolution']),np.array(meta['origin']),np.array(meta['upper']))
        self.config=CostConfig(duration=2*cfg['radio_range']/cfg['vel_max'],smooth_weight=cfg['ws'],
                               collision_weight=cfg['wc'],goal_weight=cfg['wg'],length_weight=cfg['wl'],
                               alpha=cfg['alpha'],d0=cfg['d0'],radius=cfg['r'])

    def evaluate(self,end_body,pos,rotation,obs,map_id):
        batch,candidates,_=end_body.shape
        end_body=end_body.reshape(batch,candidates,3,3).astype(float)
        rotation=np.asarray(rotation,dtype=float)
        pos=np.asarray(pos,dtype=float);obs=np.asarray(obs,dtype=float)
        start=np.empty((batch,3,3),dtype=float)
        start[:,:,0]=pos
        start[:,:,1]=np.einsum('bij,bj->bi',rotation,obs[:,:3])
        start[:,:,2]=np.einsum('bij,bj->bi',rotation,obs[:,3:6])
        goal=pos+np.einsum('bij,bj->bi',rotation,10*obs[:,6:9])
        end_world=np.einsum('bij,bmjk->bmik',rotation,end_body)
        end_world[:,:,:,0]+=pos[:,None,:]
        costs=np.empty((batch,candidates));body_grad=np.empty_like(end_body)
        for identifier in np.unique(map_id):
            selected=np.flatnonzero(map_id==identifier)
            sdf,lower,upper=self.maps[int(identifier)]
            count=len(selected)
            repeated_start=np.repeat(start[selected],candidates,axis=0)
            repeated_goal=np.repeat(goal[selected],candidates,axis=0)
            value,gradient,_=cost_and_gradient(repeated_start,end_world[selected].reshape(-1,3,3),repeated_goal,
                                                sdf,lower,upper,self.config)
            costs[selected]=value.reshape(count,candidates)
            # For end_world=R*end_body, dJ/dend_body=R^T*dJ/dend_world.
            body_grad[selected]=np.einsum('bji,bmjk->bmik',rotation[selected],gradient.reshape(count,candidates,3,3))
        return costs,upstream_network_gradient(body_grad.reshape(batch,candidates,9))


class GuidanceCost(torch.autograd.Function):
    @staticmethod
    def forward(ctx,end_body,pos,rotation,obs,map_id,bank):
        cost,gradient=bank.evaluate(end_body.detach().cpu().numpy(),pos,rotation,obs,map_id)
        ctx.save_for_backward(torch.as_tensor(gradient,device=end_body.device,dtype=end_body.dtype))
        return torch.as_tensor(cost,device=end_body.device,dtype=torch.float64)

    @staticmethod
    def backward(ctx,upstream):
        gradient,=ctx.saved_tensors
        return gradient*upstream.to(gradient.dtype).unsqueeze(-1),None,None,None,None,None


def losses(policy,depth,pos,rotation,obs,map_id,bank,profile):
    device=next(policy.parameters()).device
    prepared=torch.from_numpy(prepare_observation(obs,policy)).to(device)
    prediction=policy(depth.to(device),prepared)
    ends=decode_all(policy,prediction)
    cost=GuidanceCost.apply(ends,pos,rotation,obs,map_id,bank)
    score=prediction[:,9].reshape(len(depth),15)
    trajectory=cost.mean()
    score_loss=torch.nn.functional.smooth_l1_loss(score,cost.detach())
    total=profile['trajectory_loss_weight']*trajectory+profile['score_loss_weight']*score_loss
    return total,trajectory,score_loss
