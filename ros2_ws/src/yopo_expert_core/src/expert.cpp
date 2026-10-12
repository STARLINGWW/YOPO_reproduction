#include <flightlib/grad_traj_optimization/grad_traj_optimizer.h>
#include <nlopt.hpp>
#include <chrono>
#include <array>
#include <algorithm>
#include <limits>
#include <string>
namespace sdf_tools {
#include "original_gradient.inc"
}
namespace {
thread_local std::string error;
struct Context {
  YAML::Node config;
  std::shared_ptr<sdf_tools::SignedDistanceField> field;
  std::unique_ptr<GradTrajOptimizer> cost;
  std::array<double,9> scale;
};
struct Objective {
  Context* context;std::vector<double> start;
  int evaluations=0,nonfinite=0;
  double best=std::numeric_limits<double>::infinity();std::vector<double> best_x;
  double evaluate(const std::vector<double>& x,std::vector<double>& gradient) {
    double value;context->cost->getCostAndGradient(start,x,value,gradient);++evaluations;
    bool finite=std::isfinite(value);
    for(double g:gradient)finite=finite&&std::isfinite(g);
    if(!finite){++nonfinite;gradient.assign(9,0.);return 1e100;}
    if(value<best){best=value;best_x=x;}return value;
  }
  static double callback(const std::vector<double>& x,std::vector<double>& grad,void* p) {
    auto& self=*static_cast<Objective*>(p);std::vector<double> g;double value=self.evaluate(x,g);
    if(!grad.empty())grad=g;return value;
  }
};
}
extern "C" const char* expert_error(){return error.c_str();}
extern "C" void* expert_create(const char* yaml,const float* values,const int64_t* shape,const double* origin,const double* upper,double resolution) {
  try {
    auto object=std::make_unique<Context>();object->config=YAML::LoadFile(yaml);
    object->field=std::make_shared<sdf_tools::SignedDistanceField>(values,shape,origin,resolution);
    object->cost=std::make_unique<GradTrajOptimizer>(object->config);
    object->cost->setSignedDistanceField(object->field,resolution);
    object->cost->setBoundary(Eigen::Map<const Eigen::Vector3d>(origin),Eigen::Map<const Eigen::Vector3d>(upper));
    const double radius=object->config["radio_range"].as<double>(),velocity=object->config["vel_max"].as<double>();
    for(int i=0;i<3;++i){object->scale[3*i]=radius;object->scale[3*i+1]=velocity;object->scale[3*i+2]=velocity/(2*radius/velocity);}
    return object.release();
  } catch(const std::exception& e){error=e.what();return nullptr;}
}
extern "C" void expert_destroy(void* p){delete static_cast<Context*>(p);}
extern "C" int expert_evaluate(void* handle,const double* starts,const double* ends,const double* goals,int count,double* values,double* gradients) {
  try {
    auto& c=*static_cast<Context*>(handle);
    for(int i=0;i<count;++i){
      c.cost->setGoal(Eigen::Map<const Eigen::Vector3d>(goals+3*i));
      std::vector<double> start(starts+9*i,starts+9*i+9),end(ends+9*i,ends+9*i+9),gradient;
      c.cost->getCostAndGradient(start,end,values[i],gradient);std::copy(gradient.begin(),gradient.end(),gradients+9*i);
    }return 0;
  }catch(const std::exception& e){error=e.what();return -1;}
}
// Diagnostics per candidate: objective calls, acceptedGDupdates, NLopt status,
// nonfinite calls, core wall milliseconds. Fifty GD attempts != fifty MMA calls.
extern "C" int expert_optimize(void* handle,const double* starts,const double* initials,const double* goals,int count,int mode,int budget,double* ends,double* costs,double* diagnostics) {
  if(budget!=50 || (mode!=0 && mode!=1)){error="Only declared50-budget variants supported";return -1;}
  try {
    auto& c=*static_cast<Context*>(handle);
    for(int candidate=0;candidate<count;++candidate){
      auto started=std::chrono::steady_clock::now();
      c.cost->setGoal(Eigen::Map<const Eigen::Vector3d>(goals+3*candidate));
      Objective objective{&c,std::vector<double>(starts+9*candidate,starts+9*candidate+9)};
      std::vector<double> x(initials+9*candidate,initials+9*candidate+9),gradient;
      int accepted=0,status=0;
      if(mode==0){
        double value=objective.evaluate(x,gradient);
        for(int step=0;step<budget;++step){
          std::array<double,9> direction;double norm=0.;
          for(int j=0;j<9;++j){direction[j]=-gradient[j]*c.scale[j]*c.scale[j];norm+=std::pow(gradient[j]*c.scale[j],2);}
          norm=std::sqrt(norm);if(norm<1e-12)continue;
          if(norm>1.)for(auto& item:direction)item/=norm;
          double slope=0;for(int j=0;j<9;++j)slope+=gradient[j]*direction[j];
          double alpha=1.;
          for(int search=0;search<12;++search){
            std::vector<double> trial(9),g;
            for(int j=0;j<9;++j)trial[j]=x[j]+alpha*direction[j];
            double next=objective.evaluate(trial,g);
            if(next<=value+1e-4*alpha*slope){x=trial;gradient=g;value=next;++accepted;break;}
            alpha*=.5;
          }
        }
      }else{
        nlopt::opt optimizer(nlopt::LD_MMA,9);optimizer.set_min_objective(Objective::callback,&objective);optimizer.set_maxeval(budget);
        double value;
        try{status=optimizer.optimize(x,value);}catch(const nlopt::roundoff_limited&){status=NLOPT_ROUNDOFF_LIMITED;}
        accepted=-1;
      }
      if(objective.best_x.empty())throw std::runtime_error("No finite expert candidate");
      std::copy(objective.best_x.begin(),objective.best_x.end(),ends+9*candidate);costs[candidate]=objective.best;
      double* d=diagnostics+5*candidate;d[0]=objective.evaluations;d[1]=accepted;d[2]=status;d[3]=objective.nonfinite;
      d[4]=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-started).count();
    }return 0;
  }catch(const std::exception& e){error=e.what();return -1;}
}
