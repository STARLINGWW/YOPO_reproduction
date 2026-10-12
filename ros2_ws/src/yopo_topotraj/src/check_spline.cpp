#include <bspline/non_uniform_bspline.h>
#include <poly_traj/polynomial_traj.h>
#include <cmath>
#include <iostream>

int main() {
  Eigen::MatrixXd points(9,3);
  for(int i=0;i<9;++i) points.row(i)<<.2*i,.4*i,3.;
  fast_planner::NonUniformBspline curve(points,3,.2);
  auto velocity=curve.getDerivative();
  double start,end;curve.getTimeSpan(start,end);
  double max_error=0.;
  for(int i=1;i<50;++i) {
    double t=start+(end-start)*i/50;
    auto measured=velocity.evaluateDeBoor(t);
    max_error=std::max(max_error,(measured-Eigen::Vector3d(1.,2.,0.)).norm());
    Eigen::VectorXd numerical=(curve.evaluateDeBoor(t+1e-5)-curve.evaluateDeBoor(t-1e-5))/(2e-5);
    max_error=std::max(max_error,(measured-numerical).norm());
  }
  PolynomialTraj polynomial;
  polynomial.reset();
  polynomial.addSegment({0.,0.,1.,0.,0.,0.},{0.,0.,0.,0.,0.,0.},{0.,0.,0.,0.,0.,0.},2.);
  const double jerk_error=std::abs(polynomial.getJerk()-72.);
  const bool ok=max_error<1e-8 && jerk_error<1e-8;
  std::cout<<"{\"status\":\""<<(ok?"passed":"failed")<<"\",\"max_derivative_error\":"<<max_error<<",\"polynomial_jerk_error\":"<<jerk_error<<",\"scope\":\"ported numerical spline components only\"}\n";
  return ok?0:1;
}
