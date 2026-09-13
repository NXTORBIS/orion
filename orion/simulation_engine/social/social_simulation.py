"""
Social Simulation Engine
Complete agent-based social simulation with population dynamics and emergent behavior.
"""

import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import time

try:
    from .agent import Agent, AgentState, AgentRole
    from .population_dynamics import PopulationDynamics, PopulationConfig, DemographicStats
    from .emergent_behavior import EmergentBehavior, EmergentBehaviorMetrics, InformationDiffusion
except ImportError:
    from agent import Agent, AgentState, AgentRole
    from population_dynamics import PopulationDynamics, PopulationConfig, DemographicStats
    from emergent_behavior import EmergentBehavior, EmergentBehaviorMetrics, InformationDiffusion


@dataclass
class SocialSimulationConfig:
    """Configuration for social simulation."""
    num_initial_agents: int = 1000
    simulation_time: float = 1000.0
    dt: float = 1.0
    spatial_domain_size: float = 100.0
    interaction_range: float = 5.0
    enable_visualization: bool = True
    save_snapshots: bool = True
    snapshot_interval: int = 100


class SocialSimulationEnvironment:
    """Manages spatial environment and resources."""

    def __init__(self, size: float = 100.0):
        """
        Initialize environment.

        Args:
            size: Domain size
        """
        self.size = size
        self.resources = np.ones((50, 50))  # Resource grid
        self.resource_regeneration_rate = 0.01

    def get_resource_at(self, x: float, y: float) -> float:
        """Get resource level at position."""
        # Normalize coordinates to grid
        grid_x = int((x + self.size / 2) / self.size * 50)
        grid_y = int((y + self.size / 2) / self.size * 50)

        grid_x = np.clip(grid_x, 0, 49)
        grid_y = np.clip(grid_y, 0, 49)

        return self.resources[grid_x, grid_y]

    def consume_resource(self, x: float, y: float, amount: float) -> float:
        """Consume resource at position."""
        grid_x = int((x + self.size / 2) / self.size * 50)
        grid_y = int((y + self.size / 2) / self.size * 50)

        grid_x = np.clip(grid_x, 0, 49)
        grid_y = np.clip(grid_y, 0, 49)

        consumed = min(self.resources[grid_x, grid_y], amount)
        self.resources[grid_x, grid_y] -= consumed

        return consumed

    def regenerate_resources(self) -> None:
        """Regenerate resources over time."""
        self.resources = np.minimum(
            1.0, self.resources + self.resource_regeneration_rate
        )

    def reset(self) -> None:
        """Reset environment."""
        self.resources = np.ones((50, 50))


class SocialSimulation:
    """
    Complete social simulation engine combining agent dynamics,
    population dynamics, and emergent behavior.
    """

    def __init__(self, config: Optional[SocialSimulationConfig] = None):
        """
        Initialize social simulation.

        Args:
            config: SocialSimulationConfig
        """
        self.config = config or SocialSimulationConfig()

        # Core components
        self.time = 0.0
        self.step_count = 0

        # Population and environment
        self.population = PopulationDynamics(
            initial_population_size=self.config.num_initial_agents
        )
        self.environment = SocialSimulationEnvironment(
            size=self.config.spatial_domain_size
        )

        # Emergent behavior
        self.emergent_behavior = EmergentBehavior(
            max_agents=self.config.num_initial_agents * 2
        )

        # Statistics
        self.statistics = {
            "simulation_time": 0.0,
            "step_times": [],
            "demographic_stats": [],
            "emergent_metrics": [],
        }

        # Interaction tracking
        self.interactions_per_step = 0
        self.successful_interactions = 0

    def step(self) -> Tuple[DemographicStats, EmergentBehaviorMetrics]:
        """
        Execute one simulation step.

        Returns:
            Tuple of (demographic_stats, emergent_metrics)
        """
        step_start = time.time()

        # Update environment
        self.environment.regenerate_resources()

        # Get agents
        agents = self.population.agents
        living_agents = self.population.get_living_agents()

        # Update individual agents
        for agent in living_agents:
            # Consume resources
            resource_at_location = self.environment.get_resource_at(agent.x, agent.y)
            if agent.metabolism.is_hungry():
                consumed = self.environment.consume_resource(
                    agent.x, agent.y, 5.0
                )
                agent.metabolism.gain_energy(consumed)

            # Find neighbors
            neighbors = self._find_neighbors(agent, living_agents)

            # Decide and execute behavior
            behavior = agent.decide_behavior(neighbors, resource_at_location)

            if behavior == "search_food":
                # Move toward resource-rich areas
                self._move_toward_resources(agent)
            elif behavior == "seek_mate":
                # Move toward potential mates
                mates = [
                    n for n in neighbors
                    if n.reproduction_ready and n.age > 20
                ]
                if mates:
                    target = mates[np.random.randint(len(mates))]
                    agent.move(target.x, target.y)
            elif behavior == "cooperate":
                # Interact with neighbors
                for neighbor in neighbors[:3]:  # Limit interactions
                    success, result = agent.interact(neighbor)
                    if success:
                        self.successful_interactions += 1
            elif behavior == "explore":
                agent.move()  # Random movement

            # Update agent
            agent.update(self.config.dt)

        # Process population dynamics
        demo_stats = self.population.update(self.config.dt)

        # Detect emergent behaviors
        emergent_metrics = self.emergent_behavior.update(
            self.population.agents, self.config.dt
        )

        # Time management
        self.time += self.config.dt
        self.step_count += 1

        # Record statistics
        step_time = time.time() - step_start
        self.statistics["step_times"].append(step_time)
        self.statistics["demographic_stats"].append(demo_stats)
        self.statistics["emergent_metrics"].append(emergent_metrics)

        return demo_stats, emergent_metrics

    def _find_neighbors(self, agent: Agent, agents: List[Agent]) -> List[Agent]:
        """Find neighbors within interaction range."""
        neighbors = []
        for other in agents:
            if other.id == agent.id or other.state != AgentState.ACTIVE:
                continue

            distance = np.sqrt((agent.x - other.x)**2 + (agent.y - other.y)**2)
            if distance < agent.social_range:
                neighbors.append(other)

        return neighbors

    def _move_toward_resources(self, agent: Agent) -> None:
        """Move agent toward resource-rich areas."""
        # Sample nearby locations
        search_radius = 10.0
        best_resource = 0.0
        best_x, best_y = agent.x, agent.y

        for _ in range(5):
            angle = np.random.uniform(0, 2 * np.pi)
            dist = np.random.uniform(0, search_radius)
            test_x = agent.x + np.cos(angle) * dist
            test_y = agent.y + np.sin(angle) * dist

            resource = self.environment.get_resource_at(test_x, test_y)
            if resource > best_resource:
                best_resource = resource
                best_x, best_y = test_x, test_y

        agent.move(best_x, best_y)

    def run(self, max_steps: Optional[int] = None, verbose: bool = True) -> Dict[str, Any]:
        """
        Run simulation.

        Args:
            max_steps: Maximum steps to run
            verbose: Print progress

        Returns:
            Simulation results dictionary
        """
        steps = max_steps or int(self.config.simulation_time / self.config.dt)

        if verbose:
            print(f"Starting simulation: {steps} steps")

        for step in range(steps):
            demo_stats, emergent_metrics = self.step()

            if verbose and (step + 1) % max(1, steps // 10) == 0:
                print(
                    f"Step {step+1}/{steps}: "
                    f"Population={demo_stats.living_agents}, "
                    f"Growth={demo_stats.growth_rate:.4f}, "
                    f"Cohesion={emergent_metrics.swarm_cohesion:.3f}"
                )

            # Check for extinction
            if demo_stats.living_agents < 5:
                print(f"Population extinct at step {step}")
                break

        return self._compile_results()

    def _compile_results(self) -> Dict[str, Any]:
        """Compile simulation results."""
        demo_stats = self.statistics["demographic_stats"]
        emergent_metrics = self.statistics["emergent_metrics"]

        if not demo_stats or not emergent_metrics:
            return {"status": "no_data"}

        # Final statistics
        final_demo = demo_stats[-1]
        final_emergent = emergent_metrics[-1]

        # Population trajectory
        populations = [d.living_agents for d in demo_stats]
        births = [d.birth_rate for d in demo_stats]
        deaths = [d.death_rate for d in demo_stats]

        # Emergent patterns
        cohesion_trajectory = [m.swarm_cohesion for m in emergent_metrics]
        intel_trajectory = [m.collective_intelligence_level for m in emergent_metrics]

        # Stability analysis
        stability = self.population.get_stability_analysis()

        results = {
            "status": "success",
            "simulation_time": self.time,
            "total_steps": self.step_count,
            "final_population": final_demo.living_agents,
            "total_births": sum(d.birth_rate for d in demo_stats),
            "total_deaths": sum(d.death_rate for d in demo_stats),
            "average_age": final_demo.average_age,
            "final_cohesion": final_emergent.swarm_cohesion,
            "final_collective_intelligence": final_emergent.collective_intelligence_level,
            "network_components": final_emergent.social_network_components,
            "consensus_level": final_emergent.consensus_level,
            "polarization": final_emergent.group_polarization,
            "population_trajectory": populations,
            "birth_trajectory": births,
            "death_trajectory": deaths,
            "cohesion_trajectory": cohesion_trajectory,
            "intelligence_trajectory": intel_trajectory,
            "stability_analysis": stability,
            "final_demographics": {
                "total": final_demo.total_population,
                "living": final_demo.living_agents,
                "dead": final_demo.dead_agents,
                "average_reputation": final_demo.average_reputation,
                "average_energy": final_demo.average_energy,
                "age_distribution": final_demo.age_distribution,
            },
            "final_emergent_behavior": {
                "dominant_behavior": final_emergent.dominant_behavior,
                "phase_state": self.emergent_behavior.phase_state,
                "network_density": final_emergent.network_density,
                "clustering": final_emergent.network_clustering,
            },
        }

        return results

    def get_agent_data(self) -> List[Dict[str, Any]]:
        """Get current state of all agents."""
        return [agent.get_state_dict() for agent in self.population.agents]

    def get_social_network(self) -> Dict[str, Any]:
        """Get social network representation."""
        return {
            "nodes": list(self.emergent_behavior.social_network.graph.nodes()),
            "edges": list(self.emergent_behavior.social_network.graph.edges()),
            "num_nodes": self.emergent_behavior.social_network.graph.number_of_nodes(),
            "num_edges": self.emergent_behavior.social_network.graph.number_of_edges(),
            "clustering": self.emergent_behavior.social_network.get_clustering_coefficient(),
            "density": self.emergent_behavior.social_network.get_density(),
        }

    def reset(self) -> None:
        """Reset simulation."""
        self.time = 0.0
        self.step_count = 0
        self.population.reset()
        self.environment.reset()
        self.emergent_behavior.reset()
        self.statistics = {
            "simulation_time": 0.0,
            "step_times": [],
            "demographic_stats": [],
            "emergent_metrics": [],
        }
