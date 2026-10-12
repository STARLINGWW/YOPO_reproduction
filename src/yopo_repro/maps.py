"""Surface pointcloud and point-occupied ESDF matching the upstream data model.

Occupancy is based on surface samples, as in main/SdfConstruction; obstacle
interiors are not silently filled. Use actual scene solids for collision truth.
"""
from pathlib import Path
import numpy as np


def surface_points(scene, spacing=.1):
    if spacing <= 0:
        raise ValueError("spacing must be positive")
    chunks = []
    extent = scene["extent_m"]
    grid = np.linspace(-extent/2, extent/2, int(np.ceil(extent/spacing))+1)
    x, y = np.meshgrid(grid, grid, indexing="ij")
    chunks.append(np.column_stack([x.ravel(), y.ravel(), np.zeros(x.size)]))
    for cx, cy, radius, height in scene["trees"]:
        sides = scene["tree_sides"]
        angles = np.arange(sides)*2*np.pi/sides
        vertices = radius*np.column_stack([np.cos(angles),np.sin(angles)])+[cx,cy]
        z = np.linspace(0.,height,int(np.ceil(height/spacing))+1)
        for i in range(sides):
            a,b=vertices[i],vertices[(i+1)%sides]
            u=np.linspace(0.,1.,int(np.ceil(np.linalg.norm(b-a)/spacing))+1)
            xy=a[None,:]+u[:,None]*(b-a)
            points=np.empty((len(xy),len(z),3))
            points[:,:,:2]=xy[:,None,:]
            points[:,:,2]=z[None,:]
            chunks.append(points.reshape(-1,3))
        # Sample polygon cap interiors (not the filled cylinder volume).
        offsets=np.linspace(-radius,radius,int(np.ceil(2*radius/spacing))+1)
        xx,yy=np.meshgrid(offsets,offsets,indexing="ij")
        xy=np.column_stack([xx.ravel(),yy.ravel()])
        normals=np.column_stack([np.cos(angles+np.pi/sides),np.sin(angles+np.pi/sides)])
        inside=np.all(xy@normals.T<=radius*np.cos(np.pi/sides)+1e-12,axis=1)
        xy=xy[inside]+[cx,cy]
        for zz in (0.,height):
            chunks.append(np.column_stack([xy,np.full(len(xy),zz)]))
    for cx,cy,cz,sx,sy,sz in scene["shrubs"]:
        center=np.array([cx,cy,cz]);size=np.array([sx,sy,sz])
        for axis in range(3):
            other=[i for i in range(3) if i!=axis]
            u=np.linspace(-size[other[0]]/2,size[other[0]]/2,int(np.ceil(size[other[0]]/spacing))+1)
            v=np.linspace(-size[other[1]]/2,size[other[1]]/2,int(np.ceil(size[other[1]]/spacing))+1)
            uu,vv=np.meshgrid(u,v,indexing="ij")
            for sign in (-1,1):
                p=np.tile(center,(uu.size,1))
                p[:,axis]+=sign*size[axis]/2
                p[:,other[0]]+=uu.ravel();p[:,other[1]]+=vv.ravel()
                chunks.append(p)
    return np.vstack(chunks).astype(np.float32)


def write_ply(path, points):
    path=Path(path)
    with path.open("xb") as file:
        file.write(("ply\nformat binary_little_endian 1.0\nelement vertex %d\n"
                    "property float x\nproperty float y\nproperty float z\nend_header\n"%len(points)).encode())
        file.write(np.asarray(points,dtype="<f4").tobytes())


def pointcloud_esdf(points, resolution=.2):
    from scipy.ndimage import distance_transform_edt
    points=np.asarray(points)
    origin=points.min(axis=0).astype(float)
    upper=points.max(axis=0).astype(float)
    shape=np.ceil((upper-origin)/resolution).astype(int)
    if np.any(shape<2):
        raise ValueError("ESDF requires a 3D pointcloud extent")
    # Upstream voxel_grid truncates positive coordinates into cells and ignores
    # points at the exclusive upper boundary. Preserve that convention.
    indices=np.trunc((points-origin)*(1.0/resolution)).astype(np.int64)
    valid=np.all((indices>=0)&(indices<shape),axis=1)
    occupancy=np.zeros(tuple(shape),dtype=bool)
    occupancy[tuple(indices[valid].T)]=True
    outside=distance_transform_edt(~occupancy)*resolution
    inside=distance_transform_edt(occupancy)*resolution
    sdf=(outside-inside).astype(np.float32)
    return sdf,occupancy,origin,upper


class VoxelSDF:
    """Nearest-cell values and central/one-sided finite-difference gradients."""
    def __init__(self, values, origin, resolution, index_mode="upstream_truncate"):
        self.values=np.asarray(values)
        self.origin=np.asarray(origin,dtype=float)
        self.resolution=float(resolution)
        if index_mode not in ("upstream_truncate", "floor"):
            raise ValueError("unknown indexing convention")
        self.index_mode=index_mode

    def query(self, points):
        points=np.atleast_2d(points)
        local=(points-self.origin)*(1.0/self.resolution)
        indices=(np.trunc(local) if self.index_mode=="upstream_truncate" else np.floor(local)).astype(np.int64)
        shape=np.array(self.values.shape)
        valid=np.all((indices>=0)&(indices<shape),axis=1)
        safe=np.clip(indices,0,shape-1)
        values=np.asarray(self.values[tuple(safe.T)],dtype=float)
        gradient=np.zeros_like(points,dtype=float)
        for axis in range(3):
            lo,hi=safe.copy(),safe.copy()
            lo[:,axis]=np.maximum(lo[:,axis]-1,0)
            hi[:,axis]=np.minimum(hi[:,axis]+1,shape[axis]-1)
            gradient[:,axis]=(self.values[tuple(hi.T)]-self.values[tuple(lo.T)]) / ((hi[:,axis]-lo[:,axis])*self.resolution)
        values[~valid]=np.inf;gradient[~valid]=0
        return values,gradient,valid
