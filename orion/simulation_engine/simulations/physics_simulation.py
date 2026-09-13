"""
Physics Simulations
Rigid body dynamics, soft body simulation, collision detection,
fluid dynamics, and particle systems.
"""

import numpy as np
from typing import Dict, Any, Optional, List, Tuple
from abc import ABC, abstractmethod

from ..core.solver_base import BaseSolver, SolverConfig
from ..simulation_engine import SimulationEngine, SimulationConfig
from ..core.validator import PhysicsValidator


class PhysicsSolver(BaseSolver):
    """
    Physics equation solver.
    Handles N-body dynamics, forces, collisions.
    """

    def __init__(
        self,
        config: SolverConfig,
        gravity: float = 9.81,
        damping: float = 0.0,
        collision_enabled: bool = True,
    ):
        """
        Initialize physics solver.

        Args:
            config: SolverConfig
            gravity: Gravitational acceleration
            damping: Velocity damping factor
            collision_enabled: Enable collision detection
        """
        super().__init__(config)
        self.gravity = gravity
        self.damping = damping
        self.collision_enabled = collision_enabled
        self.forces: Dict[str, np.ndarray] = {}
        self.masses: Optional[np.ndarray] = None

    def set_masses(self, masses: np.ndarray) -> None:
        """Set particle masses."""
        self.masses = masses

    def add_force(self, force_name: str, force_vector: np.ndarray) -> None:
        """Add external force."""
        self.forces[force_name] = force_vector

    def derivative(self, t: float, state: np.ndarray) -> np.ndarray:
        """
        Compute derivative for physics ODE.
        State: [x1, y1, z1, x2, y2, z2, ..., vx1, vy1, vz1, vx2, vy2, vz2, ...]
        """
        # This is a placeholder - subclasses implement specific physics
        return np.zeros_like(state)

    def compute_forces(
        self,
        positions: np.ndarray,
        velocities: np.ndarray,
    ) -> np.ndarray:
        """
        Compute all forces on particles.

        Args:
            positions: Particle positions (N x 3)
            velocities: Particle velocities (N x 3)

        Returns:
            Force vectors (N x 3)
        """
        n_particles = len(positions)
        forces = np.zeros_like(positions)

        # Gravity
        if self.gravity != 0:
            forces[:, 1] -= self.gravity * (self.masses if self.masses is not None else 1.0)

        # Damping
        if self.damping > 0:
            forces -= self.damping * velocities

        # External forces
        for force_vector in self.forces.values():
            forces += force_vector

        return forces

    def detect_collisions(
        self,
        positions: np.ndarray,
        radii: np.ndarray,
    ) -> List[Tuple[int, int]]:
        """
        Detect particle collisions.

        Args:
            positions: Particle positions
            radii: Particle radii

        Returns:
            List of (i, j) collision pairs
        """
        collisions = []
        n_particles = len(positions)

        for i in range(n_particles):
            for j in range(i + 1, n_particles):
                dist = np.linalg.norm(positions[i] - positions[j])
                if dist < radii[i] + radii[j]:
                    collisions.append((i, j))

        return collisions

    def handle_collision(
        self,
        i: int,
        j: int,
        positions: np.ndarray,
        velocities: np.ndarray,
        masses: Optional[np.ndarray] = None,
        restitution: float = 0.5,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Handle elastic collision between two particles.

        Args:
            i, j: Particle indices
            positions: Particle positions
            velocities: Particle velocities
            masses: Particle masses
            restitution: Coefficient of restitution

        Returns:
            Updated (positions, velocities)
        """
        if masses is None:
            masses = np.ones(len(positions))

        # Separate overlapping particles
        r_ij = positions[j] - positions[i]
        dist = np.linalg.norm(r_ij)
        if dist > 0:
            r_ij = r_ij / dist

        # Relative velocity
        v_rel = velocities[i] - velocities[j]
        v_rel_along_r = np.dot(v_rel, r_ij)

        if v_rel_along_r > 0:  # Particles approaching
            # Collision impulse
            m_i, m_j = masses[i], masses[j]
            impulse = -(1 + restitution) * v_rel_along_r / (1/m_i + 1/m_j)

            # Update velocities
            velocities[i] += (impulse / m_i) * r_ij
            velocities[j] -= (impulse / m_j) * r_ij

        return positions, velocities


class RigidBodySimulation(SimulationEngine):
    """Rigid body dynamics simulation."""

    def __init__(self, name: str = "Rigid Body Simulation"):
        config = SimulationConfig(
            simulation_type="physics",
            name=name,
            description="Rigid body dynamics with collision detection",
        )
        super().__init__(config)

        self.solver = PhysicsSolver(
            SolverConfig(method="RK4"),
            gravity=9.81,
            collision_enabled=True,
        )
        self.set_solver(self.solver)

        self.validator = PhysicsValidator()
        self.radii: Optional[np.ndarray] = None
        self.restitution: float = 0.5

    def initialize(
        self,
        positions: np.ndarray,
        velocities: np.ndarray,
        masses: Optional[np.ndarray] = None,
        radii: Optional[np.ndarray] = None,
    ) -> None:
        """
        Initialize rigid body simulation.

        Args:
            positions: Initial positions (N x 3)
            velocities: Initial velocities (N x 3)
            masses: Particle masses
            radii: Particle radii for collision
        """
        if masses is None:
            masses = np.ones(len(positions))
        if radii is None:
            radii = np.ones(len(positions)) * 0.1

        self.radii = radii
        self.solver.set_masses(masses)

        initial_state = {
            "positions": positions,
            "velocities": velocities,
            "masses": masses,
            "radii": radii,
        }
        super().initialize(initial_state)

    def step(self, dt: Optional[float] = None) -> bool:
        """Execute one simulation step with physics."""
        if self.solver is None:
            return False

        # Get current state
        positions = self.state.get_state("positions")
        velocities = self.state.get_state("velocities")
        masses = self.state.get_state("masses")
        radii = self.state.get_state("radii")

        if positions is None or velocities is None:
            return False

        # Compute forces
        forces = self.solver.compute_forces(positions, velocities)

        # Update velocities
        if masses is not None:
            accelerations = forces / masses[:, np.newaxis]
            velocities = velocities + accelerations * self.config.dt

        # Update positions
        positions = positions + velocities * self.config.dt

        # Handle collisions
        if self.solver.collision_enabled and radii is not None:
            collisions = self.solver.detect_collisions(positions, radii)
            for i, j in collisions:
                positions, velocities = self.solver.handle_collision(
                    i, j, positions, velocities, masses, self.restitution
                )

        # Update state
        self.state.set_state("positions", positions)
        self.state.set_state("velocities", velocities)

        # Call parent step for time management and callbacks
        return super().step(dt)


class FluidDynamicsSimulation(SimulationEngine):
    """Navier-Stokes based fluid dynamics simulation."""

    def __init__(self, name: str = "Fluid Dynamics"):
        config = SimulationConfig(
            simulation_type="physics",
            name=name,
            description="Fluid dynamics with Navier-Stokes solver",
        )
        super().__init__(config)

        self.solver = PhysicsSolver(SolverConfig(method="RK4"))
        self.set_solver(self.solver)

        # Grid parameters
        self.grid_size = (64, 64, 64)
        self.cell_size = 1.0

        # Fluid parameters
        self.viscosity = 0.01
        self.density = 1.0

    def initialize_grid(
        self,
        grid_size: Tuple[int, int, int] = (64, 64, 64),
        cell_size: float = 1.0,
    ) -> None:
        """
        Initialize velocity grid.

        Args:
            grid_size: Grid dimensions
            cell_size: Size of each grid cell
        """
        self.grid_size = grid_size
        self.cell_size = cell_size

        initial_state = {
            "velocity_x": np.zeros(grid_size),
            "velocity_y": np.zeros(grid_size),
            "velocity_z": np.zeros(grid_size),
            "pressure": np.zeros(grid_size),
            "density": np.ones(grid_size) * self.density,
        }
        super().initialize(initial_state)

    def add_source(
        self,
        field_name: str,
        position: np.ndarray,
        strength: float,
        radius: float = 3.0,
    ) -> None:
        """
        Add source/sink to simulation.

        Args:
            field_name: Field to modify (velocity_x, density, etc.)
            position: Source position
            strength: Source strength
            radius: Influence radius
        """
        field = self.state.get_state(field_name)
        if field is not None:
            # Create Gaussian influence
            x, y, z = np.ogrid[:self.grid_size[0], :self.grid_size[1], :self.grid_size[2]]
            dist = np.sqrt((x - position[0])**2 + (y - position[1])**2 + (z - position[2])**2)
            influence = strength * np.exp(-(dist**2) / (2 * radius**2))
            field += influence
            self.state.set_state(field_name, field)


class ParticleSystemSimulation(SimulationEngine):
    """Particle system simulation for effects (smoke, fire, dust)."""

    def __init__(self, name: str = "Particle System"):
        config = SimulationConfig(
            simulation_type="physics",
            name=name,
            description="Particle effects system (smoke, fire, dust)",
        )
        super().__init__(config)

        self.solver = PhysicsSolver(SolverConfig(method="RK4"))
        self.set_solver(self.solver)

    def spawn_particles(
        self,
        position: np.ndarray,
        velocity: np.ndarray,
        count: int,
        lifetime: float = 5.0,
        spread: float = 0.5,
    ) -> None:
        """
        Spawn new particles.

        Args:
            position: Spawn position
            velocity: Base velocity
            count: Number of particles
            lifetime: Particle lifetime
            spread: Velocity spread factor
        """
        positions = self.state.get_state("positions")
        velocities = self.state.get_state("velocities")
        lifetimes = self.state.get_state("lifetimes")

        if positions is None:
            positions = np.zeros((count, 3))
            velocities = np.zeros((count, 3))
            lifetimes = np.zeros(count)

        # Add new particles
        new_positions = position + np.random.randn(count, 3) * spread
        new_velocities = velocity + np.random.randn(count, 3) * spread
        new_lifetimes = np.ones(count) * lifetime

        positions = np.vstack([positions, new_positions])
        velocities = np.vstack([velocities, new_velocities])
        lifetimes = np.concatenate([lifetimes, new_lifetimes])

        self.state.set_state("positions", positions)
        self.state.set_state("velocities", velocities)
        self.state.set_state("lifetimes", lifetimes)

    def step(self, dt: Optional[float] = None) -> bool:
        """Execute particle step with lifetime management."""
        # Update lifetimes
        lifetimes = self.state.get_state("lifetimes")
        if lifetimes is not None:
            lifetimes -= self.config.dt

            # Remove dead particles
            alive_mask = lifetimes > 0
            for key in self.state.get_all_states():
                array = self.state.get_state(key)
                if array is not None and len(array) > 0:
                    self.state.set_state(key, array[alive_mask])

        return super().step(dt)
