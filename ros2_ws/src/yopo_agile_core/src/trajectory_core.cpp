// Numerical code remains upstream; this file only provides POD state and C ABI.
#include <Eigen/Dense>
#include <Eigen/Geometry>
#include <vector>
#include <cstdio>
#include <cmath>
struct TrajectoryExtPoint {
  Eigen::Vector3d position=Eigen::Vector3d::Zero(),velocity=Eigen::Vector3d::Zero(),
    acceleration=Eigen::Vector3d::Zero(),jerk=Eigen::Vector3d::Zero(),snap=Eigen::Vector3d::Zero(),bodyrates=Eigen::Vector3d::Zero();
  Eigen::Quaterniond attitude=Eigen::Quaterniond::Identity();
  double collective_thrust=0,time_from_start=0;
};
enum class FrameID {Body,World};
class TrajectoryExt {
public:
  FrameID frame_id_=FrameID::World;
  bool yawing_enabled_=true;
  unsigned int poly_order_=5,continuity_order_=3;
  std::vector<TrajectoryExtPoint> points_;
  std::vector<Eigen::Vector3d> poly_coeff_;
  void fitPolynomialCoeffs(const unsigned int,const unsigned int);
  void resamplePointsFromPolyCoeffs();
  Eigen::Vector3d evaluatePoly(const double,const int);
  bool setConstantArcLengthSpeed(const double&,const int&,const double&);
};
#include "upstream_methods.inc"

extern "C" int agile_fit(const double* positions,const double* initial,double speed,
                         double* coefficients,double* output) {
  if(!std::isfinite(speed) || speed<=0) return -1;
  try {
    TrajectoryExt trajectory;
    for(int i=0;i<10;++i) {
      // Upstream constructor rebases the 0.1..1.0 predictions by subtracting0.1.
      TrajectoryExtPoint point;point.time_from_start=(i+1)*0.1-0.1;
      point.position=Eigen::Map<const Eigen::Vector3d>(positions+3*i);
      trajectory.points_.push_back(point);
    }
    auto& first=trajectory.points_[0];first.time_from_start=0;
    first.position=Eigen::Map<const Eigen::Vector3d>(initial);
    first.velocity=Eigen::Map<const Eigen::Vector3d>(initial+3);
    first.acceleration=Eigen::Map<const Eigen::Vector3d>(initial+6);
    first.jerk=Eigen::Map<const Eigen::Vector3d>(initial+9);
    trajectory.fitPolynomialCoeffs(5,3);trajectory.resamplePointsFromPolyCoeffs();
    int changed=trajectory.setConstantArcLengthSpeed(speed,10,0.1)?1:0;
    for(int i=0;i<6;++i)for(int axis=0;axis<3;++axis)coefficients[i*3+axis]=trajectory.poly_coeff_[i][axis];
    for(int i=0;i<10;++i) {
      const auto& p=trajectory.points_[i];double* out=output+21*i;
      out[0]=p.time_from_start;
      for(int a=0;a<3;++a){out[1+a]=p.position[a];out[4+a]=p.velocity[a];out[7+a]=p.acceleration[a];out[10+a]=p.jerk[a];out[17+a]=p.bodyrates[a];}
      out[13]=p.attitude.w();out[14]=p.attitude.x();out[15]=p.attitude.y();out[16]=p.attitude.z();out[20]=p.collective_thrust;
      for(int j=0;j<21;++j)if(!std::isfinite(out[j]))return -2;
    }
    return changed;
  } catch(...) {return -3;}
}
