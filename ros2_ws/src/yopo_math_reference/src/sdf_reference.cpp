// ROS-independent harness around the unchanged upstream distance-transform functions.
#include <arc_utilities/voxel_grid.hpp>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <fstream>
#include <string>
namespace sdf_tools {
class CollisionMapGrid {
public:
  struct bucket_cell { uint32_t location[3]; uint32_t closest_point[3]; double distance_square; int32_t update_direction; };
  using DistanceField=VoxelGrid::VoxelGrid<bucket_cell>;
  VoxelGrid::VoxelGrid<int> collision_field_;
  CollisionMapGrid(int64_t nx,int64_t ny,int64_t nz):collision_field_(.2,nx,ny,nz,0){}
  double GetResolution() const { return collision_field_.GetCellSizes()[0]; }
  DistanceField BuildDistanceField(const std::vector<VoxelGrid::GRID_INDEX>&) const;
  std::vector<std::vector<std::vector<std::vector<int>>>> MakeNeighborhoods() const;
  int GetDirectionNumber(int,int,int) const;
  double ComputeDistanceSquared(int32_t,int32_t,int32_t,int32_t,int32_t,int32_t) const;
};
#include "sdf_distance_functions.inc"
}

int main(int argc,char** argv) {
  int64_t nx,ny,nz;
  const bool binary=argc==7 && std::string(argv[1])=="--binary";
  std::vector<unsigned char> cells;
  std::ofstream binary_output;
  if(binary) {
    nx=std::stoll(argv[4]);ny=std::stoll(argv[5]);nz=std::stoll(argv[6]);
    if(nx<2||ny<2||nz<2||nx*ny*nz>40000000) return 3;
    cells.resize(nx*ny*nz);
    std::ifstream input(argv[2],std::ios::binary);
    input.read(reinterpret_cast<char*>(cells.data()),cells.size());
    if(input.gcount()!=static_cast<std::streamsize>(cells.size())) return 4;
    binary_output.open(argv[3],std::ios::binary);
    if(!binary_output) return 6;
  } else {
    if(!(std::cin>>nx>>ny>>nz)) return 2;
    if(nx<2||ny<2||nz<2||nx*ny*nz>1000000) return 3;
  }
  sdf_tools::CollisionMapGrid map(nx,ny,nz);
  std::vector<VoxelGrid::GRID_INDEX> filled,free;
  for(int64_t x=0;x<nx;++x) for(int64_t y=0;y<ny;++y) for(int64_t z=0;z<nz;++z) {
    int occupied;
    if(binary) occupied=cells[(x*ny+y)*nz+z];
    else if(!(std::cin>>occupied)) return 4;
    (occupied?filled:free).emplace_back(x,y,z);
  }
  if(filled.empty()||free.empty()) return 5;
  auto positive=map.BuildDistanceField(filled);
  auto negative=map.BuildDistanceField(free);
  if(!binary) std::cout<<std::setprecision(9)<<'[';
  bool first=true;
  for(int64_t x=0;x<nx;++x) for(int64_t y=0;y<ny;++y) for(int64_t z=0;z<nz;++z) {
    float d=float((std::sqrt(positive.GetImmutable(x,y,z).first.distance_square)
                  -std::sqrt(negative.GetImmutable(x,y,z).first.distance_square))*.2);
    if(binary) binary_output.write(reinterpret_cast<const char*>(&d),sizeof(d));
    else {if(!first) std::cout<<','; first=false;std::cout<<d;}
  }
  if(!binary) std::cout<<"]\n";
  else std::cout<<"{\"backend\":\"upstream_bucket\",\"voxels\":"<<nx*ny*nz<<"}\n";
}
