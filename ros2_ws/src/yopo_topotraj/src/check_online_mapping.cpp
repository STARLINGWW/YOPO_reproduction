#include <plan_env/sdf_map.h>
#include <fstream>
#include <thread>
#include <cstring>
#include <stdexcept>

int main(int argc,char** argv) {
  rclcpp::init(argc,argv);
  auto node=std::make_shared<rclcpp::Node>("topotraj_online_mapping");
  auto map=std::make_shared<SDFMap>(); map->initMap(node);
  auto sensor=std::make_shared<rclcpp::Node>("topotraj_mapping_fixture");
  auto images=sensor->create_publisher<sensor_msgs::msg::Image>("/sdf_map/depth",rclcpp::SensorDataQoS());
  auto poses=sensor->create_publisher<geometry_msgs::msg::PoseStamped>("/sdf_map/pose",rclcpp::SensorDataQoS());
  rclcpp::executors::SingleThreadedExecutor executor;
  executor.add_node(node); executor.add_node(sensor);
  auto start=std::chrono::steady_clock::now();
  while((images->get_subscription_count()==0 || poses->get_subscription_count()==0) &&
        std::chrono::steady_clock::now()-start<std::chrono::seconds(5)) {
    executor.spin_some();std::this_thread::sleep_for(std::chrono::milliseconds(10));
  }
  if(images->get_subscription_count()==0 || poses->get_subscription_count()==0)
    throw std::runtime_error("Mapping sensor subscriptions undiscovered");
  sensor_msgs::msg::Image image; image.header.frame_id="camera_optical";
  image.width=160; image.height=90; image.encoding="32FC1"; image.step=640;
  image.data.resize(160*90*4);
  const float depth=3.0f;
  for(size_t i=0;i<160*90;++i) std::memcpy(image.data.data()+i*4,&depth,4);
  geometry_msgs::msg::PoseStamped pose; pose.header.frame_id="world";
  pose.pose.position.x=-3; pose.pose.position.z=2;
  Eigen::Matrix3d rotation; rotation<<0,0,1,-1,0,0,0,-1,0;
  Eigen::Quaterniond q(rotation);
  pose.pose.orientation.w=q.w(); pose.pose.orientation.x=q.x();
  pose.pose.orientation.y=q.y(); pose.pose.orientation.z=q.z();
  // This diagnostic publishes only sensor data, never map truth.
  for(int i=0;i<20;++i) {
    image.header.stamp=sensor->now(); pose.header.stamp=image.header.stamp;
    images->publish(image); poses->publish(pose);
    auto end=std::chrono::steady_clock::now()+std::chrono::milliseconds(110);
    while(std::chrono::steady_clock::now()<end) {executor.spin_some(); std::this_thread::sleep_for(std::chrono::milliseconds(2));}
  }
  int occupied=map->getInflateOccupancy(Eigen::Vector3d(0.05,0.05,2.05));
  double near=map->getDistance(Eigen::Vector3d(-1.05,0.05,2.05));
  Eigen::Vector3i free_index; map->posToIndex(Eigen::Vector3d(-1.05,0.05,2.05),free_index);
  bool free=map->isKnownFree(free_index);
  std::ofstream out("/workspace/artifacts/environment/topotraj_online_mapping.json");
  bool ok=occupied==1 && free && near>0.8 && near<1.3;
  out<<"{\"status\":\""<<(ok?"passed":"failed")<<"\",\"scope\":\"ROS2 Image/PoseStamped through original depth raycasting, occupancy and ESDF; synthetic planar sensor fixture\","
     <<"\"frames\":20,\"wall_occupied\":"<<occupied<<",\"ray_known_free\":"<<(free?"true":"false")<<",\"wall_distance_m\":"<<near<<"}\n";
  out.close(); rclcpp::shutdown();
  if(!ok) throw std::runtime_error("Online sensor mapping wrong occupancy/distance");
  return 0;
}
