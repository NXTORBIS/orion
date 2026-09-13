"""
Simulation State Management
Handles state representation, time stepping, numerical integration,
and memory optimization.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
from collections import deque
import time


@dataclass
class StateSnapshot:
    """Immutable snapshot of simulation state at a specific time."""
    timestamp: float
    time_step: int
    state_dict: Dict[str, np.ndarray]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_state(self, key: str) -> Optional[np.ndarray]:
        """Get state array by key."""
        return self.state_dict.get(key)

    def memory_usage_mb(self) -> float:
        """Calculate memory usage in MB."""
        total_bytes = 0
        for array in self.state_dict.values():
            if isinstance(array, np.ndarray):
                total_bytes += array.nbytes
        return total_bytes / (1024 * 1024)


class SimulationState:
    """
    Manages simulation state with time stepping and memory optimization.
    Supports:
    - Multiple state arrays (positions, velocities, etc.)
    - Automatic time stepping
    - Circular buffer for memory efficiency
    - State history management
    """

    def __init__(
        self,
        initial_time: float = 0.0,
        dt: float = 0.01,
        max_history_size: int = 100,
        max_memory_mb: float = 512.0,
    ):
        """
        Initialize simulation state manager.

        Args:
            initial_time: Starting simulation time
            dt: Initial time step
            max_history_size: Maximum number of snapshots to keep
            max_memory_mb: Maximum memory allowed for history
        """
        self.time = initial_time
        self.dt = dt
        self.time_step = 0
        self.max_history_size = max_history_size
        self.max_memory_mb = max_memory_mb

        # Current state arrays
        self.state_dict: Dict[str, np.ndarray] = {}

        # History management with circular buffer
        self.history: deque = deque(maxlen=max_history_size)
        self.memory_usage_mb = 0.0

        # Performance tracking
        self.performance_stats = {
            "step_times_ms": deque(maxlen=100),
            "memory_usage_history": [],
        }

    def set_state(self, key: str, value: np.ndarray) -> None:
        """
        Set a state array.

        Args:
            key: State variable name
            value: Numpy array with state data
        """
        self.state_dict[key] = value.copy() if isinstance(value, np.ndarray) else value

    def get_state(self, key: str) -> Optional[np.ndarray]:
        """Get current state array."""
        return self.state_dict.get(key)

    def get_all_states(self) -> Dict[str, np.ndarray]:
        """Get all current state arrays."""
        return self.state_dict.copy()

    def step_time(self, dt: Optional[float] = None) -> None:
        """
        Advance simulation time by one step.

        Args:
            dt: Custom time step (uses self.dt if None)
        """
        step_start = time.time()

        if dt is not None:
            self.dt = dt
        self.time += self.dt
        self.time_step += 1

        # Record performance
        step_ms = (time.time() - step_start) * 1000
        self.performance_stats["step_times_ms"].append(step_ms)

    def save_snapshot(self, metadata: Optional[Dict[str, Any]] = None) -> StateSnapshot:
        """
        Save current state as a snapshot.

        Args:
            metadata: Additional metadata to store

        Returns:
            StateSnapshot object
        """
        snapshot = StateSnapshot(
            timestamp=self.time,
            time_step=self.time_step,
            state_dict={k: v.copy() if isinstance(v, np.ndarray) else v
                        for k, v in self.state_dict.items()},
            metadata=metadata or {},
        )

        self.history.append(snapshot)
        self._manage_memory()

        return snapshot

    def get_history(self, max_age: Optional[float] = None) -> List[StateSnapshot]:
        """
        Get state history.

        Args:
            max_age: Only return snapshots younger than max_age seconds

        Returns:
            List of StateSnapshot objects
        """
        history = list(self.history)

        if max_age is not None:
            cutoff_time = self.time - max_age
            history = [s for s in history if s.timestamp >= cutoff_time]

        return history

    def _manage_memory(self) -> None:
        """Automatically manage memory usage."""
        # Calculate current memory
        total_memory = sum(snapshot.memory_usage_mb() for snapshot in self.history)
        self.memory_usage_mb = total_memory

        # Log memory history
        self.performance_stats["memory_usage_history"].append(
            (self.time, total_memory)
        )

        # Remove oldest snapshots if exceeding limit
        while self.memory_usage_mb > self.max_memory_mb and len(self.history) > 1:
            self.history.popleft()
            total_memory = sum(
                snapshot.memory_usage_mb() for snapshot in self.history
            )
            self.memory_usage_mb = total_memory

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
        step_times = list(self.performance_stats["step_times_ms"])
        if not step_times:
            return {
                "avg_step_time_ms": 0.0,
                "max_step_time_ms": 0.0,
                "memory_used_mb": self.memory_usage_mb,
                "snapshots_stored": len(self.history),
            }

        return {
            "avg_step_time_ms": np.mean(step_times),
            "max_step_time_ms": np.max(step_times),
            "min_step_time_ms": np.min(step_times),
            "memory_used_mb": self.memory_usage_mb,
            "snapshots_stored": len(self.history),
            "fps": 1000.0 / np.mean(step_times),
        }

    def reset(self) -> None:
        """Reset simulation state."""
        self.time = 0.0
        self.time_step = 0
        self.state_dict.clear()
        self.history.clear()
        self.memory_usage_mb = 0.0
