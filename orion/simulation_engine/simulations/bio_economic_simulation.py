"""
Biological and Economic Simulations
Agent-based ecosystem models, population dynamics,
market simulations, economic systems.
"""

import numpy as np
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass

from ..core.solver_base import BaseSolver, SolverConfig
from ..simulation_engine import SimulationEngine, SimulationConfig


@dataclass
class Agent:
    """Base agent for simulations."""
    id: int
    position: np.ndarray  # 2D position
    velocity: np.ndarray
    energy: float
    age: float
    species: int = 0  # Species identifier


class BiologicalSolver(BaseSolver):
    """Solver for biological/ecosystem simulations."""

    def __init__(self, config: SolverConfig):
        super().__init__(config)
        self.agents: List[Agent] = []
        self.species_params: Dict[int, Dict[str, float]] = {}

    def derivative(self, t: float, state: np.ndarray) -> np.ndarray:
        """Compute derivative for population dynamics."""
        return np.zeros_like(state)

    def add_species(
        self,
        species_id: int,
        birth_rate: float = 0.1,
        death_rate: float = 0.05,
        energy_per_offspring: float = 50.0,
    ) -> None:
        """Add species parameters."""
        self.species_params[species_id] = {
            "birth_rate": birth_rate,
            "death_rate": death_rate,
            "energy_per_offspring": energy_per_offspring,
        }

    def update_agents(self, dt: float) -> None:
        """Update agent states (aging, metabolism)."""
        for agent in self.agents:
            agent.age += dt
            agent.energy -= 0.01 * dt  # Metabolism


class BiologicalSimulation(SimulationEngine):
    """Ecosystem/population dynamics simulation."""

    def __init__(self, name: str = "Ecosystem Simulation"):
        config = SimulationConfig(
            simulation_type="bio",
            name=name,
            description="Ecosystem with predator-prey dynamics",
            duration=100.0,
        )
        super().__init__(config)

        self.solver = BiologicalSolver(SolverConfig(method="RK4"))
        self.set_solver(self.solver)

        # Spatial parameters
        self.world_size = np.array([100.0, 100.0])
        self.agents: List[Agent] = []

    def add_agents(
        self,
        positions: np.ndarray,
        velocities: np.ndarray,
        energies: np.ndarray,
        species: Optional[np.ndarray] = None,
    ) -> None:
        """
        Add agents to simulation.

        Args:
            positions: Agent positions (N x 2)
            velocities: Agent velocities (N x 2)
            energies: Agent energy levels
            species: Species IDs
        """
        self.agents = []
        for i in range(len(positions)):
            agent = Agent(
                id=i,
                position=positions[i],
                velocity=velocities[i],
                energy=energies[i],
                age=0.0,
                species=species[i] if species is not None else 0,
            )
            self.agents.append(agent)

        # Store in state
        initial_state = {
            "positions": positions.copy(),
            "velocities": velocities.copy(),
            "energies": energies.copy(),
            "species": species if species is not None else np.zeros(len(positions), dtype=int),
            "ages": np.zeros(len(positions)),
        }
        super().initialize(initial_state)

    def step(self, dt: Optional[float] = None) -> bool:
        """Execute one ecosystem step."""
        if dt is None:
            dt = self.config.dt

        positions = self.state.get_state("positions")
        velocities = self.state.get_state("velocities")
        energies = self.state.get_state("energies")
        species = self.state.get_state("species")

        if positions is None:
            return False

        # Update positions
        positions = positions + velocities * dt

        # Wrap around world
        positions = np.mod(positions, self.world_size)

        # Update energies (metabolism)
        energies = energies - 0.1 * dt

        # Random movement
        velocities = velocities + (np.random.randn(*velocities.shape) * 0.1)
        velocities = np.clip(velocities, -1.0, 1.0)

        # Remove dead agents (energy depleted)
        alive_mask = energies > 0
        positions = positions[alive_mask]
        velocities = velocities[alive_mask]
        energies = energies[alive_mask]
        species = species[alive_mask]

        # Reproduction (energy threshold)
        birth_mask = energies > 100
        if np.any(birth_mask):
            birth_indices = np.where(birth_mask)[0]
            for idx in birth_indices:
                # Birth new agent
                new_pos = positions[idx] + np.random.randn(2) * 2.0
                new_vel = velocities[idx] + np.random.randn(2) * 0.1
                new_energy = 50.0
                new_species = species[idx]

                positions = np.vstack([positions, new_pos])
                velocities = np.vstack([velocities, new_vel])
                energies = np.append(energies, new_energy)
                species = np.append(species, new_species)

                # Mother loses energy
                energies[idx] -= 50

        # Update state
        self.state.set_state("positions", positions)
        self.state.set_state("velocities", velocities)
        self.state.set_state("energies", energies)
        self.state.set_state("species", species)

        return super().step(dt)


class EconomicSolver(BaseSolver):
    """Solver for economic simulations."""

    def __init__(self, config: SolverConfig):
        super().__init__(config)
        self.agents: Dict[int, Dict[str, float]] = {}

    def derivative(self, t: float, state: np.ndarray) -> np.ndarray:
        """Compute economic dynamics."""
        return np.zeros_like(state)

    def compute_equilibrium_price(
        self,
        supply: np.ndarray,
        demand: np.ndarray,
    ) -> float:
        """Compute market equilibrium price."""
        # Find intersection of supply and demand curves
        return np.mean(supply + demand)

    def compute_consumer_surplus(
        self,
        demand: np.ndarray,
        price: float,
    ) -> float:
        """Compute consumer surplus."""
        return np.maximum(demand - price, 0).sum()

    def compute_producer_surplus(
        self,
        supply: np.ndarray,
        price: float,
    ) -> float:
        """Compute producer surplus."""
        return np.maximum(price - supply, 0).sum()


class MarketSimulation(SimulationEngine):
    """Supply and demand market simulation."""

    def __init__(self, name: str = "Market Dynamics"):
        config = SimulationConfig(
            simulation_type="economic",
            name=name,
            description="Supply-demand market equilibrium simulation",
            duration=50.0,
        )
        super().__init__(config)

        self.solver = EconomicSolver(SolverConfig(method="RK4"))
        self.set_solver(self.solver)

        # Market parameters
        self.num_goods = 1
        self.price_elasticity = 1.0

    def initialize_market(
        self,
        initial_quantities: np.ndarray,
        initial_prices: np.ndarray,
        demand_params: Dict[str, float],
        supply_params: Dict[str, float],
    ) -> None:
        """
        Initialize market simulation.

        Args:
            initial_quantities: Starting quantities for each good
            initial_prices: Starting prices
            demand_params: Demand elasticity, intercept, etc.
            supply_params: Supply elasticity, intercept, etc.
        """
        initial_state = {
            "quantities": initial_quantities,
            "prices": initial_prices,
            "demand_params": np.array([demand_params.get(f"p{i}", 1.0) for i in range(len(initial_quantities))]),
            "supply_params": np.array([supply_params.get(f"p{i}", 1.0) for i in range(len(initial_quantities))]),
        }
        super().initialize(initial_state)

    def step(self, dt: Optional[float] = None) -> bool:
        """Execute one market step."""
        if dt is None:
            dt = self.config.dt

        quantities = self.state.get_state("quantities")
        prices = self.state.get_state("prices")

        if quantities is None or prices is None:
            return False

        # Compute supply and demand
        demand = prices ** (-self.price_elasticity)
        supply = prices ** (self.price_elasticity / 2)

        # Price adjustment (tâtonnement process)
        price_change = (demand - supply) * 0.1 * dt
        prices = prices + price_change

        # Quantity adjustment
        quantities = quantities + (supply - demand) * 0.05 * dt
        quantities = np.clip(quantities, 0.1, np.inf)

        # Update state
        self.state.set_state("prices", prices)
        self.state.set_state("quantities", quantities)

        return super().step(dt)


class PopulationDynamicsSimulation(SimulationEngine):
    """Logistic growth and Lotka-Volterra predator-prey."""

    def __init__(self, name: str = "Population Dynamics"):
        config = SimulationConfig(
            simulation_type="bio",
            name=name,
            description="Lotka-Volterra predator-prey dynamics",
            duration=100.0,
        )
        super().__init__(config)

        self.solver = BiologicalSolver(SolverConfig(method="RK4"))
        self.set_solver(self.solver)

    def initialize(
        self,
        prey_population: float = 100.0,
        predator_population: float = 10.0,
        prey_birth_rate: float = 0.1,
        predator_death_rate: float = 0.1,
        predation_rate: float = 0.01,
        predator_efficiency: float = 0.1,
    ) -> None:
        """
        Initialize Lotka-Volterra simulation.

        Args:
            prey_population: Initial prey count
            predator_population: Initial predator count
            prey_birth_rate: Prey reproduction rate
            predator_death_rate: Predator natural death rate
            predation_rate: Predation coefficient
            predator_efficiency: Efficiency of predation (food conversion)
        """
        initial_state = {
            "prey": np.array([prey_population]),
            "predators": np.array([predator_population]),
        }
        super().initialize(initial_state)

        self.params = {
            "alpha": prey_birth_rate,
            "beta": predation_rate,
            "gamma": predator_efficiency,
            "delta": predator_death_rate,
        }

    def step(self, dt: Optional[float] = None) -> bool:
        """Execute Lotka-Volterra step."""
        if dt is None:
            dt = self.config.dt

        prey = self.state.get_state("prey")
        predators = self.state.get_state("predators")

        if prey is None or predators is None:
            return False

        p, x = prey[0], predators[0]
        alpha = self.params["alpha"]
        beta = self.params["beta"]
        gamma = self.params["gamma"]
        delta = self.params["delta"]

        # Lotka-Volterra equations
        dp_dt = alpha * p - beta * p * x
        dx_dt = gamma * beta * p * x - delta * x

        # Update using Euler method
        p_new = p + dp_dt * dt
        x_new = x + dx_dt * dt

        # Ensure non-negative
        p_new = max(0.1, p_new)
        x_new = max(0.1, x_new)

        self.state.set_state("prey", np.array([p_new]))
        self.state.set_state("predators", np.array([x_new]))

        return super().step(dt)
