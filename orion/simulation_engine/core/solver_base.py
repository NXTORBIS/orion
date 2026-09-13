"""
Solver Architecture
Differential equation solvers, numerical methods (RK4, etc),
adaptive time stepping, and stability management.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Dict, Any, Tuple, Optional, List
import numpy as np


@dataclass
class SolverConfig:
    """Configuration for numerical solver."""
    method: str = "RK4"  # RK4, Euler, RK45, etc.
    dt: float = 0.01  # Time step
    adaptive: bool = True  # Use adaptive time stepping
    tolerance: float = 1e-6  # Accuracy tolerance
    max_step: float = 0.1  # Maximum time step
    min_step: float = 1e-6  # Minimum time step
    stability_check: bool = True  # Check stability
    max_iterations: int = 10000  # Max solver iterations


class BaseSolver(ABC):
    """
    Base class for all numerical solvers.
    Handles differential equation solving with various methods.
    """

    def __init__(self, config: SolverConfig):
        """
        Initialize solver.

        Args:
            config: SolverConfig object
        """
        self.config = config
        self.step_count = 0
        self.rejected_steps = 0
        self.statistics: Dict[str, Any] = {
            "total_steps": 0,
            "successful_steps": 0,
            "rejected_steps": 0,
            "avg_step_size": 0.0,
            "error_estimates": [],
        }

    @abstractmethod
    def derivative(self, t: float, state: np.ndarray) -> np.ndarray:
        """
        Compute derivative dy/dt.

        Args:
            t: Current time
            state: Current state vector

        Returns:
            Derivative vector
        """
        pass

    def step(self, t: float, state: np.ndarray, dt: Optional[float] = None) -> Tuple[np.ndarray, float]:
        """
        Take one solver step.

        Args:
            t: Current time
            state: Current state
            dt: Time step (uses config.dt if None)

        Returns:
            Tuple of (new_state, actual_dt_used)
        """
        if dt is None:
            dt = self.config.dt

        if self.config.adaptive:
            return self._adaptive_step(t, state, dt)
        else:
            method = getattr(self, f"_{self.config.method.lower()}", self._rk4)
            new_state = method(t, state, dt)
            self.statistics["successful_steps"] += 1
            return new_state, dt

    def _rk4(self, t: float, state: np.ndarray, dt: float) -> np.ndarray:
        """
        4th order Runge-Kutta method.
        Provides good accuracy without excessive computation.

        Args:
            t: Current time
            state: Current state
            dt: Time step

        Returns:
            New state
        """
        k1 = self.derivative(t, state)
        k2 = self.derivative(t + dt / 2, state + dt * k1 / 2)
        k3 = self.derivative(t + dt / 2, state + dt * k2 / 2)
        k4 = self.derivative(t + dt, state + dt * k3)

        return state + dt * (k1 + 2 * k2 + 2 * k3 + k4) / 6

    def _rk45(self, t: float, state: np.ndarray, dt: float) -> np.ndarray:
        """
        5th order Runge-Kutta method with embedded 4th order for error estimate.
        """
        k1 = self.derivative(t, state)
        k2 = self.derivative(t + dt / 5, state + dt * k1 / 5)
        k3 = self.derivative(t + 3 * dt / 10, state + dt * (3 * k1 + 9 * k2) / 40)
        k4 = self.derivative(
            t + 4 * dt / 5,
            state + dt * (44 * k1 - 168 * k2 + 160 * k3) / 45,
        )
        k5 = self.derivative(
            t + 8 * dt / 9,
            state + dt * (19372 * k1 - 76080 * k2 + 64448 * k3 - 1908 * k4) / 6561,
        )

        y4 = state + dt * (25 * k1 + 1408 * k3 + 2197 * k4 - k5) / 216
        y5 = state + dt * (16 * k1 + 6656 * k3 + 28561 * k4 - 9 * k5) / 135960

        error = np.max(np.abs(y5 - y4))
        self.statistics["error_estimates"].append(error)

        return y5

    def _euler(self, t: float, state: np.ndarray, dt: float) -> np.ndarray:
        """
        Euler forward method (basic, less accurate).
        """
        return state + dt * self.derivative(t, state)

    def _adaptive_step(
        self, t: float, state: np.ndarray, dt: float
    ) -> Tuple[np.ndarray, float]:
        """
        Adaptive time stepping using error estimation.

        Args:
            t: Current time
            state: Current state
            dt: Suggested time step

        Returns:
            Tuple of (new_state, actual_dt_used)
        """
        current_dt = dt
        safety_factor = 0.9

        for attempt in range(5):
            # Take two half steps
            half_state_1, _ = self._rk4(t, state, current_dt / 2)
            half_state_2, _ = self._rk4(t + current_dt / 2, half_state_1, current_dt / 2)

            # Take one full step
            full_state, _ = self._rk4(t, state, current_dt)

            # Estimate error
            error = np.max(np.abs(half_state_2 - full_state))
            self.statistics["error_estimates"].append(error)

            # Check if step is acceptable
            if error <= self.config.tolerance or current_dt <= self.config.min_step:
                self.statistics["successful_steps"] += 1

                # Adjust step size for next iteration
                if error > 0:
                    factor = (self.config.tolerance / error) ** 0.2
                    self.config.dt = np.clip(
                        current_dt * factor * safety_factor,
                        self.config.min_step,
                        self.config.max_step,
                    )

                return half_state_2, current_dt

            # Step rejected, reduce step size
            self.rejected_steps += 1
            self.statistics["rejected_steps"] += 1
            current_dt *= 0.5

        # If still failing, use half step anyway
        return self._rk4(t, state, current_dt), current_dt

    def check_stability(self, state: np.ndarray) -> Tuple[bool, Optional[str]]:
        """
        Check numerical stability of current state.

        Args:
            state: Current state vector

        Returns:
            Tuple of (is_stable, error_message)
        """
        # Check for NaN
        if np.any(np.isnan(state)):
            return False, "NaN detected in state"

        # Check for infinity
        if np.any(np.isinf(state)):
            return False, "Infinity detected in state"

        # Check for excessive growth
        if np.any(np.abs(state) > 1e10):
            return False, "State values extremely large (potential instability)"

        return True, None

    def solve(
        self,
        t_span: Tuple[float, float],
        t_eval: Optional[np.ndarray] = None,
        dense_output: bool = False,
    ) -> Dict[str, Any]:
        """
        Solve ODE over time span.

        Args:
            t_span: (t0, tf) time span
            t_eval: Times to evaluate solution
            dense_output: Return dense output solution

        Returns:
            Dictionary with 't', 'y', and optional 'solution'
        """
        t0, tf = t_span
        if t_eval is None:
            t_eval = np.arange(t0, tf + self.config.dt, self.config.dt)

        solution_times = []
        solution_states = []

        current_state = self.derivative(t0, np.zeros(1))  # Initial state shape
        current_time = t0

        while current_time < tf and self.step_count < self.config.max_iterations:
            solution_times.append(current_time)
            solution_states.append(current_state.copy())

            # Check stability
            if self.config.stability_check:
                is_stable, error = self.check_stability(current_state)
                if not is_stable:
                    break

            # Take step
            remaining = tf - current_time
            dt = min(self.config.dt, remaining)
            current_state, actual_dt = self.step(current_time, current_state, dt)
            current_time += actual_dt
            self.step_count += 1

        self.statistics["total_steps"] = self.step_count
        if self.statistics["successful_steps"] > 0:
            self.statistics["avg_step_size"] = (
                (tf - t0) / self.statistics["successful_steps"]
            )

        return {
            "t": np.array(solution_times),
            "y": np.array(solution_states),
            "message": "Solve successful",
            "success": current_time >= tf,
        }

    def get_statistics(self) -> Dict[str, Any]:
        """Get solver statistics."""
        return self.statistics.copy()

    def reset(self) -> None:
        """Reset solver statistics."""
        self.step_count = 0
        self.rejected_steps = 0
        self.statistics = {
            "total_steps": 0,
            "successful_steps": 0,
            "rejected_steps": 0,
            "avg_step_size": 0.0,
            "error_estimates": [],
        }
