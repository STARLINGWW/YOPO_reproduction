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
