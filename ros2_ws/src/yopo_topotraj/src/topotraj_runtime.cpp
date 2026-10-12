// Unified standard ROS2 boundary in the SAME DDS participant as the planner.
// This avoids a second process competing for the fixed Windows/Docker TCP port.
#include <plan_manage/topo_replan_fsm.h>
#include <sensor_msgs/msg/image.hpp>
#include <std_msgs/msg/u_int64.hpp>
#include <rosgraph_msgs/msg/clock.hpp>
#include <map>
#include <optional>
#include <yaml-cpp/yaml.h>

class Runtime {
  using Image=sensor_msgs::msg::Image;
  using Odom=nav_msgs::msg::Odometry;
  using Pose=geometry_msgs::msg::PoseStamped;
  using Trajectory=trajectory_msgs::msg::MultiDOFJointTrajectory;
  rclcpp::Node::SharedPtr node_;
  std::unique_ptr<fast_planner::TopoReplanFSM> fsm_;
  uint64_t episode_=0; int64_t clock_=-1,last_frame_=-1;
  std::string prefix_,world_="e0/world";
  std::map<int64_t,Image::ConstSharedPtr> images_;
  std::map<int64_t,Odom::ConstSharedPtr> odoms_;
  Pose::ConstSharedPtr goal_;
  bool goal_sent_=false;
  rclcpp::Publisher<Image>::SharedPtr depth_pub_;
  rclcpp::Publisher<Pose>::SharedPtr pose_pub_;
  rclcpp::Publisher<Odom>::SharedPtr odom_pub_;
  rclcpp::Publisher<nav_msgs::msg::Path>::SharedPtr goal_pub_;
  rclcpp::Publisher<Trajectory>::SharedPtr trajectory_pub_;
  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr timing_pub_;
  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr lifecycle_pub_;
  double initialization_wall_ms_=0.;
  std::vector<rclcpp::SubscriptionBase::SharedPtr> subscriptions_;
  static int64_t ns(const builtin_interfaces::msg::Time& t) {return int64_t(t.sec)*1000000000+t.nanosec;}
  void stop() {
    Trajectory message;message.header.frame_id=world_;message.header.stamp=node_->now();
    message.joint_names={"quadrotor"};trajectory_pub_->publish(message);
  }
  void reset(uint64_t episode) {
    const auto initialized_at=std::chrono::steady_clock::now();
    fsm_.reset(); images_.clear();odoms_.clear();goal_.reset();goal_sent_=false;last_frame_=-1;
    episode_=episode;world_="e"+std::to_string(episode_)+"/world";
    node_->set_parameter(rclcpp::Parameter("runtime.world_frame",world_));
    node_->set_parameter(rclcpp::Parameter("sdf_map.frame_id",world_));
    stop();
    fsm_=std::make_unique<fast_planner::TopoReplanFSM>();fsm_->init(node_);
    initialization_wall_ms_=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-initialized_at).count();
    ready();
    RCLCPP_INFO(node_->get_logger(),"Reset full planner and sensor map for episode %lu",episode_);
  }
  void ready() {
    std_msgs::msg::String message;
    message.data="{\"episode\":"+std::to_string(episode_)+",\"phase\":\"episode_ready\",\"initialization_wall_ms\":"+std::to_string(initialization_wall_ms_)+"}";
    lifecycle_pub_->publish(message);
  }
  void drain() {
    if(!fsm_ || clock_<0) return;
    for(auto it=images_.begin();it!=images_.end();) {
      const int64_t t=it->first;
      if(t>clock_) break;
      if(t<=last_frame_ || clock_-t>200000000) {odoms_.erase(t);it=images_.erase(it);continue;}
      auto other=odoms_.find(t);
      if(other==odoms_.end()) {++it;continue;}
      auto image=it->second;auto odom=other->second;
      const auto& oq=odom->pose.pose.orientation;
      Eigen::Quaterniond q(oq.w,oq.x,oq.y,oq.z);
      Eigen::Vector3d p(odom->pose.pose.position.x,odom->pose.pose.position.y,odom->pose.pose.position.z);
      if(!q.coeffs().allFinite() || std::abs(q.norm()-1)>1e-3 || !p.allFinite()) {
        odoms_.erase(other);it=images_.erase(it);continue;
      }
      Eigen::Matrix3d body_optical;body_optical<<0,0,1,-1,0,0,0,-1,0;
      Eigen::Quaterniond optical(q.toRotationMatrix()*body_optical);
      p+=q*Eigen::Vector3d(0,0,.1);
      Pose pose;pose.header=odom->header;pose.pose.position.x=p.x();pose.pose.position.y=p.y();pose.pose.position.z=p.z();
      pose.pose.orientation.w=optical.w();pose.pose.orientation.x=optical.x();
      pose.pose.orientation.y=optical.y();pose.pose.orientation.z=optical.z();
      // Pose and depth retain an identical acquisition timestamp.
      odom_pub_->publish(*odom);pose_pub_->publish(pose);depth_pub_->publish(*image);
      if(goal_ && !goal_sent_) {
        nav_msgs::msg::Path path;path.header=goal_->header;path.poses={*goal_};goal_pub_->publish(path);goal_sent_=true;
      }
      last_frame_=t;odoms_.erase(other);it=images_.erase(it);
    }
    while(images_.size()>32)images_.erase(images_.begin());
    while(odoms_.size()>32)odoms_.erase(odoms_.begin());
  }
public:
  explicit Runtime(rclcpp::Node::SharedPtr node):node_(node) {
    yopo_topotraj::parameter(node_,"runtime.prefix",prefix_,std::string("/yopo/runtime"));
    if(!node_->has_parameter("runtime.world_frame"))node_->declare_parameter("runtime.world_frame",world_);
    if(!node_->has_parameter("sdf_map.frame_id"))node_->declare_parameter("sdf_map.frame_id",world_);
    node_->declare_parameter("sdf_map.strict_frames",true);
    depth_pub_=node_->create_publisher<Image>("/topotraj/internal/depth",10);
    pose_pub_=node_->create_publisher<Pose>("/topotraj/internal/camera_pose",10);
    odom_pub_=node_->create_publisher<Odom>("/topotraj/internal/odom",10);
    goal_pub_=node_->create_publisher<nav_msgs::msg::Path>("/topotraj/internal/goal",10);
    trajectory_pub_=node_->create_publisher<Trajectory>(prefix_+"/trajectory",10);
    timing_pub_=node_->create_publisher<std_msgs::msg::String>(prefix_+"/planning_event",10);
    lifecycle_pub_=node_->create_publisher<std_msgs::msg::String>(prefix_+"/execution_status",10);
    subscriptions_.push_back(node_->create_subscription<std_msgs::msg::String>("/topotraj/internal/planning_event",20,
      [this](std_msgs::msg::String::ConstSharedPtr message){
        if(message->data.size()>8192)return;
        try {auto value=YAML::Load(message->data);if(value["frame_id"].as<std::string>()==world_)timing_pub_->publish(*message);}
        catch(const std::exception& e){RCLCPP_ERROR(node_->get_logger(),"Invalid internal timing message: %s",e.what());}}));
    subscriptions_.push_back(node_->create_subscription<std_msgs::msg::UInt64>(prefix_+"/episode",10,
      [this](std_msgs::msg::UInt64::ConstSharedPtr m){if(!fsm_ || m->data>episode_)reset(m->data);else if(m->data==episode_)ready();}));
    subscriptions_.push_back(node_->create_subscription<rosgraph_msgs::msg::Clock>("/clock",10,
      [this](rosgraph_msgs::msg::Clock::ConstSharedPtr m){auto next=ns(m->clock);if(clock_>=0 && next<clock_)reset(episode_+1);clock_=next;drain();}));
    subscriptions_.push_back(node_->create_subscription<Pose>(prefix_+"/goal",10,
      [this](Pose::ConstSharedPtr m){if(m->header.frame_id==world_){goal_=m;drain();}}));
    subscriptions_.push_back(node_->create_subscription<Image>(prefix_+"/depth",10,
      [this](Image::ConstSharedPtr m){
        if(m->header.frame_id!="e"+std::to_string(episode_)+"/camera_optical" || m->width!=160 || m->height!=90 || m->encoding!="32FC1" || m->step!=640 || m->data.size()!=57600 || m->is_bigendian)return;
        images_[ns(m->header.stamp)]=m;drain();}));
    subscriptions_.push_back(node_->create_subscription<Odom>(prefix_+"/odom",10,
      [this](Odom::ConstSharedPtr m){if(m->header.frame_id!=world_ || m->child_frame_id!="e"+std::to_string(episode_)+"/base_link")return;odoms_[ns(m->header.stamp)]=m;drain();}));
    subscriptions_.push_back(node_->create_subscription<Trajectory>("/topotraj/internal/trajectory",10,
      [this](Trajectory::ConstSharedPtr m){
        if(m->header.frame_id!=world_ || clock_<ns(m->header.stamp) || clock_-ns(m->header.stamp)>200000000)return;
        trajectory_pub_->publish(*m);}));
    subscriptions_.push_back(node_->create_subscription<std_msgs::msg::Empty>("/planning/replan",10,
      [this](std_msgs::msg::Empty::ConstSharedPtr){stop();}));
  }
};
int main(int argc,char**argv) {
  rclcpp::init(argc,argv);
  // All internal topics stay in this DDS participant; only standard boundary
  // topics cross the native Isaac/container connection.
  rclcpp::NodeOptions options;
  options.arguments({"--ros-args","-r","/sdf_map/depth:=/topotraj/internal/depth",
    "-r","/sdf_map/pose:=/topotraj/internal/camera_pose","-r","/sdf_map/odom:=/topotraj/internal/unused_odom",
    "-r","/sdf_map/cloud:=/topotraj/internal/unused_cloud","-r","/odom_world:=/topotraj/internal/odom",
    "-r","/waypoint_generator/waypoints:=/topotraj/internal/goal","-r","/topotraj/trajectory:=/topotraj/internal/trajectory",
    "-r","/topotraj/planning_event:=/topotraj/internal/planning_event"});
  options.parameter_overrides({rclcpp::Parameter("use_sim_time",true)});
  auto node=std::make_shared<rclcpp::Node>("topotraj_runtime",options);
  Runtime runtime(node);rclcpp::spin(node);rclcpp::shutdown();return 0;
}
