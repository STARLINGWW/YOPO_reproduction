// Evaluate the unchanged upstream GradTrajOptimizer with an analytic plane.
#include <flightlib/grad_traj_optimization/grad_traj_optimizer.h>
#include <iomanip>
#include <iostream>

int main(int argc,char** argv) {
  if(argc!=2) return 2;
  const YAML::Node config=YAML::LoadFile(argv[1]);
  GradTrajOptimizer optimizer(config);
  optimizer.setSignedDistanceField(std::make_shared<sdf_tools::SignedDistanceField>(),.2);
  optimizer.setBoundary(Eigen::Vector3d(-100,-100,-100),Eigen::Vector3d(100,100,100));
  std::vector<double> start(9),end(9),gradient;
  std::cout<<std::setprecision(17)<<'[';
  bool first=true;
  while(std::cin>>start[0]) {
    for(int i=1;i<9;++i) if(!(std::cin>>start[i])) return 3;
    for(int i=0;i<9;++i) if(!(std::cin>>end[i])) return 3;
    double x,y,z;
    if(!(std::cin>>x>>y>>z)) return 3;
    optimizer.setGoal(Eigen::Vector3d(x,y,z));
    double cost;
    optimizer.getCostAndGradient(start,end,cost,gradient);
    if(!first) std::cout<<',';
    first=false;
    std::cout<<"{\"cost\":"<<cost<<",\"gradient\":[";
    for(int i=0;i<9;++i) {if(i) std::cout<<',';std::cout<<gradient[i];}
    std::cout<<"]}";
  }
  std::cout<<"]\n";
}
