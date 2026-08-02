import numpy as np
from abc import ABC, abstractmethod

PARAMETER_DEFAULTS = {
    'ph': {'neutral': 7.0, 'min': 0.0, 'max': 14.0},
    'ec': {'neutral': 2.0, 'min': 0.0, 'max': 20.0},
    'n': {'neutral': 150.0, 'min': 0.0, 'max': 500.0},
    'p': {'neutral': 50.0, 'min': 0.0, 'max': 200.0},
    'k': {'neutral': 200.0, 'min': 0.0, 'max': 600.0},
    'organic_carbon': {'neutral': 2.0, 'min': 0.0, 'max': 10.0},
    's': {'neutral': 15.0, 'min': 0.0, 'max': 100.0},
    'fe': {'neutral': 10.0, 'min': 0.0, 'max': 50.0},
    'zn': {'neutral': 2.0, 'min': 0.0, 'max': 15.0},
    'cu': {'neutral': 1.0, 'min': 0.0, 'max': 10.0},
    'b': {'neutral': 0.8, 'min': 0.0, 'max': 5.0},
    'mn': {'neutral': 15.0, 'min': 0.0, 'max': 80.0},
}


class BaseInterpolator(ABC):
    @abstractmethod
    def interpolate(self, grid_points, ticket_coords, ticket_values, parameter_name, **kwargs):
        """
        grid_points: numpy array of shape (N, 2) containing cell centroids [lat, lng]
        ticket_coords: numpy array of shape (M, 2) containing point locations [lat, lng]
        ticket_values: numpy array of shape (M,) containing soil parameter values
        parameter_name: str, name of the parameter being interpolated (e.g. 'ph')
        """
        pass


class IDWInterpolator(BaseInterpolator):
    def interpolate(self, grid_points, ticket_coords, ticket_values, parameter_name, **kwargs):
        power = kwargs.get('power', 2.0)
        num_grid = len(grid_points)
        weighted_values = np.zeros(num_grid)

        chunk_size = 1000
        epsilon = 1e-7

        for start_idx in range(0, num_grid, chunk_size):
            end_idx = min(start_idx + chunk_size, num_grid)
            grid_chunk = grid_points[start_idx:end_idx]

            diff = grid_chunk[:, np.newaxis, :] - ticket_coords[np.newaxis, :, :]
            dists = np.linalg.norm(diff, axis=2)

            matching_mask = dists < epsilon
            safe_dists = np.where(dists < epsilon, epsilon, dists)

            weights = 1.0 / (safe_dists ** power)
            sum_weights = np.sum(weights, axis=1)

            chunk_vals = np.sum(weights * ticket_values, axis=1) / sum_weights

            any_match = np.any(matching_mask, axis=1)
            if np.any(any_match):
                match_indices = np.argmax(matching_mask, axis=1)
                chunk_vals[any_match] = ticket_values[match_indices[any_match]]

            weighted_values[start_idx:end_idx] = chunk_vals

        return weighted_values


class SingleSampleGradientInterpolator(BaseInterpolator):
    def interpolate(self, grid_points, ticket_coords, ticket_values, parameter_name, **kwargs):
        ticket_point = ticket_coords[0]
        ticket_val = ticket_values[0]

        param_info = PARAMETER_DEFAULTS.get(parameter_name, {'neutral': 0.0})
        neutral_val = param_info['neutral']

        dists = np.linalg.norm(grid_points - ticket_point, axis=1)

        max_dist = kwargs.get('max_dist', np.max(dists) if len(dists) > 0 else 1.0)
        if max_dist < 1e-7:
            max_dist = 1.0

        decay_factor = np.minimum(1.0, dists / max_dist)
        interpolated_values = ticket_val + (neutral_val - ticket_val) * decay_factor

        return interpolated_values
