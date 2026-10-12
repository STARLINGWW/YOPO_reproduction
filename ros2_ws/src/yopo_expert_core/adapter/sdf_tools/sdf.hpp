#pragma once
#include <arc_utilities/voxel_grid.hpp>
#include <cmath>
#include <memory>
#include <vector>
namespace sdf_tools {
class SignedDistanceField {
  VoxelGrid::VoxelGrid<float> field_;
  double resolution_;
  static Eigen::Isometry3d origin(const double* p) {
    auto transform=Eigen::Isometry3d::Identity();transform.translation()=Eigen::Map<const Eigen::Vector3d>(p);return transform;
  }
public:
  SignedDistanceField(const float* values,const int64_t* shape,const double* p,double resolution):
    field_(origin(p),resolution,shape[0],shape[1],shape[2],0.0f,INFINITY),resolution_(resolution) {
    std::vector<float> data(values,values+shape[0]*shape[1]*shape[2]);
    if(!field_.SetRawData(data))throw std::runtime_error("Field shape mismatch");
  }
  float Get(int64_t x,int64_t y,int64_t z) const {return field_.GetImmutable(x,y,z).first;}
  std::pair<float,bool> GetSafe(double x,double y,double z) const {return field_.GetImmutable(x,y,z);}
  int64_t GetNumXCells() const{return field_.GetNumXCells();}
  int64_t GetNumYCells() const{return field_.GetNumYCells();}
  int64_t GetNumZCells() const{return field_.GetNumZCells();}
  double GetResolution() const{return resolution_;}
  std::vector<double> GetGradient(int64_t x_index,int64_t y_index,int64_t z_index,bool enable_edge_gradients) const;
  std::vector<double> GetGradient(double x,double y,double z,bool edges) const {
    auto index=field_.LocationToGridIndex(x,y,z);
    if(index.size()!=3)return {0.,0.,0.};
    return GetGradient(index[0],index[1],index[2],edges);
  }
};
}
