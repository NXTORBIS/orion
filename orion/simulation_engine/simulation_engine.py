"""
Main Simulation Engine
Orchestrates all simulation components:
- State management
- Solver execution
- Parameter validation
- Visualization
- Data export
"""

from typing import Dict, Any, Optional, Callable, List, Tuple
from pathlib import Path
import numpy as np
import time
from dataclasses import dataclass

from .core.state_manager import SimulationState, StateSnapshot
from .core.solver_base import BaseSolver, SolverConfig
from .core.validator import ParameterValidator, ValidationResult
from .visualization.renderer import VisualizationRenderer, RenderConfig
from .data_export.exporter import DataExporter, ExportConfig


@dataclass
class SimulationConfig:
    """Overall simulation configuration."""
    simulation_type: str  # physics, social, economic, bio, chem, mechanical
    name: str = "Simulation"
    description: str = ""
    duration: float = 10.0  # Simulation duration
    dt: float = 0.01  # Time step
    max_particles: int = 100000
    real_time_mode: bool = False


class SimulationEngine:
    """
    Main orchestrator for all simulation types.
    Coordinates state management, solving, validation, and output.
    """

    def __init__(self, config: SimulationConfig):
        """
        Initialize simulation engine.

        Args:
            config: SimulationConfig object
        """
        self.config = config
        self.state = SimulationState(dt=config.dt)
        self.solver: Optional[BaseSolver] = None
        self.validator = ParameterValidator()
        self.renderer: Optional[VisualizationRenderer] = None
        self.exporter: Optional[DataExporter] = None

        # Execution tracking
        self.is_running = False
        self.is_paused = False
        self.execution_time = 0.0
        self.iteration_count = 0

        # Callbacks
        self.step_callbacks: List[Callable] = []
        self.completion_callbacks: List[Callable] = []

    def set_solver(self, solver: BaseSolver) -> None:
        """
        Set the numerical solver.

        Args:
            solver: BaseSolver instance
        """
        self.solver = solver

    def set_renderer(self, renderer: VisualizationRenderer) -> None:
        """
        Set the visualization renderer.

        Args:
            renderer: VisualizationRenderer instance
        """
        self.renderer = renderer

    def set_exporter(self, exporter: DataExporter) -> None:
        """
        Set the data exporter.

        Args:
            exporter: DataExporter instance
        """
        self.exporter = exporter

    def validate_parameters(
        self,
        params: Dict[str, Any],
        auto_correct: bool = False,
    ) -> ValidationResult:
        """
        Validate simulation parameters.

        Args:
            params: Parameter dictionary
            auto_correct: Auto-correct common issues

        Returns:
            ValidationResult
        """
        return self.validator.validate(params, auto_correct)

    def add_step_callback(self, callback: Callable) -> None:
        """
        Add callback executed after each step.

        Args:
            callback: Callback function(step, state, time)
        """
        self.step_callbacks.append(callback)

    def add_completion_callback(self, callback: Callable) -> None:
        """
        Add callback executed when simulation completes.

        Args:
            callback: Callback function(state, statistics)
        """
        self.completion_callbacks.append(callback)

    def initialize(self, initial_state: Dict[str, np.ndarray]) -> None:
        """
        Initialize simulation with initial conditions.

        Args:
            initial_state: Dictionary of initial state arrays
        """
        for key, value in initial_state.items():
            self.state.set_state(key, value)
        print(f"Simulation '{self.config.name}' initialized")

    def step(self, dt: Optional[float] = None) -> bool:
        """
        Execute one simulation step.

        Args:
            dt: Time step (uses config.dt if None)

        Returns:
            True if step successful, False if should halt
        """
        if self.solver is None:
            print("Error: No solver configured")
            return False

        if self.is_paused:
            return True

        # Advance state
        self.state.step_time(dt)
        self.iteration_count += 1

        # Execute solver
        current_state = self.state.get_all_states()
        if current_state:
            # For now, just update time (actual physics/solving happens in subclasses)
            pass

        # Save snapshot periodically
        if self.iteration_count % 10 == 0:
            self.state.save_snapshot()

        # Render frame if renderer configured
        if self.renderer is not None:
            current_state = self.state.get_all_states()
            self.renderer.add_frame(current_state, self.state.time)

        # Execute callbacks
        for callback in self.step_callbacks:
            try:
                callback(self.iteration_count, current_state, self.state.time)
            except Exception as e:
                print(f"Callback error: {e}")

        # Check stopping condition
        if self.state.time >= self.config.duration:
            return False

        return True

    def run(self, steps: Optional[int] = None) -> Dict[str, Any]:
        """
        Run simulation for specified duration or steps.

        Args:
            steps: Number of steps (runs until duration if None)

        Returns:
            Dictionary with simulation results
        """
        if self.solver is None:
            print("Error: No solver configured")
            return {}

        self.is_running = True
        start_time = time.time()

        if steps is None:
            # Calculate steps from duration
            steps = int(self.config.duration / self.config.dt)

        try:
            for i in range(steps):
                if not self.step():
                    break

                # Real-time mode throttling
                if self.config.real_time_mode:
                    elapsed = time.time() - start_time
                    should_be_at = i * self.config.dt
                    if should_be_at > elapsed:
                        time.sleep(should_be_at - elapsed)

        except Exception as e:
            print(f"Simulation error: {e}")
            return {}
        finally:
            self.is_running = False

        self.execution_time = time.time() - start_time

        # Collect results
        results = self._collect_results()

        # Execute completion callbacks
        for callback in self.completion_callbacks:
            try:
                callback(self.state, results)
            except Exception as e:
                print(f"Completion callback error: {e}")

        return results

    def pause(self) -> None:
        """Pause simulation."""
        self.is_paused = True
        print("Simulation paused")

    def resume(self) -> None:
        """Resume simulation."""
        self.is_paused = False
        print("Simulation resumed")

    def reset(self) -> None:
        """Reset simulation."""
        self.state.reset()
        self.iteration_count = 0
        self.execution_time = 0.0
        self.is_running = False
        self.is_paused = False
        if self.solver:
            self.solver.reset()
        if self.renderer:
            self.renderer.clear_frames()
        print("Simulation reset")

    def get_state(self) -> Dict[str, np.ndarray]:
        """Get current simulation state."""
        return self.state.get_all_states()

    def get_history(self, max_age: Optional[float] = None) -> List[StateSnapshot]:
        """Get state history."""
        return self.state.get_history(max_age)

    def export_data(
        self,
        output_path: Path,
        format: str = "csv",
        include_history: bool = True,
    ) -> bool:
        """
        Export simulation data.

        Args:
            output_path: Path to save data
            format: Export format (csv, json, hdf5)
            include_history: Include full history

        Returns:
            True if successful
        """
        if self.exporter is None:
            self.exporter = DataExporter(ExportConfig(format=format))

        # Prepare data for export
        export_data = self.state.get_all_states().copy()

        # Add time array
        if self.state.history:
            export_data["time"] = np.array([s.timestamp for s in self.state.history])

        # Add time step array
        export_data["time_step"] = np.arange(self.iteration_count + 1)

        # Metadata
        metadata = {
            "simulation_name": self.config.name,
            "simulation_type": self.config.simulation_type,
            "duration": self.config.duration,
            "final_time": self.state.time,
            "iterations": self.iteration_count,
            "execution_time_s": self.execution_time,
        }

        return self.exporter.export(export_data, output_path, format, metadata)

    def export_animation(self, output_path: Path, fps: int = 30) -> bool:
        """
        Export simulation as animation.

        Args:
            output_path: Path to save animation
            fps: Frames per second

        Returns:
            True if successful
        """
        if self.renderer is None or self.renderer.get_frame_count() == 0:
            print("Error: No frames to animate")
            return False

        return self.renderer.create_animation(output_path, fps)

    def _collect_results(self) -> Dict[str, Any]:
        """Collect simulation results."""
        final_state = self.state.get_all_states()
        stats = self.state.get_performance_stats()

        if self.solver:
            stats.update(self.solver.get_statistics())

        return {
            "final_state": final_state,
            "execution_time": self.execution_time,
            "iterations": self.iteration_count,
            "statistics": stats,
            "history": self.state.get_history() if self.state.history else [],
        }

    def get_diagnostics(self) -> Dict[str, Any]:
        """Get simulation diagnostics and status."""
        return {
            "name": self.config.name,
            "type": self.config.simulation_type,
            "is_running": self.is_running,
            "is_paused": self.is_paused,
            "current_time": self.state.time,
            "current_step": self.iteration_count,
            "duration": self.config.duration,
            "progress": self.state.time / self.config.duration if self.config.duration > 0 else 0,
            "execution_time": self.execution_time,
            "state_memory_mb": self.state.memory_usage_mb,
            "has_renderer": self.renderer is not None,
            "has_exporter": self.exporter is not None,
            "frame_count": self.renderer.get_frame_count() if self.renderer else 0,
            "performance": self.state.get_performance_stats(),
        }
