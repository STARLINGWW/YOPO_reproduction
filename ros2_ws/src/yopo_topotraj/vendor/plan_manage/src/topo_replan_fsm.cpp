/**
* This file is part of Fast-Planner.
*
* Copyright 2019 Boyu Zhou, Aerial Robotics Group, Hong Kong University of Science and Technology, <uav.ust.hk>
* Developed by Boyu Zhou <bzhouai at connect dot ust dot hk>, <uv dot boyuzhou at gmail dot com>
* for more information see <https://github.com/HKUST-Aerial-Robotics/Fast-Planner>.
* If you use this code, please cite the respective publications as
* listed on the above website.
*
* Fast-Planner is free software: you can redistribute it and/or modify
* it under the terms of the GNU Lesser General Public License as published by
* the Free Software Foundation, either version 3 of the License, or
* (at your option) any later version.
*
* Fast-Planner is distributed in the hope that it will be useful,
* but WITHOUT ANY WARRANTY; without even the implied warranty of
* MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
* GNU General Public License for more details.
*
* You should have received a copy of the GNU Lesser General Public License
* along with Fast-Planner. If not, see <http://www.gnu.org/licenses/>.
*/




#include <plan_manage/topo_replan_fsm.h>

namespace fast_planner {

void TopoReplanFSM::init(rclcpp::Node::SharedPtr nh) {
  node_=nh;
  yopo_topotraj::parameter(nh,"runtime.world_frame",world_frame_,std::string("world"));
  current_wp_  = 0;
  exec_state_  = FSM_EXEC_STATE::INIT;
  have_target_ = false;
  collide_     = false;

  /*  fsm param  */
  yopo_topotraj::parameter(nh, "fsm.flight_type", target_type_, -1);
  yopo_topotraj::parameter(nh, "fsm.thresh_replan", replan_time_threshold_, -1.0);
  yopo_topotraj::parameter(nh, "fsm.thresh_no_replan", replan_distance_threshold_, -1.0);
  yopo_topotraj::parameter(nh, "fsm.waypoint_num", waypoint_num_, -1);
  yopo_topotraj::parameter(nh, "fsm.act_map", act_map_, false);
  for (int i = 0; i < waypoint_num_; i++) {
    yopo_topotraj::parameter(nh, "fsm.waypoint" + to_string(i) + "_x", waypoints_[i][0], -1.0);
    yopo_topotraj::parameter(nh, "fsm.waypoint" + to_string(i) + "_y", waypoints_[i][1], -1.0);
    yopo_topotraj::parameter(nh, "fsm.waypoint" + to_string(i) + "_z", waypoints_[i][2], -1.0);
  }

  /* initialize main modules */
  planner_manager_.reset(new FastPlannerManager);
  planner_manager_->initPlanModules(nh);


  /* callback */
  exec_timer_   = rclcpp::create_timer(nh, nh->get_clock(), rclcpp::Duration::from_seconds(0.01), std::bind(&TopoReplanFSM::execFSMCallback, this));
  safety_timer_ = rclcpp::create_timer(nh, nh->get_clock(), rclcpp::Duration::from_seconds(0.05), std::bind(&TopoReplanFSM::checkCollisionCallback, this));

  waypoint_sub_ =
      nh->create_subscription<nav_msgs::msg::Path>("/waypoint_generator/waypoints", 10, std::bind(&TopoReplanFSM::waypointCallback, this, std::placeholders::_1));
  odom_sub_ = nh->create_subscription<nav_msgs::msg::Odometry>("/odom_world", rclcpp::SensorDataQoS(), std::bind(&TopoReplanFSM::odometryCallback, this, std::placeholders::_1));

  replan_pub_  = nh->create_publisher<std_msgs::msg::Empty>("/planning/replan", 20);
  new_pub_     = nh->create_publisher<std_msgs::msg::Empty>("/planning/new", 20);
  trajectory_pub_ = nh->create_publisher<trajectory_msgs::msg::MultiDOFJointTrajectory>("/topotraj/trajectory", 10);
  timing_pub_=nh->create_publisher<std_msgs::msg::String>("/topotraj/planning_event",10);
}

void TopoReplanFSM::waypointCallback(const nav_msgs::msg::Path::ConstSharedPtr& msg) {
  if (msg->poses.empty() || msg->header.frame_id != world_frame_) return;
  if (have_target_) return; // repeated reliable goal delivery is idempotent
  if (msg->poses[0].pose.position.z < -0.1) return;
  cout << "Triggered!" << endl;

  vector<Eigen::Vector3d> global_wp;
  if (target_type_ == TARGET_TYPE::REFENCE_PATH) {
    for (int i = 0; i < waypoint_num_; ++i) {
      Eigen::Vector3d pt;
      pt(0) = waypoints_[i][0];
      pt(1) = waypoints_[i][1];
      pt(2) = waypoints_[i][2];
      global_wp.push_back(pt);
    }
  } else {

    if (target_type_ == TARGET_TYPE::MANUAL_TARGET) {
      target_point_(0) = msg->poses[0].pose.position.x;
      target_point_(1) = msg->poses[0].pose.position.y;
      target_point_(2) = msg->poses[0].pose.position.z;
      std::cout << "manual: " << target_point_.transpose() << std::endl;

    } else if (target_type_ == TARGET_TYPE::PRESET_TARGET) {
      target_point_(0) = waypoints_[current_wp_][0];
      target_point_(1) = waypoints_[current_wp_][1];
      target_point_(2) = waypoints_[current_wp_][2];

      current_wp_ = (current_wp_ + 1) % waypoint_num_;
      std::cout << "preset: " << target_point_.transpose() << std::endl;
    }

    global_wp.push_back(target_point_);
  }

  planner_manager_->setGlobalWaypoints(global_wp);
  end_vel_.setZero();
  have_target_ = true;
  trigger_     = true;

  if (exec_state_ == WAIT_TARGET) {
    changeFSMExecState(GEN_NEW_TRAJ, "TRIG");
  }
}

void TopoReplanFSM::odometryCallback(const nav_msgs::msg::Odometry::ConstSharedPtr& msg) {
  if (msg->header.frame_id != world_frame_) return;
  double age=(node_->now()-rclcpp::Time(msg->header.stamp)).seconds();
  if (age<0 || age>0.2) return;
  odom_pos_(0) = msg->pose.pose.position.x;
  odom_pos_(1) = msg->pose.pose.position.y;
  odom_pos_(2) = msg->pose.pose.position.z;

  odom_vel_(0) = msg->twist.twist.linear.x;
  odom_vel_(1) = msg->twist.twist.linear.y;
  odom_vel_(2) = msg->twist.twist.linear.z;

  odom_orient_.w() = msg->pose.pose.orientation.w;
  odom_orient_.x() = msg->pose.pose.orientation.x;
  odom_orient_.y() = msg->pose.pose.orientation.y;
  odom_orient_.z() = msg->pose.pose.orientation.z;

  odom_vel_ = odom_orient_.toRotationMatrix() * odom_vel_; // standard ROS body twist
  latest_odom_stamp_ns_=rclcpp::Time(msg->header.stamp).nanoseconds();
  have_odom_ = true;
}

void TopoReplanFSM::changeFSMExecState(FSM_EXEC_STATE new_state, string pos_call) {
  string state_str[6] = { "INIT",
                          "WAIT_TARGET",
                          "GEN_NEW_TRAJ",
                          "REPLAN_TRAJ",
                          "EXEC_TRAJ",
                          "REPLAN_"
                          "NEW" };
  int    pre_s        = int(exec_state_);
  exec_state_         = new_state;
  cout << "[" + pos_call + "]: from " + state_str[pre_s] + " to " + state_str[int(new_state)] << endl;
}

void TopoReplanFSM::printFSMExecState() {
  string state_str[6] = { "INIT",
                          "WAIT_TARGET",
                          "GEN_NEW_TRAJ",
                          "REPLAN_TRAJ",
                          "EXEC_TRAJ",
                          "REPLAN_"
                          "NEW" };
  cout << "state: " + state_str[int(exec_state_)] << endl;
}

void TopoReplanFSM::execFSMCallback() {
  static int fsm_num = 0;
  fsm_num++;
  if (fsm_num == 100) {
    printFSMExecState();
    if (!have_odom_) cout << "no odom." << endl;
    if (!trigger_) cout << "no trigger_." << endl;
    fsm_num = 0;
  }

  switch (exec_state_) {
    case INIT: {
      if (!have_odom_) {
        return;
      }
      if (!trigger_) {
        return;
      }
      changeFSMExecState(WAIT_TARGET, "FSM");

      break;
    }

    case WAIT_TARGET: {
      if (!have_target_)
        return;
      else {
        changeFSMExecState(GEN_NEW_TRAJ, "FSM");
      }

      break;
    }

    case GEN_NEW_TRAJ: {
      start_pt_  = odom_pos_;
      start_vel_ = odom_vel_;
      start_acc_.setZero();

      Eigen::Vector3d rot_x = odom_orient_.toRotationMatrix().block(0, 0, 3, 1);
      start_yaw_(0)         = atan2(rot_x(1), rot_x(0));
      start_yaw_(1) = start_yaw_(2) = 0.0;

      new_pub_->publish(std_msgs::msg::Empty());
      /* topo path finding and optimization */
      bool success = callTopologicalTraj(1);
      if (success) {
        changeFSMExecState(EXEC_TRAJ, "FSM");
      } else {
        changeFSMExecState(GEN_NEW_TRAJ, "FSM");
      }
      break;
    }

    case EXEC_TRAJ: {
      /* determine if need to replan */

      GlobalTrajData* global_data = &planner_manager_->global_data_;
      rclcpp::Time       time_now    = node_->now();
      double          t_cur       = (time_now - global_data->global_start_time_).seconds();

      if (t_cur > global_data->global_duration_ - 1e-2) {
        have_target_ = false;
        changeFSMExecState(WAIT_TARGET, "FSM");
        return;

      } else {
        LocalTrajData*  info      = &planner_manager_->local_data_;
        Eigen::Vector3d start_pos = info->start_pos_;
        t_cur                     = (time_now - info->start_time_).seconds();

        if (t_cur > replan_time_threshold_) {

          if (!global_data->localTrajReachTarget()) {
            changeFSMExecState(REPLAN_TRAJ, "FSM");

          } else {
            Eigen::Vector3d cur_pos = info->position_traj_.evaluateDeBoorT(t_cur);
            Eigen::Vector3d end_pos = info->position_traj_.evaluateDeBoorT(info->duration_);
            if ((cur_pos - end_pos).norm() > replan_distance_threshold_)
              changeFSMExecState(REPLAN_TRAJ, "FSM");
          }
        }
      }
      break;
    }

    case REPLAN_TRAJ: {
      LocalTrajData* info     = &planner_manager_->local_data_;
      rclcpp::Time      time_now = node_->now();
      double         t_cur    = (time_now - info->start_time_).seconds();

      start_pt_  = info->position_traj_.evaluateDeBoorT(t_cur);
      start_vel_ = info->velocity_traj_.evaluateDeBoorT(t_cur);
      start_acc_ = info->acceleration_traj_.evaluateDeBoorT(t_cur);

      start_yaw_(0) = info->yaw_traj_.evaluateDeBoorT(t_cur)[0];
      start_yaw_(1) = info->yawdot_traj_.evaluateDeBoorT(t_cur)[0];
      start_yaw_(2) = info->yawdotdot_traj_.evaluateDeBoorT(t_cur)[0];

      bool success = callTopologicalTraj(2);
      if (success) {
        changeFSMExecState(EXEC_TRAJ, "FSM");
      } else {
        RCLCPP_WARN(rclcpp::get_logger("topotraj"), "Replan fail, retrying...");
      }

      break;
    }
    case REPLAN_NEW: {
      LocalTrajData* info     = &planner_manager_->local_data_;
      rclcpp::Time      time_now = node_->now();
      double         t_cur    = (time_now - info->start_time_).seconds();

      start_pt_  = info->position_traj_.evaluateDeBoorT(t_cur);
      start_vel_ = info->velocity_traj_.evaluateDeBoorT(t_cur);
      start_acc_ = info->acceleration_traj_.evaluateDeBoorT(t_cur);

      /* inform server */
      new_pub_->publish(std_msgs::msg::Empty());

      // bool success = callSearchAndOptimization();
      bool success = callTopologicalTraj(1);
      if (success) {
        changeFSMExecState(EXEC_TRAJ, "FSM");
      } else {
        changeFSMExecState(GEN_NEW_TRAJ, "FSM");
      }

      break;
    }
  }
}

void TopoReplanFSM::checkCollisionCallback() {
  LocalTrajData* info = &planner_manager_->local_data_;

  /* ---------- check goal safety ---------- */
  // if (have_target_)
  if (false) {
    auto edt_env = planner_manager_->edt_environment_;

    double dist = planner_manager_->pp_.dynamic_ ?
        edt_env->evaluateCoarseEDT(target_point_, /* time to program start */ info->duration_) :
        edt_env->evaluateCoarseEDT(target_point_, -1.0);

    if (dist <= 0.3) {
      /* try to find a max distance goal around */
      bool         new_goal = false;
      const double dr = 0.5, dtheta = 30, dz = 0.3;

      double          new_x, new_y, new_z, max_dist = -1.0;
      Eigen::Vector3d goal;

      for (double r = dr; r <= 5 * dr + 1e-3; r += dr) {
        for (double theta = -90; theta <= 270; theta += dtheta) {
          for (double nz = 1 * dz; nz >= -1 * dz; nz -= dz) {

            new_x = target_point_(0) + r * cos(theta / 57.3);
            new_y = target_point_(1) + r * sin(theta / 57.3);
            new_z = target_point_(2) + nz;
            Eigen::Vector3d new_pt(new_x, new_y, new_z);

            dist = planner_manager_->pp_.dynamic_ ?
                edt_env->evaluateCoarseEDT(new_pt, /* time to program start */ info->duration_) :
                edt_env->evaluateCoarseEDT(new_pt, -1.0);

            if (dist > max_dist) {
              /* reset target_point_ */
              goal(0)  = new_x;
              goal(1)  = new_y;
              goal(2)  = new_z;
              max_dist = dist;
            }
          }
        }
      }

      if (max_dist > 0.3) {
        cout << "change goal, replan." << endl;
        target_point_ = goal;
        have_target_  = true;
        end_vel_.setZero();

        if (exec_state_ == EXEC_TRAJ) {
          changeFSMExecState(REPLAN_NEW, "SAFETY");
        }

      } else {
        // have_target_ = false;
        // cout << "Goal near collision, stop." << endl;
        // changeFSMExecState(WAIT_TARGET, "SAFETY");
        cout << "goal near collision, keep retry" << endl;
        changeFSMExecState(REPLAN_TRAJ, "FSM");
      }
    }
  }

  /* ---------- check trajectory ---------- */
  if (exec_state_ == EXEC_TRAJ || exec_state_ == REPLAN_TRAJ) {
    double dist;
    bool   safe = planner_manager_->checkTrajCollision(dist);
    if (!safe) {
      if (dist > 0.5) {
        RCLCPP_WARN(rclcpp::get_logger("topotraj"), "current traj %lf m to collision", dist);
        collide_ = true;
        changeFSMExecState(REPLAN_TRAJ, "SAFETY");
      } else {
        RCLCPP_ERROR(rclcpp::get_logger("topotraj"), "current traj %lf m to collision, emergency stop!", dist);
        replan_pub_->publish(std_msgs::msg::Empty());
        have_target_ = false;
        changeFSMExecState(WAIT_TARGET, "SAFETY");
      }
    } else {
      collide_ = false;
    }
  }
}

bool TopoReplanFSM::callSearchAndOptimization() { return false; }

bool TopoReplanFSM::callTopologicalTraj(int step) {
  const auto planning_wall_start=std::chrono::steady_clock::now();
  const auto map=planner_manager_->edt_environment_->sdf_map_;
  const int64_t used_odom_stamp=latest_odom_stamp_ns_;
  const int64_t used_map_stamp=map->esdf_depth_stamp_ns_;
  const int64_t observation_stamp=(used_odom_stamp>0 && used_map_stamp>0)?std::min(used_odom_stamp,used_map_stamp):std::max(used_odom_stamp,used_map_stamp);
  const double fusion_ms=map->last_fusion_wall_ms_,esdf_ms=map->last_esdf_wall_ms_;
  auto publish_timing=[&](const char* status) {
    std::ostringstream json;json<<std::setprecision(17);
    json<<"{\"status\":\""<<status<<"\",\"frame_id\":\""<<world_frame_<<"\","
        <<"\"trajectory_stamp_ns\":"<<planner_manager_->local_data_.start_time_.nanoseconds()
        <<",\"observation_stamp_ns\":"<<observation_stamp<<",\"odom_stamp_ns\":"<<used_odom_stamp
        <<",\"map_esdf_stamp_ns\":"<<used_map_stamp<<",\"map_fusion_wall_ms\":"<<fusion_ms
        <<",\"map_esdf_wall_ms\":"<<esdf_ms
        <<",\"planner_wall_ms\":"<<std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-planning_wall_start).count()
        <<",\"queue_wall_ms\":null,\"debug\":{\"baseline\":\"TopoTraj\"}}";
    std_msgs::msg::String message;message.data=json.str();timing_pub_->publish(message);
  };

  bool plan_success;

  if (step == 1) {
    plan_success = planner_manager_->planGlobalTraj(start_pt_);
  } else {
    plan_success = planner_manager_->topoReplan(collide_);
  }

  if (plan_success) {

    planner_manager_->planYaw(start_yaw_);

    LocalTrajData* locdat = &planner_manager_->local_data_;

    // Standard-message boundary; samples retain original spline p/v/a and yaw.
    const double age=(node_->now()-locdat->start_time_).seconds();
    if(age<0 || age>0.2) {
      RCLCPP_WARN(node_->get_logger(), "Discard late trajectory age=%f",age);
      publish_timing("stale_result");
      return false;
    }
    trajectory_msgs::msg::MultiDOFJointTrajectory message;
    message.header.stamp=locdat->start_time_; message.header.frame_id=world_frame_;
    message.joint_names={"quadrotor"};
    int count=std::max(1,int(std::ceil(locdat->duration_/0.02)));
    for(int i=0;i<=count;++i) {
      double t=locdat->duration_*i/count;
      Eigen::Vector3d p=locdat->position_traj_.evaluateDeBoorT(t);
      Eigen::Vector3d v=locdat->velocity_traj_.evaluateDeBoorT(t);
      Eigen::Vector3d a=locdat->acceleration_traj_.evaluateDeBoorT(t);
      double yaw=locdat->yaw_traj_.evaluateDeBoorT(t)[0];
      double rate=locdat->yawdot_traj_.evaluateDeBoorT(t)[0];
      if(!p.allFinite() || !v.allFinite() || !a.allFinite() || !std::isfinite(yaw)) {publish_timing("nonfinite_result");return false;}
      trajectory_msgs::msg::MultiDOFJointTrajectoryPoint point;
      geometry_msgs::msg::Transform transform;
      transform.translation.x=p.x();transform.translation.y=p.y();transform.translation.z=p.z();
      transform.rotation.z=std::sin(yaw/2);transform.rotation.w=std::cos(yaw/2);
      geometry_msgs::msg::Twist velocity,acceleration;
      velocity.linear.x=v.x();velocity.linear.y=v.y();velocity.linear.z=v.z();velocity.angular.z=rate;
      acceleration.linear.x=a.x();acceleration.linear.y=a.y();acceleration.linear.z=a.z();
      point.transforms={transform};point.velocities={velocity};point.accelerations={acceleration};
      point.time_from_start=rclcpp::Duration::from_seconds(t);
      message.points.push_back(point);
    }
    trajectory_pub_->publish(message);
    publish_timing("published");

    return true;
  } else {
    publish_timing("planner_no_path");
    return false;
  }
}
// TopoReplanFSM::
}  // namespace fast_planner
