"""Seeded Isaac-equivalent forest geometry, with independent ray/distance queries.

These procedural cylinders and low box shrubs are not original Flightmare
assets. Geometry differences are explicit in the scene manifest.
"""
import numpy as np


def generate(seed, density=1/30, extent=80.):
    rng = np.random.default_rng(seed)
    trees = []
    for _ in range(round(extent * extent * density)):
        x, y = rng.uniform(-extent/2 + 1, extent/2 - 1, 2)
        trees.append([float(x), float(y), float(rng.uniform(.15, .3)), float(rng.uniform(5., 8.))])
    shrubs = []
    for _ in range(round(extent * extent / 100)):
        x, y = rng.uniform(-extent/2 + 1, extent/2 - 1, 2)
        sx, sy, sz = rng.uniform(.5, 1.5), rng.uniform(.5, 1.5), rng.uniform(.3, 1.2)
        shrubs.append([float(x), float(y), float(sz/2), float(sx), float(sy), float(sz)])
    return {"version": 2, "seed": seed, "density_per_m2": density, "extent_m": extent, "tree_sides": 64,
            "trees": trees, "shrubs": shrubs,
            "provenance": "procedural Isaac equivalent; not original Flightmare forest assets"}


def signed_distance(position, scene):
    p = np.asarray(position)
    best = float(p[2])
    for x, y, radius, height in scene["trees"]:
        d = np.array([np.linalg.norm(p[:2] - [x, y]) - radius, abs(p[2] - height/2) - height/2])
        best = min(best, float(min(d.max(), 0) + np.linalg.norm(np.maximum(d, 0))))
    for x, y, z, sx, sy, sz in scene["shrubs"]:
        d = np.abs(p - [x, y, z]) - np.array([sx, sy, sz])/2
        best = min(best, float(min(d.max(), 0) + np.linalg.norm(np.maximum(d, 0))))
    return best


def ray_depth(origin, directions, scene, max_depth=20.):
    """Ray parameter for unnormalised optical-Z rays, not Euclidean range."""
    origin, directions = np.asarray(origin), np.asarray(directions)
    best = np.full(len(directions), max_depth, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        ground = -origin[2] / directions[:, 2]
    with np.errstate(invalid="ignore"):
        ground_points = origin + ground[:, None] * directions
    valid = (ground > .04) & np.all(np.abs(ground_points[:, :2]) <= scene["extent_m"]/2, axis=1)
    best = np.minimum(best, np.where(valid, ground, np.inf))
    a = (directions[:, :2] ** 2).sum(axis=1)
    for x, y, radius, height in scene["trees"]:
        o = origin - [x, y, 0.]
        sides_count = scene.get("tree_sides", 0)
        if sides_count:
            # Exact intersection of the same finite polygon prism authored in USD.
            angles = (np.arange(sides_count) + .5) * 2*np.pi/sides_count
            normals = np.column_stack([np.cos(angles), np.sin(angles), np.zeros(sides_count)])
            normals = np.vstack([normals, [0,0,-1], [0,0,1]])
            limits = np.r_[np.full(sides_count,radius*np.cos(np.pi/sides_count)), 0., height]
            numerator = limits - normals @ o
            denominator = directions @ normals.T
            parallel = np.abs(denominator) < 1e-14
            t = numerator[None,:] / np.where(parallel,1.,denominator)
            enter = np.where(denominator < -1e-14,t,-np.inf).max(axis=1)
            leave = np.where(denominator > 1e-14,t,np.inf).min(axis=1)
            outside = np.any(parallel & (numerator[None,:] < 0),axis=1)
            hit = np.where(enter > .04,enter,leave)
            valid = ~outside & (enter <= leave) & (hit > .04)
            best = np.minimum(best,np.where(valid,hit,np.inf))
            continue
        b = 2 * (directions[:, :2] * o[:2]).sum(axis=1)
        c = (o[:2] ** 2).sum() - radius ** 2
        disc = b*b - 4*a*c
        with np.errstate(divide="ignore", invalid="ignore"):
            root = np.sqrt(np.maximum(disc, 0))
            sides = [(-b-root)/(2*a), (-b+root)/(2*a)]
            caps = [-o[2]/directions[:, 2], (height-o[2])/directions[:, 2]]
        for t in sides:
            z = o[2] + t * directions[:, 2]
            valid = (disc >= 0) & (a > 1e-15) & (t > .04) & (z >= 0) & (z <= height)
            best = np.minimum(best, np.where(valid, t, np.inf))
        for t in caps:
            with np.errstate(invalid="ignore"):
                xy = o[None, :2] + t[:, None] * directions[:, :2]
            valid = (t > .04) & (np.sum(xy*xy, axis=1) <= radius*radius)
            best = np.minimum(best, np.where(valid, t, np.inf))
    for x, y, z, sx, sy, sz in scene["shrubs"]:
        lower = np.array([x-sx/2, y-sy/2, z-sz/2])
        upper = np.array([x+sx/2, y+sy/2, z+sz/2])
        parallel = np.abs(directions) < 1e-15
        safe_d = np.where(parallel, 1., directions)
        t1, t2 = (lower-origin)/safe_d, (upper-origin)/safe_d
        near = np.where(parallel, -np.inf, np.minimum(t1, t2)).max(axis=1)
        far = np.where(parallel, np.inf, np.maximum(t1, t2)).min(axis=1)
        outside = np.any(parallel & ((origin < lower) | (origin > upper)), axis=1)
        t = np.where(near > .04, near, far)
        valid = ~outside & (near <= far) & (t > .04)
        best = np.minimum(best, np.where(valid, t, np.inf))
    return best


def author_scene(stage, scene):
    from pxr import Gf, UsdGeom, UsdPhysics
    def box(path, center, size):
        primitive = UsdGeom.Cube.Define(stage, path)
        primitive.CreateSizeAttr(1.)
        xf = UsdGeom.Xformable(primitive)
        xf.AddTranslateOp().Set(Gf.Vec3d(*center))
        xf.AddScaleOp().Set(Gf.Vec3d(*size))
        primitive.CreateDisplayColorAttr([(.25, .36, .2)])
        UsdPhysics.CollisionAPI.Apply(primitive.GetPrim())
    extent = scene["extent_m"]
    box("/World/Forest/Floor", [0., 0., -.1], [extent, extent, .2])
    for i, (x, y, radius, height) in enumerate(scene["trees"]):
        sides = scene.get("tree_sides", 0)
        if sides:
            primitive = UsdGeom.Mesh.Define(stage, f"/World/Forest/Tree_{i}")
            angles = np.arange(sides)*2*np.pi/sides
            xy = radius*np.column_stack([np.cos(angles),np.sin(angles)]) + [x,y]
            vertices = np.vstack([np.column_stack([xy,np.zeros(sides)]),np.column_stack([xy,np.full(sides,height)])])
            faces = []
            for j in range(sides):
                nxt=(j+1)%sides
                faces.extend([j,nxt,nxt+sides,j+sides])
            faces.extend(list(reversed(range(sides))))
            faces.extend(list(range(sides,2*sides)))
            primitive.CreatePointsAttr(vertices.tolist())
            primitive.CreateFaceVertexCountsAttr([4]*sides+[sides,sides])
            primitive.CreateFaceVertexIndicesAttr(faces)
            primitive.CreateSubdivisionSchemeAttr("none")
            UsdPhysics.CollisionAPI.Apply(primitive.GetPrim())
            continue
        primitive = UsdGeom.Cylinder.Define(stage, f"/World/Forest/Tree_{i}")
        primitive.CreateRadiusAttr(radius)
        primitive.CreateHeightAttr(height)
        primitive.CreateAxisAttr("Z")
        UsdGeom.Xformable(primitive).AddTranslateOp().Set(Gf.Vec3d(x, y, height/2))
        UsdPhysics.CollisionAPI.Apply(primitive.GetPrim())
    for i, shrub in enumerate(scene["shrubs"]):
        box(f"/World/Forest/Shrub_{i}", shrub[:3], shrub[3:])
