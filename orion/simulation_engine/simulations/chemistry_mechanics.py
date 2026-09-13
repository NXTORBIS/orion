"""
Chemical and Mechanical Simulations
Molecular dynamics, chemical reactions,
machine dynamics, and engineering systems.
"""

import numpy as np
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass

from ..core.solver_base import BaseSolver, SolverConfig
from ..simulation_engine import SimulationEngine, SimulationConfig


@dataclass
class ChemicalReaction:
    """Represents a chemical reaction."""
    name: str
    reactants: Dict[str, int]  # Species name -> stoichiometry
    products: Dict[str, int]
    rate_constant: float
    order: int = 2  # Reaction order


class ChemicalSolver(BaseSolver):
    """Solver for chemical reaction systems."""

    def __init__(self, config: SolverConfig):
        super().__init__(config)
        self.reactions: List[ChemicalReaction] = []
        self.species: Dict[str, float] = {}  # Concentrations
        self.temperature: float = 298.0  # Kelvin
        self.volume: float = 1.0  # Liters

    def add_reaction(self, reaction: ChemicalReaction) -> None:
        """Add reaction to system."""
        self.reactions.append(reaction)

    def set_concentration(self, species: str, concentration: float) -> None:
        """Set species concentration."""
        self.species[species] = concentration

    def derivative(self, t: float, state: np.ndarray) -> np.ndarray:
        """Compute reaction rate derivatives."""
        # Placeholder - actual chemistry computation in subclass
        return np.zeros_like(state)

    def compute_reaction_rate(self, reaction: ChemicalReaction) -> float:
        """Compute rate of a reaction."""
        rate = reaction.rate_constant

        # Multiply by reactant concentrations
        for reactant, stoich in reaction.reactants.items():
            c = self.species.get(reactant, 0.0)
            rate *= c ** stoich

        return rate

    def update_concentrations(self, dt: float) -> None:
        """Update species concentrations based on reactions."""
        # Compute all reaction rates
        reaction_rates = []
        for reaction in self.reactions:
            rate = self.compute_reaction_rate(reaction)
            reaction_rates.append(rate)

        # Update concentrations
        for i, reaction in enumerate(self.reactions):
            rate = reaction_rates[i]

            # Decrease reactants
            for reactant, stoich in reaction.reactants.items():
                if reactant in self.species:
                    self.species[reactant] -= stoich * rate * dt

            # Increase products
            for product, stoich in reaction.products.items():
                if product not in self.species:
                    self.species[product] = 0.0
                self.species[product] += stoich * rate * dt

        # Ensure non-negative
        for species in self.species:
            self.species[species] = max(0.0, self.species[species])


class ChemicalReactionSimulation(SimulationEngine):
    """Chemical reaction kinetics simulation."""

    def __init__(self, name: str = "Chemical Reaction"):
        config = SimulationConfig(
            simulation_type="chem",
            name=name,
            description="Chemical reaction network simulation",
            duration=10.0,
        )
        super().__init__(config)

        self.solver = ChemicalSolver(SolverConfig(method="RK4", adaptive=True))
        self.set_solver(self.solver)

        self.temperature = 298.0  # Kelvin
        self.pressure = 1.0  # atm

    def add_reaction(
        self,
        name: str,
        reactants: Dict[str, int],
        products: Dict[str, int],
        rate_constant: float,
    ) -> None:
        """
        Add chemical reaction.

        Args:
            name: Reaction name
            reactants: Dict of species -> stoichiometry
            products: Dict of species -> stoichiometry
            rate_constant: Reaction rate constant
        """
        reaction = ChemicalReaction(
            name=name,
            reactants=reactants,
            products=products,
            rate_constant=rate_constant,
        )
        self.solver.add_reaction(reaction)

    def set_initial_concentrations(
        self,
        concentrations: Dict[str, float],
    ) -> None:
        """
        Set initial species concentrations.

        Args:
            concentrations: Dict of species name -> concentration (M)
        """
        for species, conc in concentrations.items():
            self.solver.set_concentration(species, conc)

        # Store as state
        conc_array = np.array(list(concentrations.values()))
        self.state.set_state("concentrations", conc_array)
        self.state.set_state("species_names", np.array(list(concentrations.keys())))

    def step(self, dt: Optional[float] = None) -> bool:
        """Execute one reaction step."""
        if dt is None:
            dt = self.config.dt

        # Update concentrations
        self.solver.update_concentrations(dt)

        # Store in state
        species_names = self.solver.species.keys()
        conc_values = np.array(list(self.solver.species.values()))

        self.state.set_state("concentrations", conc_values)
        if not hasattr(self, "_stored_names"):
            self.state.set_state("species_names", np.array(list(species_names)))
            self._stored_names = True

        return super().step(dt)

    def get_concentrations(self) -> Dict[str, float]:
        """Get current species concentrations."""
        return self.solver.species.copy()


class MolecularDynamicsSolver(BaseSolver):
    """Molecular dynamics force field solver."""

    def __init__(self, config: SolverConfig):
        super().__init__(config)
        self.epsilon = 0.1  # Lennard-Jones parameter
        self.sigma = 1.0
        self.cutoff = 2.5

    def derivative(self, t: float, state: np.ndarray) -> np.ndarray:
        """Compute MD forces."""
        return np.zeros_like(state)

    def lennard_jones_force(
        self,
        positions: np.ndarray,
        pairs: List[Tuple[int, int]],
    ) -> np.ndarray:
        """
        Compute Lennard-Jones forces.

        Args:
            positions: Atom positions (N x 3)
            pairs: List of atom pairs to compute

        Returns:
            Forces (N x 3)
        """
        forces = np.zeros_like(positions)

        for i, j in pairs:
            r_vec = positions[j] - positions[i]
            r = np.linalg.norm(r_vec)

            if r > self.cutoff or r < 0.1:
                continue

            # Lennard-Jones force
            r6 = r ** 6
            r12 = r ** 12
            force_mag = 24 * self.epsilon * (2 / r12 - 1 / r6) / r

            f_vec = force_mag * r_vec / r

            forces[i] -= f_vec
            forces[j] += f_vec

        return forces


class MechanicalSolver(BaseSolver):
    """Solver for mechanical systems."""

    def __init__(self, config: SolverConfig):
        super().__init__(config)
        self.friction = 0.1
        self.spring_constant = 100.0

    def derivative(self, t: float, state: np.ndarray) -> np.ndarray:
        """Compute mechanical dynamics."""
        return np.zeros_like(state)

    def compute_spring_force(
        self,
        positions: np.ndarray,
        natural_lengths: np.ndarray,
        connections: List[Tuple[int, int]],
    ) -> np.ndarray:
        """
        Compute spring forces.

        Args:
            positions: Node positions
            natural_lengths: Rest lengths
            connections: List of (i, j) connections

        Returns:
            Forces on each node
        """
        forces = np.zeros_like(positions)

        for idx, (i, j) in enumerate(connections):
            r_vec = positions[j] - positions[i]
            r = np.linalg.norm(r_vec)

            if r > 0:
                # Hooke's law
                extension = r - natural_lengths[idx]
                force_mag = -self.spring_constant * extension

                f_vec = force_mag * r_vec / r

                forces[i] -= f_vec
                forces[j] += f_vec

        return forces


class MechanicalSystemSimulation(SimulationEngine):
    """Mechanical system dynamics (springs, linkages, etc.)."""

    def __init__(self, name: str = "Mechanical System"):
        config = SimulationConfig(
            simulation_type="mechanical",
            name=name,
            description="Mechanical system with springs and damping",
            duration=20.0,
        )
        super().__init__(config)

        self.solver = MechanicalSolver(SolverConfig(method="RK4"))
        self.set_solver(self.solver)

    def initialize_structure(
        self,
        positions: np.ndarray,  # Nodes
        connections: List[Tuple[int, int, float]],  # (i, j, natural_length)
        masses: Optional[np.ndarray] = None,
    ) -> None:
        """
        Initialize mechanical structure.

        Args:
            positions: Node positions (N x 3)
            connections: List of (node_i, node_j, natural_length)
            masses: Node masses
        """
        if masses is None:
            masses = np.ones(len(positions))

        self.connections = connections
        self.natural_lengths = np.array([c[2] for c in connections])

        initial_state = {
            "positions": positions.copy(),
            "velocities": np.zeros_like(positions),
            "masses": masses,
        }
        super().initialize(initial_state)

    def step(self, dt: Optional[float] = None) -> bool:
        """Execute one mechanical step."""
        if dt is None:
            dt = self.config.dt

        positions = self.state.get_state("positions")
        velocities = self.state.get_state("velocities")
        masses = self.state.get_state("masses")

        if positions is None:
            return False

        # Compute spring forces
        forces = self.solver.compute_spring_force(
            positions,
            self.natural_lengths,
            [(c[0], c[1]) for c in self.connections],
        )

        # Add gravity
        forces[:, 1] -= masses * 9.81

        # Add damping
        forces -= 0.1 * velocities

        # Update velocities
        accelerations = forces / masses[:, np.newaxis]
        velocities = velocities + accelerations * dt

        # Update positions
        positions = positions + velocities * dt

        # Update state
        self.state.set_state("positions", positions)
        self.state.set_state("velocities", velocities)

        return super().step(dt)


class GearSystemSimulation(SimulationEngine):
    """Gear system transmission simulation."""

    def __init__(self, name: str = "Gear System"):
        config = SimulationConfig(
            simulation_type="mechanical",
            name=name,
            description="Power transmission through gears",
            duration=30.0,
        )
        super().__init__(config)

        self.solver = MechanicalSolver(SolverConfig(method="RK4"))
        self.set_solver(self.solver)

        # Gear configuration
        self.gears: Dict[str, Dict[str, float]] = {}

    def add_gear(
        self,
        gear_id: str,
        radius: float,
        moment_inertia: float,
        initial_omega: float = 0.0,
    ) -> None:
        """
        Add gear to system.

        Args:
            gear_id: Gear identifier
            radius: Gear radius
            moment_inertia: Rotational inertia
            initial_omega: Initial angular velocity
        """
        self.gears[gear_id] = {
            "radius": radius,
            "moment_inertia": moment_inertia,
            "omega": initial_omega,
            "torque": 0.0,
        }

    def add_gear_mesh(
        self,
        gear1_id: str,
        gear2_id: str,
    ) -> None:
        """Add meshing relationship between gears."""
        if not hasattr(self, "_meshes"):
            self._meshes = []
        self._meshes.append((gear1_id, gear2_id))

    def step(self, dt: Optional[float] = None) -> bool:
        """Execute one gear step."""
        if dt is None:
            dt = self.config.dt

        # Transmit torque through meshes
        if hasattr(self, "_meshes"):
            for gear1_id, gear2_id in self._meshes:
                g1 = self.gears[gear1_id]
                g2 = self.gears[gear2_id]

                # Gear ratio
                ratio = g2["radius"] / g1["radius"]

                # Velocity constraint (at mesh point)
                v1 = g1["omega"] * g1["radius"]
                v2 = g2["omega"] * g2["radius"]

                # Friction/slip torque
                slip_torque = 10.0 * (v1 - v2) / (g1["radius"] + g2["radius"])

                g1["torque"] -= slip_torque
                g2["torque"] += slip_torque * ratio

        # Update angular velocities
        for gear in self.gears.values():
            alpha = gear["torque"] / gear["moment_inertia"]
            gear["omega"] += alpha * dt
            gear["torque"] = 0.0  # Reset torque each step

        # Store state
        gears_omega = np.array([g["omega"] for g in self.gears.values()])
        self.state.set_state("gear_omegas", gears_omega)

        return super().step(dt)
