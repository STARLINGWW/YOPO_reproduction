#include <path_searching/topo_prm.h>
#include <bspline_opt/bspline_optimizer.h>
#include <fstream>
#include <stdexcept>

static void require(bool ok, const char* reason) { if (!ok) throw std::runtime_error(reason); }
static double smoothness(const Eigen::MatrixXd& p) {
  double value=0;
  for (int i=0;i+3<p.rows();++i)
    value += (p.row(i+3)-3*p.row(i+2)+3*p.row(i+1)-p.row(i)).squaredNorm();
  return value;
}
int main(int argc, char** argv) {
  rclcpp::init(argc, argv);
  auto node=std::make_shared<rclcpp::Node>("topotraj_components");
  auto map=std::make_shared<SDFMap>(); map->initMap(node); map->resetBuffer();
  // Diagnostic fixture only. Online planner must populate its map from sensors.
  for(double x=-0.45;x<0.5;x+=0.1)
    for(double y=-0.95;y<1.0;y+=0.1)
      for(double z=-0.95;z<5.0;z+=0.1) map->setOccupied(Eigen::Vector3d(x,y,z));
  map->updateESDF3d();
  auto env=std::make_shared<fast_planner::EDTEnvironment>(); env->setMap(map);
  double dist; Eigen::Vector3d grad, pos(-2.35,0.15,2.15);
  env->evaluateEDTWithGrad(pos,-1,dist,grad);
  double fd_error=0;
  for(int k=0;k<3;++k) {
    auto a=pos,b=pos; a[k]+=1e-5; b[k]-=1e-5;
    double da,db; Eigen::Vector3d g;
    env->evaluateEDTWithGrad(a,-1,da,g); env->evaluateEDTWithGrad(b,-1,db,g);
    fd_error=std::max(fd_error,std::abs((da-db)/2e-5-grad[k]));
  }
  require(fd_error<1e-6,"ESDF interpolation gradient mismatch");
  require(std::abs(dist-1.9)<0.11,"ESDF wall distance incorrect");
  fast_planner::TopologyPRM prm; prm.setEnvironment(env); prm.init(node);
  std::list<fast_planner::GraphNode::Ptr> graph;
  std::vector<std::vector<Eigen::Vector3d>> raw,filtered,selected;
  prm.findTopoPaths(Eigen::Vector3d(-3,0,2),Eigen::Vector3d(3,0,2),{},{},graph,raw,filtered,selected);
  require(!selected.empty(),"No obstacle-detour path");
  double minimum=1e9;
  for(const auto& path:selected) for(size_t j=1;j<path.size();++j) {
    int steps=std::max(1,int(std::ceil((path[j]-path[j-1]).norm()/0.02)));
    for(int k=0;k<=steps;++k) {
      Eigen::Vector3d p=path[j-1]+(path[j]-path[j-1])*double(k)/steps;
      minimum=std::min(minimum,map->getDistance(p));
    }
  }
  std::cout << "MEASURED_PATH_CLEARANCE " << minimum << std::endl;
  // Original PRM visibility/shortcut threshold is one voxel, not clearance_.
  // clearance_ only rejects sampled roadmap vertices. Do not alter the method.
  require(minimum>=map->getResolution()-1e-9,"Selected path intersects occupied voxels");
  fast_planner::BsplineOptimizer opt; opt.setParam(node); opt.setEnvironment(env);
  Eigen::MatrixXd points(12,3);
  for(int i=0;i<12;++i) points.row(i)=Eigen::Vector3d(-4+0.6*i,3+(i%2?0.5:-0.5),2);
  double before=smoothness(points);
  auto result=opt.BsplineOptimizeTraj(points,0.3,fast_planner::BsplineOptimizer::SMOOTHNESS,1,1);
  double after=smoothness(result);
  require(result.allFinite() && after<before*0.1,"Optimizer did not reduce jerk cost");
  require((points.topRows(3)-result.topRows(3)).norm()==0 &&
          (points.bottomRows(3)-result.bottomRows(3)).norm()==0,"Optimizer changed fixed boundary points");
  std::ofstream out("/workspace/artifacts/environment/topotraj_components.json");
  out << "{\"status\":\"passed\",\"scope\":\"original ESDF, topology search and NLopt component fixtures; not online benchmark\","
      << "\"gradient_max_error\":" << fd_error << ",\"selected_paths\":" << selected.size()
      << ",\"minimum_path_grid_clearance_m\":" << minimum << ",\"smoothness_before\":" << before
      << ",\"smoothness_after\":" << after << "}\n";
  rclcpp::shutdown(); return 0;
}
