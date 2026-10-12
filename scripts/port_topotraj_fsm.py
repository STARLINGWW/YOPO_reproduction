"""Port pinned TopoTraj FSM to native ROS2 and standard trajectory output."""
from pathlib import Path
import hashlib
import json
import re
from port_topotraj_components import ROOT, UP, OUT, convert

files=[]
for ext, part in [('h','include/plan_manage'),('cpp','src')]:
    source=UP/'plan_manage'/part/f'topo_replan_fsm.{ext}'
    target=OUT/'vendor/plan_manage'/part/f'topo_replan_fsm.{ext}'
    s=convert(source.read_text(encoding='utf-8'))
    for a,b in {
        '#include <nav_msgs/Path.h>':'#include <nav_msgs/msg/path.hpp>',
        '#include <std_msgs/Empty.h>':'#include <std_msgs/msg/empty.hpp>',
        '#include <plan_manage/Bspline.h>':'#include <trajectory_msgs/msg/multi_dof_joint_trajectory.hpp>',
        '#include <traj_utils/planning_visualization.h>':'',
        'nav_msgs::PathConstPtr':'nav_msgs::msg::Path::ConstSharedPtr',
        'std_msgs::Empty':'std_msgs::msg::Empty',
        'const rclcpp::TimerEvent& e':'',
        'rclcpp::Clock(RCL_STEADY_TIME).now()':'node_->now()',
    }.items():s=s.replace(a,b)
    if ext=='h':
        s=s.replace('#include <std_msgs/msg/empty.hpp>', '#include <std_msgs/msg/empty.hpp>\n#include <std_msgs/msg/string.hpp>\n#include <sstream>\n#include <iomanip>')
        s=s.replace('PlanningVisualization::Ptr visualization_;','')
        s=s.replace('rclcpp::Timer exec_timer_, safety_timer_, vis_timer_, frontier_timer_;',
                    'rclcpp::TimerBase::SharedPtr exec_timer_, safety_timer_;')
        s=s.replace('ros::Subscriber waypoint_sub_, odom_sub_;',
                    'rclcpp::Subscription<nav_msgs::msg::Path>::SharedPtr waypoint_sub_;\n'
                    '  rclcpp::Subscription<nav_msgs::msg::Odometry>::SharedPtr odom_sub_;')
        s=s.replace('ros::Publisher replan_pub_, new_pub_, bspline_pub_;',
                    'rclcpp::Publisher<std_msgs::msg::Empty>::SharedPtr replan_pub_, new_pub_;\n'
                    '  rclcpp::Publisher<trajectory_msgs::msg::MultiDOFJointTrajectory>::SharedPtr trajectory_pub_;\n'
                    '  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr timing_pub_;\n'
                    '  int64_t latest_odom_stamp_ns_=0;\n  std::string world_frame_;')
        s=s.replace('bool trigger_, have_target_, have_odom_, collide_;',
                    'bool trigger_=false, have_target_=false, have_odom_=false, collide_=false;')
    else:
        s=s.replace('void TopoReplanFSM::init(rclcpp::Node::SharedPtr nh) {',
                    'void TopoReplanFSM::init(rclcpp::Node::SharedPtr nh) {\n  node_=nh;\n'
                    '  yopo_topotraj::parameter(nh,"runtime.world_frame",world_frame_,std::string("world"));')
        s=s.replace('  visualization_.reset(new PlanningVisualization(nh));','')
        s=re.sub(r'\s*visualization_->\w+\(.*?\);','',s,flags=re.S)
        s=re.sub(r'nh\.param\("fsm/waypoint" \+ to_string\(i\) \+ "_([xyz])", (.*?), -1.0\);',
                 r'yopo_topotraj::parameter(nh, "fsm.waypoint" + to_string(i) + "_\1", \2, -1.0);',s)
        s=re.sub(r'nh.createTimer\(ros::Duration\((.*?)\), &TopoReplanFSM::(\w+), this\)',
                 r'rclcpp::create_timer(nh, nh->get_clock(), rclcpp::Duration::from_seconds(\1), std::bind(&TopoReplanFSM::\2, this))',s)
        s=s.replace('nh.subscribe("/waypoint_generator/waypoints", 1, &TopoReplanFSM::waypointCallback, this)',
                    'nh->create_subscription<nav_msgs::msg::Path>("/waypoint_generator/waypoints", 10, std::bind(&TopoReplanFSM::waypointCallback, this, std::placeholders::_1))')
        s=s.replace('nh.subscribe("/odom_world", 1, &TopoReplanFSM::odometryCallback, this)',
                    'nh->create_subscription<nav_msgs::msg::Odometry>("/odom_world", rclcpp::SensorDataQoS(), std::bind(&TopoReplanFSM::odometryCallback, this, std::placeholders::_1))')
        s=s.replace('nh.advertise<','nh->create_publisher<')
        s=s.replace('bspline_pub_ = nh->create_publisher<plan_manage::Bspline>("/planning/bspline", 20);',
                    'trajectory_pub_ = nh->create_publisher<trajectory_msgs::msg::MultiDOFJointTrajectory>("/topotraj/trajectory", 10);\n'
                    '  timing_pub_=nh->create_publisher<std_msgs::msg::String>("/topotraj/planning_event",10);')
        s=re.sub(r'(\w+_pub_)\.publish\(',r'\1->publish(',s)
        s=s.replace('  if (msg->poses[0].pose.position.z < -0.1) return;',
                    '  if (msg->poses.empty() || msg->header.frame_id != world_frame_) return;\n'
                    '  if (have_target_) return; // repeated reliable goal delivery is idempotent\n'
                    '  if (msg->poses[0].pose.position.z < -0.1) return;')
        s=s.replace('target_point_(2) = 1.0;', 'target_point_(2) = msg->poses[0].pose.position.z;')
        s=s.replace('void TopoReplanFSM::odometryCallback(const nav_msgs::msg::Odometry::ConstSharedPtr& msg) {',
                    'void TopoReplanFSM::odometryCallback(const nav_msgs::msg::Odometry::ConstSharedPtr& msg) {\n'
                    '  if (msg->header.frame_id != world_frame_) return;\n'
                    '  double age=(node_->now()-rclcpp::Time(msg->header.stamp)).seconds();\n'
                    '  if (age<0 || age>0.2) return;')
        s=s.replace('  have_odom_ = true;',
                    '  odom_vel_ = odom_orient_.toRotationMatrix() * odom_vel_; // standard ROS body twist\n'
                    '  latest_odom_stamp_ns_=rclcpp::Time(msg->header.stamp).nanoseconds();\n  have_odom_ = true;')
        s=s.replace('bool TopoReplanFSM::callSearchAndOptimization() {}',
                    'bool TopoReplanFSM::callSearchAndOptimization() { return false; }')
        signature='bool TopoReplanFSM::callTopologicalTraj(int step) {'
        timing=(ROOT/'scripts/ros2/topotraj_timing_capture.inc').read_text(encoding='utf-8')
        s=s.replace(signature,signature+'\n'+timing)
        first=s.index('    /* publish newest trajectory to server */')
        last=s.index('    return true;',first)
        replacement=(ROOT/'scripts/ros2/topotraj_standard_output.inc').read_text(encoding='utf-8')
        s=s[:first]+replacement+'\n'+s[last:]
        tail='  } else {\n    return false;\n  }\n}\n// TopoReplanFSM::'
        assert tail in s
        s=s.replace(tail,'  } else {\n    publish_timing("planner_no_path");\n    return false;\n  }\n}\n// TopoReplanFSM::')
    target.write_text(s,encoding='utf-8')
    files.append({'source':str(source.relative_to(ROOT)),'destination':str(target.relative_to(ROOT)),
                  'upstream_sha256':hashlib.sha256(source.read_bytes()).hexdigest()})
p=OUT/'port_provenance.json'; record=json.loads(p.read_text(encoding='utf-8'))
record['files']=[f for f in record['files'] if 'topo_replan_fsm' not in f['source']]+files
record['fsm_changes']=['Preserve original state transitions, replanning and collision logic',
    'ROS2 native timers/subscriptions; standard sampled trajectory replaces ROS1 Bspline/traj_server',
    'Omit RViz-only publications; record trajectory externally',
    'Manual target uses supplied z instead of upstream hard-coded 1m',
    'Standard body-frame odometry twist rotated to world; reject stale/wrong-frame odometry',
    'Initialize flags; ignore empty or repeated active goals; reject trajectory older than0.2s',
    'Unified topotraj_runtime rebuilds full FSM/map on episode and clock rewind; see runtime probe evidence',
    'Raw topotraj_node is a component fixture; use unified topotraj_runtime for episode-aware experiments']
p.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
