#pragma once
#include <rclcpp/rclcpp.hpp>
#include <rclcpp/create_timer.hpp>
#include <sensor_msgs/msg/image.hpp>
#include <sensor_msgs/image_encodings.hpp>
#include <functional>
#include <chrono>
namespace yopo_topotraj {
template<class T> void parameter(const rclcpp::Node::SharedPtr& node,
                                const std::string& name, T& target, const T& fallback) {
  if (!node->has_parameter(name)) node->declare_parameter<T>(name, fallback);
  node->get_parameter(name, target);
}
}
