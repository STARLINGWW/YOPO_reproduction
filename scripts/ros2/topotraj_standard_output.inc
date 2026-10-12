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
