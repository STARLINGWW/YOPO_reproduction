"""Batched numerical port of pinned main GradTrajOptimizer.

The external ESDF object supplies nearest-cell distances and finite-difference
gradients. This module returns raw world-frame gradients. Upstream's asymmetric
network-gradient clipping is a separate operation after rotation to body frame.
Full C++ oracle validation is required before formal training.
"""
from dataclasses import dataclass
from functools import lru_cache
import numpy as np
from .quintic import matrices

@lru_cache(maxsize=16)
def _cost_matrices(duration):
    return matrices(duration)


@dataclass(frozen=True)
class CostConfig:
    duration: float = 8./6.
    smooth_weight: float = .00004
    collision_weight: float = .001
    goal_weight: float = .0002
    length_weight: float = 0.
    alpha: float = 10.
    d0: float = 1.2
    radius: float = .6
    offset: float = .001


def boundary_distance(points, lower, upper):
    return np.minimum(points-lower,upper-points).min(axis=-1)


def boundary_gradient(points, lower, upper, resolution):
    """Upstream boundary stencil, including its particular cross-axis choice."""
    output=np.zeros_like(points)
    for axis,other in [(0,1),(1,0),(2,1)]:
        delta=np.zeros(3);delta[axis]=resolution
        cross=np.zeros(3);cross[other]=resolution
        central=boundary_distance(points+delta,lower,upper)-boundary_distance(points-delta,lower,upper)
        positive=boundary_distance(points+delta+cross,lower,upper)-boundary_distance(points-delta+cross,lower,upper)
        negative=boundary_distance(points+delta-cross,lower,upper)-boundary_distance(points-delta-cross,lower,upper)
        output[...,axis]=(10*central+3*positive+3*negative)/(32*resolution)
    return output


def cost_and_gradient(start, end, goal, sdf, lower, upper, config=CostConfig()):
    """Inputs [batch,axis,pva], goal[batch,xyz]; outputs cost and dcost/dend."""
    start,end,goal=[np.asarray(x,dtype=float) for x in (start,end,goal)]
    if start.ndim!=3 or start.shape[1:]!=(3,3) or end.shape!=start.shape or goal.shape!=(len(start),3):
        raise ValueError('Expected start/end [B,3,3] and goal[B,3]')
    if not all(np.isfinite(x).all() for x in (start,end,goal)):
        raise ValueError('Non-finite trajectory input')
    lower,upper=np.asarray(lower),np.asarray(upper)
    L,H,R=_cost_matrices(config.duration)
    boundary=np.concatenate([start,end],axis=-1)
    coefficients=boundary@L.T
    smooth=np.einsum('bai,ij,baj->b',boundary,R,boundary)
    smooth_grad=(2*boundary@R)[...,3:]
    dt=config.duration/30
    times=.001+np.arange(30)*dt
    basis=np.stack([times**i for i in range(6)],axis=-1)
    # Upstream getPositionFromCoeff uses float intermediates even though Eigen
    # coefficients and trajectory Jacobians are doubles.
    position=np.einsum('ti,bai->bta',basis,coefficients).astype(np.float32).astype(float)
    flat=position.reshape(-1,3)
    distances,gradients,valid=sdf.query(np.clip(flat,lower,upper))
    distance_to_bounds=boundary_distance(flat,lower,upper)
    use_bounds=distance_to_bounds<distances
    # The original unchecked gradient vector is empty for an out-of-grid query.
    # Here boundary handling replaces it before use, avoiding undefined access.
    if not np.all(valid | use_bounds):
        raise ValueError('Invalid SDF query without a boundary replacement')
    distances[use_bounds]=distance_to_bounds[use_bounds]
    gradients[use_bounds]=boundary_gradient(flat[use_bounds],lower,upper,sdf.resolution)
    penalty=config.alpha*np.exp(-(distances-config.d0)/config.radius)
    collision=penalty.reshape(len(start),-1).sum(axis=1)*dt
    spatial_grad=(-penalty/config.radius)[:,None]*gradients
    spatial_grad=spatial_grad.reshape(len(start),30,3)
    jacobian=basis@L[:,3:]
    collision_grad=np.einsum('bta,td->bad',spatial_grad,jacobian)*dt
    delta_goal=end[:,:,0]-goal
    goal_cost=np.sum(delta_goal**2,axis=1)
    goal_grad=np.zeros_like(end);goal_grad[:,:,0]=2*delta_goal
    delta_position=end[:,:,0]-start[:,:,0]
    length=np.exp(-np.sum(delta_position[:,:2]**2,axis=1)/100.)
    length_grad=np.zeros_like(end)
    length_grad[:,:2,0]=(-2/100)*delta_position[:,:2]*length[:,None]
    total=(config.smooth_weight*smooth+config.collision_weight*collision+
           config.goal_weight*goal_cost+config.length_weight*length+config.offset)
    gradient=(config.smooth_weight*smooth_grad+config.collision_weight*collision_grad+
              config.goal_weight*goal_grad+config.length_weight*length_grad)
    detail={'smooth':smooth,'collision':collision,'goal':goal_cost,'length':length}
    return total,gradient,detail


def upstream_network_gradient(raw_body_gradient):
    """Match np.minimum(grad,1.0), not a symmetric [-1,1] clip."""
    return np.minimum(raw_body_gradient,1.0)
