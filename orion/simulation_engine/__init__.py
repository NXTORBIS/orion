"""
ORION Simulation Engine Infrastructure
Core framework powering all 6 simulation types:
- Physics Simulations
- Social Simulations
- Economic Simulations
- Biological Simulations
- Chemical Simulations
- Mechanical Simulations

Provides unified interface for state management, solving, validation,
visualization, and data export.
"""

from .core.state_manager import SimulationState, StateSnapshot
from .core.solver_base import BaseSolver, SolverConfig
from .core.validator import ParameterValidator, ValidationResult
from .visualization.renderer import VisualizationRenderer, RenderConfig
from .data_export.exporter import DataExporter, ExportConfig
from .simulation_engine import SimulationEngine

__version__ = "1.0.0"
__author__ = "ORION Development Team"

__all__ = [
    "SimulationEngine",
    "SimulationState",
    "StateSnapshot",
    "BaseSolver",
    "SolverConfig",
    "ParameterValidator",
    "ValidationResult",
    "VisualizationRenderer",
    "RenderConfig",
    "DataExporter",
    "ExportConfig",
]
