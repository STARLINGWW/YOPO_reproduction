"""Author the common force-driven vehicle; used only inside initialized Isaac."""
import numpy as np


def author_vehicle(stage,config,path='/World/Quadrotor',position=(0.,0.,3.),orientation_wxyz=None):
    from pxr import Gf,UsdGeom,UsdPhysics,PhysxSchema
    root=UsdGeom.Xform.Define(stage,path)
    # Place the authored actor before World.reset's initialization step. Starting
    # it at the origin would intersect the floor and leave a stale contact sample.
    UsdGeom.Xformable(root).AddTranslateOp().Set(Gf.Vec3d(*map(float,position)))
    if orientation_wxyz is not None:
        q=orientation_wxyz
        UsdGeom.Xformable(root).AddOrientOp().Set(Gf.Quatf(float(q[0]),Gf.Vec3f(*map(float,q[1:]))))
    UsdPhysics.RigidBodyAPI.Apply(root.GetPrim()).CreateRigidBodyEnabledAttr(True)
    mass=UsdPhysics.MassAPI.Apply(root.GetPrim());mass.CreateMassAttr(config['mass_kg'])
    mass.CreateCenterOfMassAttr(Gf.Vec3f(0,0,0));mass.CreateDiagonalInertiaAttr(Gf.Vec3f(*config['inertia_kgm2']))
    body=PhysxSchema.PhysxRigidBodyAPI.Apply(root.GetPrim())
    body.CreateEnableGyroscopicForcesAttr(True);body.CreateLinearDampingAttr(0.)
    # USD PhysX maxAngularVelocity is degrees/s, unlike RigidPrim rates (rad/s).
    body.CreateAngularDampingAttr(0.);body.CreateMaxAngularVelocityAttr(float(np.rad2deg(200.)))
    body.CreateSolverPositionIterationCountAttr(8);body.CreateSolverVelocityIterationCountAttr(4)
    def box(name,size,color,collider=False):
        prim=UsdGeom.Cube.Define(stage,path+'/'+name);prim.CreateSizeAttr(1.)
        UsdGeom.Xformable(prim).AddScaleOp().Set(Gf.Vec3d(*size));prim.CreateDisplayColorAttr([color])
        if collider:UsdPhysics.CollisionAPI.Apply(prim.GetPrim())
    box('Body',(.18,.12,.08),(.08,.15,.2),True)
    arm=config['arm_length_m'];radius=config['propeller_radius_m']
    box('ArmX',(2*arm,.02,.025),(.2,.3,.4),True)
    box('ArmY',(.02,2*arm,.025),(.2,.3,.4),True)
    for i,position in enumerate([(arm,0,0),(-arm,0,0),(0,arm,0),(0,-arm,0)]):
        sphere=UsdGeom.Sphere.Define(stage,f'{path}/Rotor_{i}')
        sphere.CreateRadiusAttr(radius)
        UsdGeom.Xformable(sphere).AddTranslateOp().Set(Gf.Vec3d(*position))
        sphere.CreateDisplayColorAttr([(.8,.45,.05) if i==0 else (.15,.24,.3)])
        UsdPhysics.CollisionAPI.Apply(sphere.GetPrim())
    return root


def author_floor(stage):
    from pxr import Gf,UsdGeom,UsdPhysics
    floor=UsdGeom.Cube.Define(stage,'/World/Floor');floor.CreateSizeAttr(1.)
    xf=UsdGeom.Xformable(floor);xf.AddTranslateOp().Set(Gf.Vec3d(0,0,-.1));xf.AddScaleOp().Set(Gf.Vec3d(100,100,.2))
    UsdPhysics.CollisionAPI.Apply(floor.GetPrim())


def read_state(body):
    from scipy.spatial.transform import Rotation
    p,q=body.get_world_poses();p=np.asarray(p[0],float);q=np.asarray(q[0],float)
    rotation=Rotation.from_quat(q[[1,2,3,0]]).as_matrix()
    velocity=np.asarray(body.get_linear_velocities()[0],float)
    rates=rotation.T@np.asarray(body.get_angular_velocities()[0],float)
    return p,q,rotation,velocity,rates
