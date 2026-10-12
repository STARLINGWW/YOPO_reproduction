# Container-internal interface, not required in Windows Isaac's bundled types.
# header.frame_id is the world frame; header.stamp is publication simulation time.
std_msgs/Header header
uint64 episode_id
uint64 observation_id
builtin_interfaces/Time observation_stamp
builtin_interfaces/Time start_time
builtin_interfaces/Time valid_until
# Quintic coefficients in ascending powers: x[0:6], y[0:6], z[0:6].
# Position in metres, time in seconds relative to start_time.
float64[18] coefficients
float64 yaw
float64 yaw_rate
float32[] candidate_costs
uint32 selected_candidate
float32 planning_latency_ms
