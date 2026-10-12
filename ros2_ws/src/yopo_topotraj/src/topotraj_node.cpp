#include <plan_manage/topo_replan_fsm.h>
int main(int argc,char** argv) {
  rclcpp::init(argc,argv);
  auto node=std::make_shared<rclcpp::Node>("topotraj_planner");
  fast_planner::TopoReplanFSM fsm; fsm.init(node);
  // Mapping and planning share mutable maps: serialize callbacks, retain
  // original optimization worker joins, and keep physics in its own process.
  rclcpp::spin(node); rclcpp::shutdown(); return 0;
}
