// Numerical oracle: upstream source remains unchanged and retains its MIT license.
#include <flightlib/grad_traj_optimization/qp_generator.h>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <stdexcept>

void emit(const Eigen::MatrixXd& matrix) {
  std::cout << '[';
  for (int i = 0; i < matrix.rows(); ++i) {
    if (i) std::cout << ',';
    std::cout << '[';
    for (int j = 0; j < matrix.cols(); ++j) {
      if (j) std::cout << ',';
      std::cout << matrix(i, j);
    }
    std::cout << ']';
  }
  std::cout << ']';
}

int main(int argc, char** argv) {
  const double duration = argc > 1 ? std::stod(argv[1]) : 8.0 / 6.0;
  if (!std::isfinite(duration) || duration <= 0) return 2;
  Eigen::VectorXd time(1);
  time(0) = duration;
  TrajectoryGenerator generator;
  generator.QPGeneration(time);
  std::cout << std::setprecision(17) << "{\"duration\":" << duration << ",\"L\":";
  emit(generator.getL());
  std::cout << ",\"H\":";
  emit(generator.getQ());
  std::cout << ",\"R\":";
  emit(generator.getR());
  std::cout << "}\n";
}
