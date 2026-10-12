std::vector<double> SignedDistanceField::GetGradient(const int64_t x_index, const int64_t y_index, const int64_t z_index, const bool enable_edge_gradients) const
    {
        // Make sure the index is inside bounds
        if ((x_index >= 0) && (y_index >= 0) && (z_index >= 0) && (x_index < GetNumXCells()) && (y_index < GetNumYCells()) && (z_index < GetNumZCells()))
        {
            // Make sure the index we're trying to query is one cell in from the edge
            if ((x_index > 0) && (y_index > 0) && (z_index > 0) && (x_index < (GetNumXCells() - 1)) && (y_index < (GetNumYCells() - 1)) && (z_index < (GetNumZCells() - 1)))
            {
                double inv_twice_resolution = 1.0 / (2.0 * GetResolution());
                double gx = (Get(x_index + 1, y_index, z_index) - Get(x_index - 1, y_index, z_index)) * inv_twice_resolution;
                double gy = (Get(x_index, y_index + 1, z_index) - Get(x_index, y_index - 1, z_index)) * inv_twice_resolution;
                double gz = (Get(x_index, y_index, z_index + 1) - Get(x_index, y_index, z_index - 1)) * inv_twice_resolution;
                return std::vector<double>{gx, gy, gz};
            }
            // If we're on the edge, handle it specially
            else if (enable_edge_gradients)
            {
                // Get the "best" indices we can use
                int64_t low_x_index = std::max((int64_t)0, x_index - 1);
                int64_t high_x_index = std::min(GetNumXCells() - 1, x_index + 1);
                int64_t low_y_index = std::max((int64_t)0, y_index - 1);
                int64_t high_y_index = std::min(GetNumYCells() - 1, y_index + 1);
                int64_t low_z_index = std::max((int64_t)0, z_index - 1);
                int64_t high_z_index = std::min(GetNumZCells() - 1, z_index + 1);
                // Compute the axis increments
                double x_increment = (high_x_index - low_x_index) * GetResolution();
                double y_increment = (high_y_index - low_y_index) * GetResolution();
                double z_increment = (high_z_index - low_z_index) * GetResolution();
                // Compute the gradients for each axis - by default these are zero
                double gx = 0.0;
                double gy = 0.0;
                double gz = 0.0;
                // Only if the increments are non-zero do we compute the gradient of an axis
                if (x_increment > 0.0)
                {
                    double inv_x_increment = 1.0 / x_increment;
                    double high_x_value = Get(high_x_index, y_index, z_index);
                    double low_x_value = Get(low_x_index, y_index, z_index);
                    // Compute the gradient
                    gx = (high_x_value - low_x_value) * inv_x_increment;
                }
                if (y_increment > 0.0)
                {
                    double inv_y_increment = 1.0 / y_increment;
                    double high_y_value = Get(x_index, high_y_index, z_index);
                    double low_y_value = Get(x_index, low_y_index, z_index);
                    // Compute the gradient
                    gy = (high_y_value - low_y_value) * inv_y_increment;
                }
                if (z_increment > 0.0)
                {
                    double inv_z_increment = 1.0 / z_increment;
                    double high_z_value = Get(x_index, y_index, high_z_index);
                    double low_z_value = Get(x_index, y_index, low_z_index);
                    // Compute the gradient
                    gz = (high_z_value - low_z_value) * inv_z_increment;
                }
                // Assemble and return the computed gradient
                return std::vector<double>{gx, gy, gz};
            }
            // Edge gradients disabled, return no gradient
            else
            {
                return std::vector<double>();
            }
        }
        // If we're out of bounds, return no gradient
        else
        {
            return std::vector<double>();
        }
    }
