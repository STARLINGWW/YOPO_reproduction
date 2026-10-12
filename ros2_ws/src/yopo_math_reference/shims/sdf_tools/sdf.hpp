#pragma once
// Analytic plane test double, NOT a replacement for the upstream ESDF library.
// It isolates original trajectory cost/Jacobian code from ROS1 visualization
// and serialization headers. Real voxel queries have a separate oracle.
#include <memory>
#include <utility>
#include <vector>
namespace sdf_tools {
class SignedDistanceField {
public:
  std::pair<float,bool> GetSafe(double x,double y,double z) const {
    return {static_cast<float>(z),true};
  }
  std::vector<double> GetGradient(double x,double y,double z,bool edges) const {
    return {0.0,0.0,1.0};
  }
};
}
