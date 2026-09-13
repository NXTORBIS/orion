"""
Agent System
Individual agent representation with state, behaviors, learning, and interaction protocols.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Callable
from enum import Enum
import random


class AgentState(Enum):
    """Enumeration of possible agent states."""
    ACTIVE = 1
    INACTIVE = 2
    DEAD = 3
    TRANSITIONING = 4


class AgentRole(Enum):
    """Agent roles in society."""
    WORKER = 1
    LEADER = 2
    INNOVATOR = 3
    CONSUMER = 4
    PRODUCER = 5


@dataclass
class AgentMemory:
    """Agent's learning and memory system."""
    experiences: List[Dict[str, Any]] = field(default_factory=list)
    learned_behaviors: List[str] = field(default_factory=list)
    interaction_history: Dict[int, int] = field(default_factory=dict)  # agent_id -> interaction_count
    success_rate: float = 0.5
    adaptation_level: float = 0.0
    max_memory_size: int = 100

    def add_experience(self, experience: Dict[str, Any]) -> None:
        """Add experience to memory."""
        self.experiences.append(experience)
        if len(self.experiences) > self.max_memory_size:
            self.experiences.pop(0)

    def update_success_rate(self, success: bool, weight: float = 0.1) -> None:
        """Update success rate with exponential moving average."""
        self.success_rate = (1 - weight) * self.success_rate + weight * float(success)

    def learn_behavior(self, behavior: str) -> None:
        """Learn a new behavior."""
        if behavior not in self.learned_behaviors:
            self.learned_behaviors.append(behavior)
            self.adaptation_level += 0.05

    def record_interaction(self, agent_id: int) -> None:
        """Record interaction with another agent."""
        if agent_id not in self.interaction_history:
            self.interaction_history[agent_id] = 0
        self.interaction_history[agent_id] += 1


@dataclass
class AgentMetabolism:
    """Agent metabolic properties and energy dynamics."""
    energy: float = 100.0
    energy_consumption_rate: float = 0.1
    max_energy: float = 100.0
    metabolism_efficiency: float = 0.95
    hunger_threshold: float = 30.0

    def consume_energy(self, amount: float) -> float:
        """Consume energy, return actual amount consumed."""
        consumed = min(self.energy, amount)
        self.energy = max(0, self.energy - amount)
        return consumed

    def gain_energy(self, amount: float) -> float:
        """Gain energy, return actual amount gained."""
        gained = min(self.max_energy - self.energy, amount * self.metabolism_efficiency)
        self.energy = min(self.max_energy, self.energy + gained)
        return gained

    def is_hungry(self) -> bool:
        """Check if agent is hungry."""
        return self.energy < self.hunger_threshold

    def is_alive(self) -> bool:
        """Check if agent is still alive."""
        return self.energy > 0


class Agent:
    """
    Individual agent with complete state representation, behaviors, and learning.
    """

    _id_counter = 0

    def __init__(
        self,
        x: float = 0.0,
        y: float = 0.0,
        role: AgentRole = AgentRole.WORKER,
        generation: int = 0,
        personality: Optional[Dict[str, float]] = None,
    ):
        """
        Initialize an agent.

        Args:
            x: Initial x position
            y: Initial y position
            role: Agent role in society
            generation: Generation number
            personality: Dict with personality traits
        """
        Agent._id_counter += 1
        self.id = Agent._id_counter

        # Position and movement
        self.x = x
        self.y = y
        self.vx = 0.0
        self.vy = 0.0
        self.speed = np.random.uniform(0.5, 2.0)

        # Life cycle
        self.age = 0
        self.generation = generation
        self.state = AgentState.ACTIVE
        self.reproduction_ready = False
        self.reproduction_cooldown = 0

        # Social properties
        self.role = role
        self.status = np.random.uniform(0.0, 1.0)  # Social status
        self.reputation = 0.5  # Reputation in community [0, 1]
        self.social_range = 5.0  # Distance to perceive other agents

        # Personality and traits
        self.personality = personality or self._generate_personality()
        self.intelligence = np.random.uniform(0.3, 1.0)
        self.cooperativeness = np.random.uniform(0.3, 1.0)
        self.risk_tolerance = np.random.uniform(0.3, 1.0)

        # Memory and learning
        self.memory = AgentMemory()
        self.metabolism = AgentMetabolism()

        # Behavioral state
        self.current_behavior = "idle"
        self.behavior_duration = 0
        self.goals: List[str] = ["survive", "reproduce", "socialize"]

        # Social connections
        self.relationships: Dict[int, float] = {}  # agent_id -> relationship_strength

    def _generate_personality(self) -> Dict[str, float]:
        """Generate random personality traits."""
        return {
            "aggressiveness": np.random.uniform(0.0, 1.0),
            "friendliness": np.random.uniform(0.0, 1.0),
            "curiosity": np.random.uniform(0.0, 1.0),
            "conservatism": np.random.uniform(0.0, 1.0),
            "loyalty": np.random.uniform(0.0, 1.0),
        }

    def update(self, dt: float = 1.0) -> None:
        """
        Update agent state for one time step.

        Args:
            dt: Time step
        """
        # Age and metabolism
        self.age += dt
        self.metabolism.consume_energy(self.metabolism.energy_consumption_rate * dt)

        # Update position
        self.x += self.vx * dt
        self.y += self.vy * dt

        # Update reproduction
        if self.reproduction_cooldown > 0:
            self.reproduction_cooldown -= dt

        if self.age > 10 and self.age < 60 and self.metabolism.energy > 50:
            self.reproduction_ready = True
        else:
            self.reproduction_ready = False

        # Update behavior
        if self.behavior_duration > 0:
            self.behavior_duration -= dt

        # Check vitality
        if not self.metabolism.is_alive():
            self.state = AgentState.DEAD

        # Stress and adaptation
        self.memory.adaptation_level = max(0.0, self.memory.adaptation_level - 0.001 * dt)

    def decide_behavior(self, neighbors: List['Agent'], resources: float) -> str:
        """
        Decide next behavior based on state and environment.

        Args:
            neighbors: List of nearby agents
            resources: Available environmental resources

        Returns:
            New behavior string
        """
        # Priority: survival > reproduction > social
        if self.metabolism.is_hungry():
            self.current_behavior = "search_food"
            return "search_food"

        if self.reproduction_ready and self.age > 25:
            self.current_behavior = "seek_mate"
            return "seek_mate"

        if len(neighbors) > 0 and self.cooperativeness > 0.5:
            if np.random.rand() < self.cooperativeness:
                self.current_behavior = "cooperate"
                return "cooperate"
            else:
                self.current_behavior = "compete"
                return "compete"

        self.current_behavior = "explore"
        return "explore"

    def interact(self, other: 'Agent') -> Tuple[bool, Dict[str, Any]]:
        """
        Interact with another agent.

        Args:
            other: Other agent to interact with

        Returns:
            Tuple of (success, result_dict)
        """
        if self.state != AgentState.ACTIVE or other.state != AgentState.ACTIVE:
            return False, {}

        distance = np.sqrt((self.x - other.x)**2 + (self.y - other.y)**2)
        if distance > self.social_range:
            return False, {}

        # Record interaction
        self.memory.record_interaction(other.id)
        other.memory.record_interaction(self.id)

        # Determine interaction outcome based on personalities
        compatibility = self._calculate_compatibility(other)
        interaction_type = self._determine_interaction_type(other, compatibility)

        result = {
            "type": interaction_type,
            "compatibility": compatibility,
            "energy_exchange": 0.0,
            "information_shared": False,
        }

        # Execute interaction
        if interaction_type == "cooperate":
            result["energy_exchange"] = 5.0
            self.metabolism.gain_energy(result["energy_exchange"])
            other.metabolism.consume_energy(result["energy_exchange"] * 0.5)
            self.reputation += 0.02
            other.reputation += 0.02
            result["information_shared"] = True
            self.memory.learn_behavior("cooperation")

        elif interaction_type == "compete":
            if self.intelligence > other.intelligence:
                self.metabolism.gain_energy(3.0)
                other.metabolism.consume_energy(5.0)
                self.reputation += 0.01
            else:
                other.metabolism.gain_energy(3.0)
                self.metabolism.consume_energy(5.0)
                other.reputation += 0.01
            self.memory.learn_behavior("competition")

        elif interaction_type == "mate":
            if self.reproduction_ready and other.reproduction_ready:
                self.reproduction_cooldown = 10.0
                other.reproduction_cooldown = 10.0
                result["reproduction"] = True
                self.memory.learn_behavior("reproduction")

        # Update relationship
        if other.id not in self.relationships:
            self.relationships[other.id] = compatibility
        else:
            self.relationships[other.id] = (self.relationships[other.id] + compatibility) / 2

        return True, result

    def _calculate_compatibility(self, other: 'Agent') -> float:
        """Calculate compatibility with another agent."""
        personality_diff = sum(
            abs(self.personality.get(k, 0) - other.personality.get(k, 0))
            for k in self.personality
        ) / len(self.personality)

        compatibility = 1.0 - personality_diff
        compatibility *= (1.0 + self.cooperativeness + other.cooperativeness) / 3
        return np.clip(compatibility, 0.0, 1.0)

    def _determine_interaction_type(self, other: 'Agent', compatibility: float) -> str:
        """Determine type of interaction."""
        if self.reproduction_ready and other.reproduction_ready and compatibility > 0.6:
            return "mate"
        elif compatibility > 0.6 and self.cooperativeness > 0.5:
            return "cooperate"
        elif self.risk_tolerance > 0.6:
            return "compete"
        else:
            return "neutral"

    def reproduce(self, partner: Optional['Agent'] = None) -> Optional['Agent']:
        """
        Reproduce to create offspring.

        Args:
            partner: Partner agent for reproduction

        Returns:
            New agent or None if unable to reproduce
        """
        if not self.reproduction_ready:
            return None

        if self.metabolism.energy < 50:
            return None

        # Create offspring
        child_x = (self.x + (partner.x if partner else 0)) / (2 if partner else 1)
        child_y = (self.y + (partner.y if partner else 0)) / (2 if partner else 1)

        # Mutate personality traits
        child_personality = self.personality.copy()
        for key in child_personality:
            mutation = np.random.normal(0, 0.1)
            child_personality[key] = np.clip(child_personality[key] + mutation, 0, 1)

        if partner:
            # Mix personality from both parents
            for key in child_personality:
                partner_trait = partner.personality.get(key, 0.5)
                child_personality[key] = (child_personality[key] + partner_trait) / 2
                mutation = np.random.normal(0, 0.05)
                child_personality[key] = np.clip(child_personality[key] + mutation, 0, 1)

        # Create child agent
        child = Agent(
            x=child_x + np.random.normal(0, 1),
            y=child_y + np.random.normal(0, 1),
            role=self.role,
            generation=self.generation + 1,
            personality=child_personality,
        )

        # Energy cost
        self.metabolism.energy *= 0.7
        if partner:
            partner.metabolism.energy *= 0.7

        return child

    def move(self, target_x: Optional[float] = None, target_y: Optional[float] = None) -> None:
        """
        Move agent towards target or random direction.

        Args:
            target_x: Target x coordinate
            target_y: Target y coordinate
        """
        if target_x is not None and target_y is not None:
            # Move towards target
            dx = target_x - self.x
            dy = target_y - self.y
            distance = np.sqrt(dx**2 + dy**2)

            if distance > 0.1:
                self.vx = (dx / distance) * self.speed
                self.vy = (dy / distance) * self.speed
            else:
                self.vx = 0
                self.vy = 0
        else:
            # Random movement
            if np.random.rand() < 0.1:  # Change direction occasionally
                angle = np.random.uniform(0, 2 * np.pi)
                self.vx = np.cos(angle) * self.speed
                self.vy = np.sin(angle) * self.speed

    def get_state_dict(self) -> Dict[str, Any]:
        """Get complete agent state as dictionary."""
        return {
            "id": self.id,
            "x": self.x,
            "y": self.y,
            "age": self.age,
            "energy": self.metabolism.energy,
            "state": self.state.name,
            "role": self.role.name,
            "reputation": self.reputation,
            "intelligence": self.intelligence,
            "cooperativeness": self.cooperativeness,
            "current_behavior": self.current_behavior,
            "relationships_count": len(self.relationships),
        }

    def __repr__(self) -> str:
        return f"Agent(id={self.id}, age={self.age:.1f}, energy={self.metabolism.energy:.1f}, state={self.state.name})"
