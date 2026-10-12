"""Deterministic forest geometry shared by sensing, physics and presentation."""
import numpy as np


def obstacle_map(seed=7):
    rng = np.random.default_rng(seed)
    obstacles = []
    for x in [6., 11., 16., 21.]:
        for y in [-6., -3., 0., 3., 6.]:
            obstacles.append([x + rng.uniform(-0.5, 0.5), y + rng.uniform(-0.5, 0.5),
                              rng.uniform(0.35, 0.5), rng.uniform(5., 6.)])
    return np.asarray(obstacles)


def build_scene(stage, obstacles, collision=True):
    from pxr import Gf, UsdGeom, UsdPhysics, UsdLux
    ground = UsdGeom.Cube.Define(stage, "/World/Floor")
    ground.CreateSizeAttr(1.)
    xf = UsdGeom.Xformable(ground)
    xf.AddTranslateOp().Set(Gf.Vec3d(11., 0., -0.15))
    xf.AddScaleOp().Set(Gf.Vec3d(34., 22., 0.3))
    ground.CreateDisplayColorAttr([(0.13, 0.18, 0.22)])
    if collision:
        UsdPhysics.CollisionAPI.Apply(ground.GetPrim())
    for i, (x, y, radius, height) in enumerate(obstacles):
        cylinder = UsdGeom.Cylinder.Define(stage, f"/World/Forest/Tree_{i:02d}")
        cylinder.CreateRadiusAttr(float(radius))
        cylinder.CreateHeightAttr(float(height))
        cylinder.CreateAxisAttr("Z")
        UsdGeom.Xformable(cylinder).AddTranslateOp().Set(Gf.Vec3d(float(x), float(y), float(height / 2)))
        cylinder.CreateDisplayColorAttr([(0.22, 0.34, 0.32)])
        if collision:
            UsdPhysics.CollisionAPI.Apply(cylinder.GetPrim())
    distant = UsdLux.DistantLight.Define(stage, "/World/Sun")
    distant.CreateIntensityAttr(2200.)
    distant.CreateAngleAttr(1.5)
    UsdGeom.Xformable(distant).AddRotateXYZOp().Set(Gf.Vec3f(-35., -25., 15.))
    dome = UsdLux.DomeLight.Define(stage, "/World/Sky")
    dome.CreateIntensityAttr(650.)


def clearance(position, obstacles, vehicle_radius=0.12):
    rho = np.linalg.norm(obstacles[:, :2] - position[:2], axis=1) - obstacles[:, 2]
    dz = np.abs(position[2] - obstacles[:, 3] / 2) - obstacles[:, 3] / 2
    d = np.stack([rho, dz], axis=1)
    signed = np.minimum(d.max(axis=1), 0.) + np.linalg.norm(np.maximum(d, 0.), axis=1)
    return float(min(signed.min() - vehicle_radius, position[2] - vehicle_radius))


def depth_camera(stage):
    from pxr import UsdGeom
    camera = UsdGeom.Camera.Define(stage, "/World/DepthCamera")
    camera.CreateFocalLengthAttr(18.)
    camera.CreateHorizontalApertureAttr(36.)
    camera.CreateVerticalApertureAttr(20.25)
    camera.CreateClippingRangeAttr((0.04, 40.))
    transform = UsdGeom.Xformable(camera)
    return transform.AddTranslateOp(), transform.AddOrientOp()


def set_camera_pose(ops, position, rotation_wb):
    from pxr import Gf
    from scipy.spatial.transform import Rotation
    p = position + rotation_wb @ np.array([0.15, 0., 0.03])
    usd_rotation = np.column_stack([-rotation_wb[:, 1], rotation_wb[:, 2], -rotation_wb[:, 0]])
    xyzw = Rotation.from_matrix(usd_rotation).as_quat()
    ops[0].Set(Gf.Vec3d(*p.tolist()))
    ops[1].Set(Gf.Quatf(float(xyzw[3]), Gf.Vec3f(*xyzw[:3].tolist())))
