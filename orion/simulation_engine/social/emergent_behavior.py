"""
Emergent Behavior Detection
Swarm dynamics, collective intelligence, social networks, information diffusion, phase transitions.
"""

import numpy as np
import networkx as nx
from typing import Dict, List, Tuple, Optional, Any, Set
from dataclasses import dataclass, field
from collections import defaultdict

try:
    from .agent import Agent, AgentState
except ImportError:
    from agent import Agent, AgentState


@dataclass
class EmergentBehaviorMetrics:
    """Metrics for emergent behavior detection."""
    swarm_cohesion: float = 0.0
    collective_intelligence_level: float = 0.0
    network_clustering: float = 0.0
    network_density: float = 0.0
    information_diffusion_speed: float = 0.0
    phase_transition_indicator: float = 0.0
    dominant_behavior: str = "none"
    behavior_distribution: Dict[str, int] = field(default_factory=dict)
    social_network_components: int = 1
    average_connection_strength: float = 0.0
    group_polarization: float = 0.0
    consensus_level: float = 0.0


class SocialNetwork:
    """Manages social network structure and dynamics."""

    def __init__(self):
        """Initialize social network."""
        self.graph = nx.Graph()
        self.relationships: Dict[int, Dict[int, float]] = {}
        self.interaction_counts: Dict[Tuple[int, int], int] = {}

    def add_agent(self, agent: Agent) -> None:
        """Add agent to network."""
        if agent.id not in self.graph:
            self.graph.add_node(agent.id, agent=agent)
            self.relationships[agent.id] = {}

    def add_connection(self, agent_id1: int, agent_id2: int, strength: float = 0.5) -> None:
        """Add connection between agents."""
        if not self.graph.has_edge(agent_id1, agent_id2):
            self.graph.add_edge(agent_id1, agent_id2, weight=strength)
            self.relationships[agent_id1][agent_id2] = strength
            if agent_id2 not in self.relationships:
                self.relationships[agent_id2] = {}
            self.relationships[agent_id2][agent_id1] = strength
        else:
            # Update weight
            current_weight = self.graph[agent_id1][agent_id2]["weight"]
            new_weight = (current_weight + strength) / 2
            self.graph[agent_id1][agent_id2]["weight"] = new_weight
            self.relationships[agent_id1][agent_id2] = new_weight
            self.relationships[agent_id2][agent_id1] = new_weight

    def get_clustering_coefficient(self) -> float:
        """Calculate network clustering coefficient."""
        try:
            return nx.average_clustering(self.graph)
        except:
            return 0.0

    def get_density(self) -> float:
        """Calculate network density."""
        if len(self.graph) < 2:
            return 0.0
        return nx.density(self.graph)

    def get_connected_components(self) -> int:
        """Get number of connected components."""
        return nx.number_connected_components(self.graph)

    def get_average_path_length(self) -> float:
        """Calculate average shortest path length."""
        try:
            if self.graph.number_of_nodes() < 2:
                return 0.0

            if nx.is_connected(self.graph):
                return nx.average_shortest_path_length(self.graph)
            else:
                # For disconnected graphs, average over connected components
                lengths = []
                for component in nx.connected_components(self.graph):
                    subgraph = self.graph.subgraph(component)
                    if len(subgraph) > 1:
                        lengths.append(nx.average_shortest_path_length(subgraph))
                return np.mean(lengths) if lengths else 0.0
        except:
            return 0.0

    def get_most_connected_nodes(self, top_n: int = 5) -> List[Tuple[int, int]]:
        """Get most connected agents."""
        degrees = [(node, self.graph.degree(node)) for node in self.graph.nodes()]
        return sorted(degrees, key=lambda x: x[1], reverse=True)[:top_n]

    def reset(self) -> None:
        """Reset social network."""
        self.graph.clear()
        self.relationships.clear()
        self.interaction_counts.clear()


class InformationDiffusion:
    """Manages information diffusion through population."""

    def __init__(self):
        """Initialize information diffusion."""
        self.ideas: Dict[str, Set[int]] = {}  # idea_name -> set of agent_ids
        self.idea_timestamps: Dict[str, float] = {}
        self.diffusion_rates: Dict[str, float] = {}

    def introduce_idea(self, idea_name: str, agent_id: int, timestamp: float = 0.0) -> None:
        """Introduce new idea to population."""
        if idea_name not in self.ideas:
            self.ideas[idea_name] = set()
            self.idea_timestamps[idea_name] = timestamp
            self.diffusion_rates[idea_name] = 0.0

        self.ideas[idea_name].add(agent_id)

    def get_adoption_rate(self, idea_name: str, total_population: int) -> float:
        """Get adoption rate of an idea."""
        if idea_name not in self.ideas:
            return 0.0
        return len(self.ideas[idea_name]) / total_population if total_population > 0 else 0.0

    def get_diffusion_speed(self, idea_name: str, current_time: float) -> float:
        """Estimate diffusion speed."""
        if idea_name not in self.ideas:
            return 0.0

        age = current_time - self.idea_timestamps.get(idea_name, 0)
        if age <= 0:
            return 0.0

        adoption = len(self.ideas[idea_name])
        return adoption / (age + 1)

    def process_diffusion(
        self,
        agents: List[Agent],
        social_network: SocialNetwork,
        current_time: float,
    ) -> None:
        """Process information diffusion based on social connections."""
        for idea, adopters in self.ideas.items():
            # Calculate diffusion probability
            adoption_rate = len(adopters) / len(agents) if agents else 0
            diffusion_prob = 0.05 * adoption_rate * (1 - adoption_rate)

            # Spread to connected agents
            new_adopters = set()
            for agent_id in adopters:
                if agent_id in social_network.relationships:
                    neighbors = social_network.relationships[agent_id]
                    for neighbor_id, strength in neighbors.items():
                        if neighbor_id not in adopters:
                            spread_prob = diffusion_prob * strength
                            if np.random.rand() < spread_prob:
                                new_adopters.add(neighbor_id)

            adopters.update(new_adopters)

    def reset(self) -> None:
        """Reset information diffusion."""
        self.ideas.clear()
        self.idea_timestamps.clear()
        self.diffusion_rates.clear()


class EmergentBehavior:
    """
    Detects and analyzes emergent behaviors in the population.
    """

    def __init__(self, max_agents: int = 10000):
        """
        Initialize emergent behavior detector.

        Args:
            max_agents: Maximum agents to handle
        """
        self.max_agents = max_agents
        self.social_network = SocialNetwork()
        self.information_diffusion = InformationDiffusion()
        self.behavior_history: List[EmergentBehaviorMetrics] = []
        self.phase_state = "normal"

    def update(self, agents: List[Agent], dt: float = 1.0) -> EmergentBehaviorMetrics:
        """
        Update emergent behavior analysis.

        Args:
            agents: List of agents
            dt: Time step

        Returns:
            EmergentBehaviorMetrics
        """
        living_agents = [a for a in agents if a.state == AgentState.ACTIVE]

        # Update social network
        self._update_network(living_agents)

        # Detect swarm cohesion
        swarm_cohesion = self._calculate_swarm_cohesion(living_agents)

        # Detect collective intelligence
        collective_intel = self._calculate_collective_intelligence(living_agents)

        # Calculate network metrics
        clustering = self.social_network.get_clustering_coefficient()
        density = self.social_network.get_density()
        components = self.social_network.get_connected_components()
        avg_connection = self._calculate_average_connection_strength()

        # Information diffusion
        self.information_diffusion.process_diffusion(living_agents, self.social_network, 0)
        diffusion_speed = self._calculate_diffusion_speed()

        # Detect phase transitions
        phase_indicator = self._detect_phase_transition(living_agents)

        # Behavior analysis
        dominant_behavior, behavior_dist = self._analyze_behaviors(living_agents)

        # Calculate polarization and consensus
        polarization = self._calculate_polarization(living_agents)
        consensus = self._calculate_consensus(living_agents)

        metrics = EmergentBehaviorMetrics(
            swarm_cohesion=swarm_cohesion,
            collective_intelligence_level=collective_intel,
            network_clustering=clustering,
            network_density=density,
            information_diffusion_speed=diffusion_speed,
            phase_transition_indicator=phase_indicator,
            dominant_behavior=dominant_behavior,
            behavior_distribution=behavior_dist,
            social_network_components=components,
            average_connection_strength=avg_connection,
            group_polarization=polarization,
            consensus_level=consensus,
        )

        self.behavior_history.append(metrics)
        self._update_phase_state(phase_indicator)

        return metrics

    def _update_network(self, agents: List[Agent]) -> None:
        """Update social network based on agent relationships."""
        self.social_network.reset()

        for agent in agents:
            self.social_network.add_agent(agent)

        # Add connections from relationships
        for agent in agents:
            for other_id, strength in agent.relationships.items():
                if other_id < agent.id:  # Avoid duplicates
                    self.social_network.add_connection(agent.id, other_id, strength)

    def _calculate_swarm_cohesion(self, agents: List[Agent]) -> float:
        """
        Calculate swarm cohesion based on spatial proximity and coordination.

        Args:
            agents: List of agents

        Returns:
            Cohesion score [0, 1]
        """
        if len(agents) < 2:
            return 0.0

        # Calculate center of mass
        positions = np.array([[a.x, a.y] for a in agents])
        center = np.mean(positions, axis=0)

        # Calculate average distance from center
        distances = np.linalg.norm(positions - center, axis=1)
        avg_distance = np.mean(distances)
        max_distance = np.max(distances)

        if max_distance == 0:
            return 1.0

        cohesion = 1.0 - (avg_distance / (max_distance + 1e-10))
        return np.clip(cohesion, 0.0, 1.0)

    def _calculate_collective_intelligence(self, agents: List[Agent]) -> float:
        """
        Calculate collective intelligence based on cooperation and diversity.

        Args:
            agents: List of agents

        Returns:
            Collective intelligence score [0, 1]
        """
        if len(agents) == 0:
            return 0.0

        # Average cooperativeness
        avg_cooperativeness = np.mean([a.cooperativeness for a in agents])

        # Intelligence diversity
        intelligences = np.array([a.intelligence for a in agents])
        diversity = np.std(intelligences) / (np.mean(intelligences) + 1e-10)

        # Network diversity
        roles = set(a.role for a in agents)
        role_diversity = len(roles) / len([r for r in roles])

        collective_intel = (
            avg_cooperativeness * 0.5
            + min(diversity, 1.0) * 0.3
            + min(role_diversity, 1.0) * 0.2
        )

        return np.clip(collective_intel, 0.0, 1.0)

    def _calculate_average_connection_strength(self) -> float:
        """Calculate average strength of connections in network."""
        if self.social_network.graph.number_of_edges() == 0:
            return 0.0

        weights = [
            data["weight"]
            for _, _, data in self.social_network.graph.edges(data=True)
        ]
        return np.mean(weights) if weights else 0.0

    def _calculate_diffusion_speed(self) -> float:
        """Calculate average diffusion speed of ideas."""
        if not self.information_diffusion.ideas:
            return 0.0

        speeds = []
        for idea in self.information_diffusion.ideas:
            speed = len(self.information_diffusion.ideas[idea])
            speeds.append(speed)

        return np.mean(speeds) / 100.0 if speeds else 0.0

    def _detect_phase_transition(self, agents: List[Agent]) -> float:
        """
        Detect phase transitions in system behavior.

        Args:
            agents: List of agents

        Returns:
            Phase transition indicator [0, 1]
        """
        if len(self.behavior_history) < 5:
            return 0.0

        recent_metrics = self.behavior_history[-5:]

        # Calculate changes in key metrics
        cohesion_change = (
            recent_metrics[-1].swarm_cohesion - recent_metrics[0].swarm_cohesion
        )
        intel_change = (
            recent_metrics[-1].collective_intelligence_level
            - recent_metrics[0].collective_intelligence_level
        )
        clustering_change = (
            recent_metrics[-1].network_clustering - recent_metrics[0].network_clustering
        )

        # Phase transition occurs when metrics change significantly
        transition_indicator = abs(cohesion_change) + abs(intel_change) + abs(clustering_change)

        return np.clip(transition_indicator, 0.0, 1.0)

    def _analyze_behaviors(self, agents: List[Agent]) -> Tuple[str, Dict[str, int]]:
        """
        Analyze dominant behaviors in population.

        Args:
            agents: List of agents

        Returns:
            Tuple of (dominant_behavior, behavior_distribution)
        """
        behaviors = [a.current_behavior for a in agents]
        behavior_counts = {}

        for behavior in behaviors:
            behavior_counts[behavior] = behavior_counts.get(behavior, 0) + 1

        if not behavior_counts:
            return "none", {}

        dominant = max(behavior_counts, key=behavior_counts.get)
        return dominant, behavior_counts

    def _calculate_polarization(self, agents: List[Agent]) -> float:
        """
        Calculate group polarization based on opinion distribution.

        Args:
            agents: List of agents

        Returns:
            Polarization score [0, 1]
        """
        if len(agents) < 2:
            return 0.0

        # Use reputation as proxy for group opinion
        reputations = np.array([a.reputation for a in agents])
        mean_rep = np.mean(reputations)

        # Calculate bimodality (tendency to form two opposing groups)
        std_rep = np.std(reputations)
        if std_rep == 0:
            return 0.0

        # Normalize to [0, 1]
        polarization = min(std_rep, 0.5) / 0.5

        return np.clip(polarization, 0.0, 1.0)

    def _calculate_consensus(self, agents: List[Agent]) -> float:
        """
        Calculate level of consensus in group.

        Args:
            agents: List of agents

        Returns:
            Consensus score [0, 1]
        """
        if len(agents) < 2:
            return 1.0

        # High consensus when agents have similar behaviors
        behaviors = [a.current_behavior for a in agents]
        behavior_set = set(behaviors)

        consensus = 1.0 - (len(behavior_set) / len(agents))
        return np.clip(consensus, 0.0, 1.0)

    def _update_phase_state(self, phase_indicator: float) -> None:
        """Update phase state based on transition indicator."""
        if phase_indicator > 0.3:
            if self.phase_state == "normal":
                self.phase_state = "transitioning"
            elif self.phase_state == "transitioning" and phase_indicator > 0.5:
                self.phase_state = "transformed"
        else:
            self.phase_state = "normal"

    def get_history(self, max_steps: Optional[int] = None) -> List[EmergentBehaviorMetrics]:
        """Get history of emergent behavior metrics."""
        if max_steps:
            return self.behavior_history[-max_steps:]
        return self.behavior_history.copy()

    def reset(self) -> None:
        """Reset emergent behavior detector."""
        self.social_network.reset()
        self.information_diffusion.reset()
        self.behavior_history.clear()
        self.phase_state = "normal"
