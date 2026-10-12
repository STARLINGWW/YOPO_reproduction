"""Reproducible ROS2 port; preserve upstream numerical kernels and licenses.

Only run intentionally: regenerates these vendor files, not bspline/poly_traj.
The static forest evaluation does not use dynamic-object history prediction.
"""
from pathlib import Path
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
UP = ROOT / 'external/Fast-Planner/fast_planner'
OUT = ROOT / 'ros2_ws/src/yopo_topotraj'


def convert(s):
    for a, b in {
        '#include <ros/ros.h>': '#include <yopo_topotraj/ros2_support.hpp>',
        '#include <ros/console.h>': '#include <rclcpp/rclcpp.hpp>',
        '#include <geometry_msgs/PoseStamped.h>': '#include <geometry_msgs/msg/pose_stamped.hpp>',
        '#include <nav_msgs/Odometry.h>': '#include <nav_msgs/msg/odometry.hpp>',
        '#include <visualization_msgs/Marker.h>': '#include <visualization_msgs/msg/marker.hpp>',
        'ros::NodeHandle&': 'rclcpp::Node::SharedPtr',
        'ros::NodeHandle node_;': 'rclcpp::Node::SharedPtr node_;',
        'const ros::TimerEvent& /*event*/': '',
        'ros::Time::now()': 'rclcpp::Clock(RCL_STEADY_TIME).now()',
        'ros::Time': 'rclcpp::Time',
        'ros::ok()': 'rclcpp::ok()',
        '.toSec()': '.seconds()',
        'boost::bind': 'std::bind',
        'this, _1, _2': 'this, std::placeholders::_1, std::placeholders::_2',
    }.items():
        s = s.replace(a, b)
    for ns, typ in [('sensor_msgs', 'Image'), ('sensor_msgs', 'PointCloud2'),
                    ('geometry_msgs', 'PoseStamped'), ('nav_msgs', 'Odometry'),
                    ('visualization_msgs', 'Marker')]:
        s = s.replace(f'{ns}::{typ}ConstPtr', f'{ns}::msg::{typ}::ConstSharedPtr')
        s = s.replace(f'{ns}::{typ}', f'{ns}::msg::{typ}')
    s = re.sub(r'(nh|node_)\.param\("([^"]+)", (.*), (.*)\);',
               lambda m: f'yopo_topotraj::parameter({m[1]}, "{m[2].replace("/", ".")}", {m[3]}, {m[4]});', s)
    for level in ('INFO_STREAM', 'ERROR_STREAM', 'WARN_STREAM', 'ERROR', 'WARN', 'INFO'):
        s = s.replace(f'ROS_{level}(', f'RCLCPP_{level}(rclcpp::get_logger("topotraj"), ')
    return s


def map_specific(s, header):
    if header:
        s = s.replace('  SDFMap() {}', '  SDFMap() {}\n  int64_t observed_depth_stamp_ns_=0, fused_depth_stamp_ns_=0, esdf_depth_stamp_ns_=0;\n  double last_fusion_wall_ms_=0., last_esdf_wall_ms_=0.;')
        s = s.replace('int pose_type_;', 'int pose_type_;\n  bool strict_frames_;')
        s = s.replace('ros::Subscriber indep_depth_sub_, indep_odom_sub_, indep_pose_sub_, indep_cloud_sub_;',
                      'rclcpp::Subscription<sensor_msgs::msg::PointCloud2>::SharedPtr indep_cloud_sub_;\n'
                      '  rclcpp::Subscription<nav_msgs::msg::Odometry>::SharedPtr indep_odom_sub_;')
        s = s.replace('ros::Publisher map_pub_, esdf_pub_, map_inf_pub_, update_range_pub_;',
                      'rclcpp::Publisher<sensor_msgs::msg::PointCloud2>::SharedPtr map_pub_, esdf_pub_, map_inf_pub_;\n'
                      '  rclcpp::Publisher<visualization_msgs::msg::Marker>::SharedPtr update_range_pub_;')
        s = s.replace('ros::Publisher unknown_pub_, depth_pub_;',
                      'rclcpp::Publisher<sensor_msgs::msg::PointCloud2>::SharedPtr unknown_pub_, depth_pub_;')
        s = s.replace('rclcpp::Timer occ_timer_, esdf_timer_, vis_timer_;',
                      'rclcpp::TimerBase::SharedPtr occ_timer_, esdf_timer_, vis_timer_;')
        s = s.replace('MappingParameters mp_;', 'MappingParameters mp_{};')
        s = s.replace('MappingData md_;', 'MappingData md_{};')
    else:
        s = s.replace('  node_ = nh;', '  node_ = nh;\n  yopo_topotraj::parameter(node_, "sdf_map.strict_frames", mp_.strict_frames_, false);')
        s = s.replace('  /* get depth image */', '  observed_depth_stamp_ns_=rclcpp::Time(img->header.stamp).nanoseconds();\n  /* get depth image */')
        s = s.replace('  md_.fuse_time_ +=', '  fused_depth_stamp_ns_=observed_depth_stamp_ns_;\n  last_fusion_wall_ms_=(t2-t1).seconds()*1000.;\n  md_.fuse_time_ +=')
        s = s.replace('  md_.esdf_time_ +=', '  esdf_depth_stamp_ns_=fused_depth_stamp_ns_;\n  last_esdf_wall_ms_=(t2-t1).seconds()*1000.;\n  md_.esdf_time_ +=')
        signature = 'const geometry_msgs::msg::PoseStamped::ConstSharedPtr& pose) {'
        s = s.replace(signature, signature + '\n  if (mp_.strict_frames_ && (pose->header.frame_id != mp_.frame_id_ || img->header.stamp != pose->header.stamp || (node_->now()-rclcpp::Time(img->header.stamp)).seconds()>0.2)) return;', 1)
        s = re.sub(r'(message_filters::Subscriber<[^>]+>\()node_, ("[^"]+"), \d+\)',
                   r'\1node_.get(), \2, rmw_qos_profile_sensor_data)', s)
        s = re.sub(r'node_\.subscribe<([^>]+)>\(("[^"]+"), 10, &SDFMap::(\w+), this\)',
                   r'node_->create_subscription<\1>(\2, rclcpp::SensorDataQoS(), std::bind(&SDFMap::\3, this, std::placeholders::_1))', s)
        s = re.sub(r'node_\.createTimer\(ros::Duration\(0.05\), &SDFMap::(\w+), this\)',
                   r'rclcpp::create_timer(node_, node_->get_clock(), std::chrono::milliseconds(50), std::bind(&SDFMap::\1, this))', s)
        s = s.replace('node_.advertise<', 'node_->create_publisher<')
        s = re.sub(r'(\w+_pub_)\.publish\(', r'\1->publish(', s)
        s = s.replace('mk.header.stamp = rclcpp::Clock(RCL_STEADY_TIME).now();', 'mk.header.stamp = node_->now();')
        s = re.sub(r'(img|pose)->header.stamp <<', r'rclcpp::Time(\1->header.stamp).seconds() <<', s)
        # ROS2 image dimensions vary; original fixed VGA allocation can overflow.
        s = s.replace('cv_ptr->image.copyTo(md_.depth_image_);',
                      'cv_ptr->image.copyTo(md_.depth_image_);\n'
                      '  md_.proj_points_.resize(md_.depth_image_.total());')
    return s


def main():
    entries = []
    files = [('plan_env', 'sdf_map'), ('plan_env', 'raycast'),
             ('plan_env', 'edt_environment'), ('path_searching', 'topo_prm'),
             ('bspline_opt', 'bspline_optimizer'), ('path_searching', 'astar'),
             ('path_searching', 'kinodynamic_astar'), ('plan_manage', 'planner_manager')]
    for package, name in files:
        for part, ext in [('include/' + package, 'h'), ('src', 'cpp')]:
            rel = Path(package) / part / (name + '.' + ext)
            original = UP / rel
            s = convert(original.read_text(encoding='utf-8'))
            if name == 'sdf_map':
                s = map_specific(s, ext == 'h')
            if name == 'topo_prm' and ext == 'cpp':
                s = s.replace('eng_ = default_random_engine(rd_());',
                              'int seed = 0; yopo_topotraj::parameter(nh, "topo_prm.seed", seed, 0);\n'
                              '  eng_ = default_random_engine(seed);\n  casters_.clear();')
            if name == 'astar' and ext == 'cpp':
                s = s.replace('int idx = floor((time - time_origin_) * inv_time_resolution_);',
                              'int idx = floor((time - time_origin_) * inv_time_resolution_);\n  return idx;')
            if name == 'planner_manager':
                if ext == 'h':
                    s = s.replace('SDFMap::Ptr sdf_map_;', 'SDFMap::Ptr sdf_map_;\n  rclcpp::Node::SharedPtr node_;')
                else:
                    s = s.replace('void FastPlannerManager::initPlanModules(rclcpp::Node::SharedPtr nh) {',
                                  'void FastPlannerManager::initPlanModules(rclcpp::Node::SharedPtr nh) {\n  node_ = nh;')
                    s = s.replace('(rclcpp::Clock(RCL_STEADY_TIME).now() - local_data_.start_time_)',
                                  '(node_->now() - local_data_.start_time_)')
                    s = s.replace('local_data_.start_time_ = rclcpp::Clock(RCL_STEADY_TIME).now();',
                                  'local_data_.start_time_ = node_->now();')
                    s = s.replace('time_now = rclcpp::Clock(RCL_STEADY_TIME).now();', 'time_now = node_->now();')
            target = OUT / 'vendor' / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(s, encoding='utf-8')
            entries.append({'source': str(original.relative_to(ROOT)),
                            'destination': str(target.relative_to(ROOT)),
                            'upstream_sha256': hashlib.sha256(original.read_bytes()).hexdigest()})
    # Retain the exact polynomial object representation referenced by EDT.
    original = UP / 'plan_env/include/plan_env/obj_predictor.h'
    s = convert(original.read_text(encoding='utf-8'))
    s = s[:s.index('/* ========== subscribe and record object history')] + '\n} // namespace fast_planner\n#endif\n'
    target = OUT / 'vendor/plan_env/include/plan_env/obj_predictor.h'
    target.write_text(s, encoding='utf-8')
    entries.append({'source': str(original.relative_to(ROOT)), 'destination': str(target.relative_to(ROOT)),
                    'upstream_sha256': hashlib.sha256(original.read_bytes()).hexdigest(),
                    'scope': 'PolynomialPrediction only; moving-object history not ported for static forests'})
    original = UP / 'plan_manage/include/plan_manage/plan_container.hpp'
    target = OUT / 'vendor/plan_manage/include/plan_manage/plan_container.hpp'
    target.write_text(convert(original.read_text(encoding='utf-8')), encoding='utf-8')
    entries.append({'source': str(original.relative_to(ROOT)), 'destination': str(target.relative_to(ROOT)),
                    'upstream_sha256': hashlib.sha256(original.read_bytes()).hexdigest()})
    path = OUT / 'port_provenance.json'
    record = json.loads(path.read_text(encoding='utf-8'))
    retained = [e for e in record['files'] if not any(k in e['source'] for k in ['plan_env', 'path_searching', 'bspline_opt', 'plan_manage'])]
    record['files'] = retained + entries
    record['status'] = 'mapping_search_optimizer_port_in_validation_not_full_planner'
    record['ros2_port_changes'] = [
        'Native rclcpp parameters/messages/publishers/subscribers; dotted parameter namespaces',
        'ROS-time update timers; steady-clock computational budgets and timings',
        'Preserve original approximate-depth-pose sync pending uniform adapter integration',
        'Explicit deterministic PRM seed instead of random_device; same generator and distribution',
        'Value-initialize mapping structs and size projected-point buffer to actual sensor dimensions',
        'Static forest scope: preserve polynomial prediction type; dynamic-object subscriber not ported',
    ]
    path.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
