"""
Social Simulation Engine
Agent-based modeling with population dynamics and emergent behavior detection.
"""

from .agent import Agent, AgentState, AgentRole, AgentMemory, AgentMetabolism
from .population_dynamics import (
    PopulationDynamics,
    PopulationConfig,
    DemographicStats,
)
from .emergent_behavior import (
    EmergentBehavior,
    EmergentBehaviorMetrics,
    SocialNetwork,
    InformationDiffusion,
)
from .social_simulation import (
    SocialSimulation,
    SocialSimulationConfig,
    SocialSimulationEnvironment,
)

__version__ = "1.0.0"
__author__ = "ORION Social Simulation Team"

__all__ = [
    "Agent",
    "AgentState",
    "AgentRole",
    "AgentMemory",
    "AgentMetabolism",
    "PopulationDynamics",
    "PopulationConfig",
    "DemographicStats",
    "EmergentBehavior",
    "EmergentBehaviorMetrics",
    "SocialNetwork",
    "InformationDiffusion",
    "SocialSimulation",
    "SocialSimulationConfig",
    "SocialSimulationEnvironment",
]
