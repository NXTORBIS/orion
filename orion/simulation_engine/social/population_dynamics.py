"""
Population Dynamics
Birth/death processes, migration patterns, age structure, growth rates, and stability analysis.
"""

import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field

try:
    from .agent import Agent, AgentRole, AgentState
except ImportError:
    from agent import Agent, AgentRole, AgentState


@dataclass
class DemographicStats:
    """Statistics about population demographics."""
    total_population: int = 0
    birth_rate: float = 0.0
    death_rate: float = 0.0
    growth_rate: float = 0.0
    average_age: float = 0.0
    age_distribution: Dict[str, int] = field(default_factory=dict)
    role_distribution: Dict[str, int] = field(default_factory=dict)
    generation_distribution: Dict[int, int] = field(default_factory=dict)
    living_agents: int = 0
    dead_agents: int = 0
    average_energy: float = 0.0
    average_reputation: float = 0.0
    migration_in: int = 0
    migration_out: int = 0


@dataclass
class PopulationConfig:
    """Configuration for population dynamics."""
    birth_rate_base: float = 0.08  # Base birth rate per time step
    death_rate_base: float = 0.005  # Base death rate per time step
    death_rate_age_factor: float = 0.001  # Increase in death rate per year of age
    reproduction_energy_cost: float = 0.3  # Energy cost of reproduction as fraction
    max_population: int = 10000  # Carrying capacity
    migration_rate: float = 0.001  # Migration rate
    environmental_stress: float = 0.0  # Environmental stressor [0, 1]
    resource_availability: float = 1.0  # Resource availability multiplier
    min_reproduction_age: int = 15
    max_reproduction_age: int = 60
    family_size_avg: float = 2.5  # Average children per reproduction event


class PopulationDynamics:
    """
    Manages population-level dynamics including births, deaths, migration, and growth.
    """

    def __init__(
        self,
        config: Optional[PopulationConfig] = None,
        initial_population_size: int = 100,
    ):
        """
        Initialize population dynamics.

        Args:
            config: PopulationConfig
            initial_population_size: Starting population size
        """
        self.config = config or PopulationConfig()
        self.agents: List[Agent] = []
        self.time_step = 0
        self.history: List[DemographicStats] = []

        # Initialize population
        for i in range(initial_population_size):
            age = np.random.uniform(0, 50)
            agent = Agent(
                x=np.random.uniform(-50, 50),
                y=np.random.uniform(-50, 50),
                role=np.random.choice(list(AgentRole)),
                generation=0,
            )
            agent.age = age
            if age > 20:
                agent.metabolism.energy = np.random.uniform(30, 100)
            self.agents.append(agent)

    def add_agent(self, agent: Agent) -> None:
        """Add agent to population."""
        self.agents.append(agent)

    def remove_agent(self, agent_id: int) -> Optional[Agent]:
        """Remove agent from population."""
        for i, agent in enumerate(self.agents):
            if agent.id == agent_id:
                return self.agents.pop(i)
        return None

    def get_agent(self, agent_id: int) -> Optional[Agent]:
        """Get agent by ID."""
        for agent in self.agents:
            if agent.id == agent_id:
                return agent
        return None

    def get_living_agents(self) -> List[Agent]:
        """Get all living agents."""
        return [a for a in self.agents if a.state != AgentState.DEAD]

    def update(self, dt: float = 1.0) -> DemographicStats:
        """
        Update population dynamics for one time step.

        Args:
            dt: Time step

        Returns:
            DemographicStats snapshot
        """
        self.time_step += 1
        living_agents_before = len(self.get_living_agents())

        # Update all agents
        for agent in self.agents:
            if agent.state != AgentState.DEAD:
                agent.update(dt)

        # Process births
        births = self._process_births(dt)

        # Process deaths
        deaths = self._process_deaths(dt)

        # Process migration
        migrations = self._process_migration(dt)

        # Calculate statistics
        stats = self._calculate_statistics(births, deaths, migrations)

        self.history.append(stats)

        return stats

    def _process_births(self, dt: float) -> int:
        """
        Process birth events.

        Args:
            dt: Time step

        Returns:
            Number of births
        """
        births = 0
        living = self.get_living_agents()
        reproduction_candidates = [
            a for a in living
            if a.reproduction_ready
            and self.config.min_reproduction_age <= a.age <= self.config.max_reproduction_age
            and a.metabolism.energy > 60
        ]

        for agent in reproduction_candidates:
            # Adjusted birth probability based on resources and stress
            birth_prob = (
                self.config.birth_rate_base * dt
                * self.config.resource_availability
                * (1.0 - self.config.environmental_stress)
            )

            # Find potential mate
            mate = None
            for other in reproduction_candidates:
                if (
                    other.id != agent.id
                    and other.state == AgentState.ACTIVE
                    and np.random.rand() < agent.cooperativeness
                ):
                    mate = other
                    break

            if np.random.rand() < birth_prob and mate:
                # Create offspring
                child = agent.reproduce(mate)
                if child:
                    self.add_agent(child)
                    births += 1
                    agent.memory.learn_behavior("reproduction")

        return births

    def _process_deaths(self, dt: float) -> int:
        """
        Process death events.

        Args:
            dt: Time step

        Returns:
            Number of deaths
        """
        deaths = 0
        living = self.get_living_agents()

        for agent in living:
            # Death probability increases with age
            age_factor = agent.age * self.config.death_rate_age_factor
            death_prob = (
                (self.config.death_rate_base + age_factor) * dt
                * (1.0 + self.config.environmental_stress)
            )

            # Starvation or energy depletion
            if not agent.metabolism.is_alive():
                death_prob = 1.0

            # Low energy increases death rate
            if agent.metabolism.energy < 10:
                death_prob = min(1.0, death_prob * 3)

            if np.random.rand() < death_prob:
                agent.state = AgentState.DEAD
                deaths += 1

        return deaths

    def _process_migration(self, dt: float) -> Tuple[int, int]:
        """
        Process migration events.

        Args:
            dt: Time step

        Returns:
            Tuple of (migration_in, migration_out)
        """
        migration_in = 0
        migration_out = 0
        living = self.get_living_agents()

        for agent in living:
            # Probability of emigration increases with population stress
            population_stress = len(living) / self.config.max_population
            emigration_prob = self.config.migration_rate * population_stress * dt

            if np.random.rand() < emigration_prob:
                # Agent leaves (conceptually)
                migration_out += 1
                agent.status *= 0.9  # Reduce status

            # Immigration
            immigration_prob = self.config.migration_rate * (1 - population_stress) * dt * 0.5
            if np.random.rand() < immigration_prob and len(self.agents) < self.config.max_population:
                # New agent arrives
                migrant = Agent(
                    x=np.random.uniform(-50, 50),
                    y=np.random.uniform(-50, 50),
                    role=np.random.choice(list(AgentRole)),
                    generation=np.random.randint(0, 3),
                )
                migrant.age = np.random.uniform(15, 40)
                self.add_agent(migrant)
                migration_in += 1

        return migration_in, migration_out

    def _calculate_statistics(
        self, births: int, deaths: int, migrations: Tuple[int, int]
    ) -> DemographicStats:
        """Calculate demographic statistics."""
        stats = DemographicStats()

        living = self.get_living_agents()
        all_agents = self.agents

        stats.total_population = len(all_agents)
        stats.living_agents = len(living)
        stats.dead_agents = stats.total_population - stats.living_agents
        stats.migration_in, stats.migration_out = migrations

        # Birth and death rates
        if len(living) > 0:
            stats.birth_rate = births / len(living) if len(living) > 0 else 0
            stats.death_rate = deaths / len(living) if len(living) > 0 else 0
            stats.growth_rate = stats.birth_rate - stats.death_rate

            # Age statistics
            ages = [a.age for a in living]
            stats.average_age = np.mean(ages) if ages else 0
            stats.average_energy = np.mean([a.metabolism.energy for a in living])
            stats.average_reputation = np.mean([a.reputation for a in living])

            # Age distribution
            age_groups = {
                "0-10": sum(1 for a in living if 0 <= a.age < 10),
                "10-20": sum(1 for a in living if 10 <= a.age < 20),
                "20-30": sum(1 for a in living if 20 <= a.age < 30),
                "30-40": sum(1 for a in living if 30 <= a.age < 40),
                "40-50": sum(1 for a in living if 40 <= a.age < 50),
                "50+": sum(1 for a in living if a.age >= 50),
            }
            stats.age_distribution = age_groups

            # Role distribution
            for role in AgentRole:
                stats.role_distribution[role.name] = sum(1 for a in living if a.role == role)

            # Generation distribution
            for agent in living:
                gen = agent.generation
                if gen not in stats.generation_distribution:
                    stats.generation_distribution[gen] = 0
                stats.generation_distribution[gen] += 1

        return stats

    def get_statistics(self) -> DemographicStats:
        """Get current demographic statistics."""
        if self.history:
            return self.history[-1]
        return DemographicStats()

    def get_history(self, max_steps: Optional[int] = None) -> List[DemographicStats]:
        """Get history of demographic statistics."""
        if max_steps:
            return self.history[-max_steps:]
        return self.history.copy()

    def get_stability_analysis(self) -> Dict[str, Any]:
        """
        Analyze population stability.

        Returns:
            Dictionary with stability metrics
        """
        if len(self.history) < 10:
            return {"stability": "insufficient_data"}

        recent_stats = self.history[-100:] if len(self.history) > 100 else self.history

        growth_rates = [s.growth_rate for s in recent_stats]
        populations = [s.living_agents for s in recent_stats]

        # Stability metrics
        growth_volatility = np.std(growth_rates) if growth_rates else 0
        population_variance = np.var(populations) if populations else 0
        avg_growth = np.mean(growth_rates) if growth_rates else 0

        # Age structure entropy (indicator of population health)
        age_counts = []
        if recent_stats[-1].age_distribution:
            age_counts = list(recent_stats[-1].age_distribution.values())
        age_entropy = -sum(
            (c / sum(age_counts)) * np.log(c / sum(age_counts) + 1e-10)
            for c in age_counts if c > 0
        ) if age_counts else 0

        # Determine stability state
        if growth_volatility < 0.002 and population_variance < 100:
            stability = "stable"
        elif growth_volatility < 0.01:
            stability = "oscillating"
        else:
            stability = "chaotic"

        # Check for extinction risk
        extinction_risk = "low"
        if populations[-1] < 50:
            extinction_risk = "high"
        elif populations[-1] < 100:
            extinction_risk = "medium"

        return {
            "stability": stability,
            "growth_volatility": growth_volatility,
            "population_variance": population_variance,
            "average_growth_rate": avg_growth,
            "age_structure_entropy": age_entropy,
            "extinction_risk": extinction_risk,
            "current_population": populations[-1] if populations else 0,
            "max_population": max(populations) if populations else 0,
            "min_population": min(populations) if populations else 0,
        }

    def reset(self) -> None:
        """Reset population dynamics."""
        self.agents.clear()
        self.time_step = 0
        self.history.clear()
