"""
Physics Simulation Package
Three-subsystem physics engine:
1. Mechanics Engine (Rigid & Soft Bodies) - Newton's equations with constraints
2. Fluid Dynamics Engine (Navier-Stokes) - Incompressible flow solver
3. Particle System Engine - Physics-based effects with lifecycle management
"""

from .mechanics_solver import MechanicsSolver, RigidBody
from .fluid_dynamics_solver import FluidDynamicsSolver
from .particle_system_solver import ParticleSystemSolver, Particle
from .physics_engine import PhysicsEngine, PhysicsEngineConfig

__all__ = [
    "MechanicsSolver",
    "RigidBody",
    "FluidDynamicsSolver",
    "ParticleSystemSolver",
    "Particle",
    "PhysicsEngine",
    "PhysicsEngineConfig",
]
