#include <so3_control/SO3Control.h>
extern "C" void so3_reference(const double* state,const double* reference,double yaw,
                              const double* gains,double mass,double gravity,double* out) {
  SO3Control control;control.setMass(mass);control.setGravity(gravity);
  control.setPosition(Eigen::Map<const Eigen::Vector3d>(state));
  control.setVelocity(Eigen::Map<const Eigen::Vector3d>(state+3));
  control.setAcc(Eigen::Map<const Eigen::Vector3d>(state+6));
  control.calculateControl(Eigen::Map<const Eigen::Vector3d>(reference),Eigen::Map<const Eigen::Vector3d>(reference+3),
    Eigen::Map<const Eigen::Vector3d>(reference+6),yaw,0.,Eigen::Map<const Eigen::Vector3d>(gains),Eigen::Map<const Eigen::Vector3d>(gains+3));
  auto force=control.getComputedForce();auto rotation=control.getComputedOrientation().toRotationMatrix();
  for(int k=0;k<3;++k)out[k]=force[k];
  for(int row=0;row<3;++row)for(int col=0;col<3;++col)out[3+row*3+col]=rotation(row,col);
}
