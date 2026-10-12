// Exact numerical functions from pinned Agile Autonomy; see provenance.json

void TrajectoryExt::fitPolynomialCoeffs(const unsigned int poly_order,
                                         const unsigned int continuity_order) {
  poly_order_ = poly_order;
  continuity_order_ = continuity_order;
  poly_coeff_.clear();

  if (points_.front().time_from_start != 0.0) {
    std::printf(
        "Cannot fit polynomial when first point does not start from zero!\n");
    return;
  }

  double scaling[4] = {1.0, 1.0, 0.5, 1.0 / 6.0};
  for (int i = 0; i <= poly_order_; i++) {
    poly_coeff_.push_back(Eigen::Vector3d::Zero());
  }
  // constraint at beginning
  for (int axis = 0; axis < 3; axis++) {
    for (unsigned int cont_idx = 0; cont_idx <= continuity_order_; cont_idx++) {
      switch (cont_idx) {
        case 0: {
          poly_coeff_.at(cont_idx)[axis] =
              scaling[cont_idx] * points_.front().position[axis];
          break;
        }
        case 1: {
          poly_coeff_.at(cont_idx)[axis] =
              scaling[cont_idx] * points_.front().velocity[axis];
          if (points_.front().velocity.norm() < 0.1 && axis == 0) {
            poly_coeff_.at(cont_idx)[axis] += 0.2;
          }
          break;
        }
        case 2: {
          poly_coeff_.at(cont_idx)[axis] =
              scaling[cont_idx] * points_.front().acceleration[axis];
          break;
        }
        case 3: {
          poly_coeff_.at(cont_idx)[axis] =
              scaling[cont_idx] * points_.front().jerk[axis];
          break;
        }
      }
    }
  }
  if (points_.size() < 3) {
    printf("Trajectory of length [%lu] too short to compute meaningful fit!\n",
           points_.size());
    return;
  }

  Eigen::MatrixXd A = Eigen::MatrixXd::Zero(points_.size() - 1,
                                            poly_order_ - continuity_order_);
  Eigen::MatrixXd b = Eigen::MatrixXd::Zero(points_.size() - 1, 1);

  for (int axis = 0; axis < 3; axis++) {
    for (int i = 1; i < points_.size(); i++) {
      double t = points_.at(i).time_from_start;
      for (unsigned int j = continuity_order_ + 1; j <= poly_order_; j++) {
        A(i - 1, j - (continuity_order_ + 1)) =
            std::pow(t, static_cast<double>(j));
      }
      b(i - 1) = points_.at(i).position[axis];
      for (unsigned int cont_idx = 0; cont_idx <= continuity_order_;
           cont_idx++) {
        b(i - 1) -= poly_coeff_.at(cont_idx)[axis] *
                    std::pow(t, static_cast<double>(cont_idx));
      }
    }
    Eigen::MatrixXd x_coeff =
        A.bdcSvd(Eigen::ComputeThinU | Eigen::ComputeThinV).solve(b);
    for (unsigned int j = (continuity_order_ + 1); j <= poly_order_; j++) {
      poly_coeff_.at(j)[axis] = x_coeff(j - (continuity_order_ + 1));
    }
  }
}

void TrajectoryExt::resamplePointsFromPolyCoeffs() {
  for (auto &traj_point : points_) {
    traj_point.position = evaluatePoly(traj_point.time_from_start, 0);
    traj_point.velocity = evaluatePoly(traj_point.time_from_start, 1);
    traj_point.acceleration = evaluatePoly(traj_point.time_from_start, 2);
    traj_point.jerk = evaluatePoly(traj_point.time_from_start, 3);

    if (frame_id_ != FrameID::World) {
      continue;
    }
    // Attitude
    Eigen::Vector3d thrust =
        traj_point.acceleration + 9.81 * Eigen::Vector3d::UnitZ();
    Eigen::Vector3d I_eZ_I(0.0, 0.0, 1.0);
    Eigen::Quaterniond q_pitch_roll =
        Eigen::Quaterniond::FromTwoVectors(I_eZ_I, thrust);

    Eigen::Vector3d linvel_body = q_pitch_roll.inverse() * traj_point.velocity;
    double heading = 0.0;
    if (yawing_enabled_) {
      heading = std::atan2(traj_point.velocity.y(), traj_point.velocity.x());
    }

    Eigen::Quaterniond q_heading = Eigen::Quaterniond(
        Eigen::AngleAxisd(heading, Eigen::Vector3d::UnitZ()));
    Eigen::Quaterniond q_att = q_pitch_roll * q_heading;
    q_att.normalize();
    traj_point.attitude = q_att;

    // Inputs
    traj_point.collective_thrust = thrust.norm();
    double time_step = 0.1;
    Eigen::Vector3d thrust_1 = thrust - time_step / 2.0 * traj_point.jerk;
    Eigen::Vector3d thrust_2 = thrust + time_step / 2.0 * traj_point.jerk;
    thrust_1.normalize();
    thrust_2.normalize();
    Eigen::Vector3d crossProd = thrust_1.cross(thrust_2);
    Eigen::Vector3d angular_rates_wf = Eigen::Vector3d::Zero();
    if (crossProd.norm() > 0.0) {
      angular_rates_wf =
          std::acos(std::min(1.0, std::max(-1.0, thrust_1.dot(thrust_2)))) /
          time_step * crossProd / (crossProd.norm() + 1.0e-5);
    }
    traj_point.bodyrates = q_att.inverse() * angular_rates_wf;
  }
}

Eigen::Vector3d TrajectoryExt::evaluatePoly(const double dt,
                                             const int derivative) {
  Eigen::Vector3d result = Eigen::Vector3d::Zero();
  switch (derivative) {
    case 0: {
      for (int j = 0; j <= poly_order_; j++) {
        result += poly_coeff_.at(j) * std::pow(dt, j);
      }
      break;
    }
    case 1: {
      for (int j = derivative; j <= poly_order_; j++) {
        result += j * poly_coeff_.at(j) * std::pow(dt, j - derivative);
      }
      break;
    }
    case 2: {
      for (int j = derivative; j <= poly_order_; j++) {
        result +=
            j * (j - 1) * poly_coeff_.at(j) * std::pow(dt, j - derivative);
      }
      break;
    }
    case 3: {
      for (int j = 3; j <= poly_order_; j++) {
        result += (j) * (j - 1) * (j - 2) * poly_coeff_.at(j) *
                  std::pow(dt, j - derivative);
      }
      break;
    }
  }

  return result;
}

bool TrajectoryExt::setConstantArcLengthSpeed(const double &speed,
                                               const int &traj_len,
                                               const double &traj_dt) {
  //  std::printf("setConstantArcLengthSpeed\n");
  // this only works when the trajectory is already fitted with a polynomial
  // (workaround...?)
  if (poly_coeff_.empty()) {
    std::printf("polynomial coefficients unknown!");
    return false;
  }

  // we can reuse the previous first point
  // this assumes that the first point already correctly fulfills the continuity
  // constraints
  std::vector<TrajectoryExtPoint> new_points;
  new_points.push_back(points_.front());
  // iterate through the polynomial, find points that are equally spaced
  double start_time = 0.0;
  double end_time = points_.back().time_from_start;
  int steps = 100;
  double dt = (end_time - start_time) / steps;

  int j = 1;  // this index iterates through the evaluation points

  double t_curr = start_time + dt;
  Eigen::Vector3d pos_prev = evaluatePoly(t_curr, 0);
  Eigen::Vector3d pos_curr;
  double acc_arc_length = 0.0;
  while (t_curr <= end_time) {
    // finely sample the polynomial
    // as soon as point is found that has accumulated arc length of x, add it to
    // the points
    pos_curr = evaluatePoly(t_curr, 0);

    acc_arc_length += (pos_curr - pos_prev).norm();
    if (acc_arc_length >= speed * j * traj_dt) {
      // add this point to the resampled points
      TrajectoryExtPoint temp_point;
      temp_point.time_from_start = j * traj_dt;
      temp_point.position = pos_curr;
      new_points.push_back(temp_point);
      j += 1;
    }
    if (new_points.size() >= points_.size()) {
      break;
    }
    pos_prev = pos_curr;
    t_curr += dt;
  }

  // in case we don't have enough points, extrapolate with constant velocity
  if (j < 2) {
    std::printf("not enough points to extrapolate, won't adapt trajectory!\n");
    return false;
  }

  while (new_points.size() < points_.size()) {
    TrajectoryExtPoint temp_point;
    temp_point.time_from_start = j * traj_dt;
    temp_point.position =
        new_points.at(j - 1).position +
        (new_points.at(j - 1).position - new_points.at(j - 2).position);
    new_points.push_back(temp_point);
    j += 1;
  }
  // refit the polynomial coefficients to these points
  points_.clear();
  for (auto &point : new_points) {
    points_.push_back(point);
  }
  fitPolynomialCoeffs(poly_order_, continuity_order_);
  resamplePointsFromPolyCoeffs();
  return true;
}
