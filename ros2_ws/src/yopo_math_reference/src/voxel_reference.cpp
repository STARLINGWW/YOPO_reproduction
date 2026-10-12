// Executes the original (unmodified) upstream VoxelGrid implementation.
#include <arc_utilities/voxel_grid.hpp>
#include <cmath>
#include <iomanip>
#include <iostream>

int main() {
  Eigen::Isometry3d origin = Eigen::Isometry3d::Identity();
  origin.translation() = Eigen::Vector3d(-1.0, -2.0, -3.0);
  VoxelGrid::VoxelGrid<float> grid(origin, 0.2, int64_t(7), int64_t(8), int64_t(9), 0.0f, INFINITY);
  for(int64_t i=0;i<7;++i) for(int64_t j=0;j<8;++j) for(int64_t k=0;k<9;++k)
    grid.SetValue(i,j,k,float(std::sin(.3*i)+.1*j*j-.2*k));
  double x,y,z;
  bool first=true;
  std::cout << std::setprecision(17) << '[';
  while(std::cin >> x >> y >> z) {
    auto query = grid.GetImmutable(x,y,z);
    if(!first) std::cout << ',';
    first=false;
    if(query.second) std::cout << "{\"valid\":true,\"value\":" << query.first << '}';
    else std::cout << "{\"valid\":false,\"value\":null}";
  }
  std::cout << "]\n";
}
