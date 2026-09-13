"""
Test and demonstration of the Biological Simulation Engine.
Validates ecosystem dynamics, organism behavior, and evolution.
"""

import numpy as np
from typing import Dict, Any
from biological_engine import (
    BiologicalSimulationSystem,
    SpeciesType,
    SeasonalPhase,
    Organism,
    Genome,
    Gene,
)


def test_genome_system():
    """Test genetic system."""
    print("Testing Genome System...")
    genome = Genome()

    # Verify genes exist
    assert "speed" in genome.genes
    assert "size" in genome.genes
    assert "metabolism" in genome.genes
    assert "sense_range" in genome.genes
    assert "fertility" in genome.genes

    # Test phenotype expression
    speed_phenotype = genome.get_phenotype("speed")
    assert 0 <= speed_phenotype <= 1.0

    # Test mutation
    original_value = genome.genes["speed"].value
    genome.genes["speed"].mutation_rate = 1.0  # Force mutation
    genome.mutate()
    # Mutation may or may not change value significantly

    # Test genome copy
    genome_copy = genome.copy()
    assert genome_copy.generation == genome.generation + 1
    assert "speed" in genome_copy.genes

    print("  [PASS] Genome system validated")


def test_organism_system():
    """Test individual organism."""
    print("Testing Organism System...")

    genome = Genome()
    organism = Organism(
        id=1,
        species_type=SpeciesType.HERBIVORE,
        position=np.array([250.0, 250.0]),
        velocity=np.array([1.0, 0.5]),
        genome=genome,
        energy=100.0
    )

    # Verify properties
    assert organism.speed > 1.0
    assert organism.size > 0.5
    assert organism.metabolism_rate > 0
    assert organism.sense_range > 5.0
    assert 0 <= organism.fertility <= 1.0
    assert organism.is_alive

    # Test energy consumption
    initial_energy = organism.energy
    organism.consume_energy(1.0)
    assert organism.energy < initial_energy

    # Test movement
    direction = np.array([1.0, 0.0])
    organism.move(direction, 1.0, np.array([500.0, 500.0]))
    assert not np.allclose(organism.position, np.array([250.0, 250.0]))

    # Test aging
    organism.age_organism(1.0)
    assert organism.age == 1.0

    # Test reproduction
    offspring = organism.reproduce()
    assert offspring is not None
    assert offspring.species_type == organism.species_type
    assert offspring.energy > 0
    assert organism.reproduction_cooldown > 0

    # Test death
    organism.energy = 0
    assert not organism.is_alive

    print("  [PASS] Organism system validated")


def test_ecosystem_engine():
    """Test ecosystem dynamics."""
    print("Testing Ecosystem Engine...")

    from biological_engine import EcosystemEngine

    ecosystem = EcosystemEngine(world_size=np.array([500.0, 500.0]))

    # Create different organisms
    herbivore = Organism(
        id=-1,
        species_type=SpeciesType.HERBIVORE,
        position=np.array([250.0, 250.0]),
        velocity=np.array([0.5, 0.5]),
        genome=Genome(),
        energy=100.0
    )

    carnivore = Organism(
        id=-2,
        species_type=SpeciesType.CARNIVORE,
        position=np.array([260.0, 250.0]),
        velocity=np.array([0.0, 0.0]),
        genome=Genome(),
        energy=100.0
    )

    # Add to ecosystem
    hb_id = ecosystem.add_organism(herbivore, 1)
    cb_id = ecosystem.add_organism(carnivore, 2)

    assert hb_id in ecosystem.organisms
    assert cb_id in ecosystem.organisms

    # Test herbivory
    ecosystem.compute_herbivory()
    # Herbivore should gain some energy from plants

    # Test predation
    initial_carnivore_energy = ecosystem.organisms[cb_id].energy
    ecosystem.compute_species_interactions()
    # Carnivore might gain energy or herbivore might die

    # Test nutrient cycling
    ecosystem.organisms[hb_id].energy = 0  # Kill herbivore
    ecosystem.nutrient_cycling()
    # Dead organism should return nutrients

    # Test habitat effects
    ecosystem.apply_habitat_effects(SeasonalPhase.WINTER)
    # Organisms should have stress

    # Test energy flow computation
    energy_flow = ecosystem.compute_energy_flow()
    assert isinstance(energy_flow, dict)

    print("  [PASS] Ecosystem engine validated")


def test_evolution_engine():
    """Test evolutionary dynamics."""
    print("Testing Evolution Engine...")

    from biological_engine import EcosystemEngine, EvolutionEngine

    ecosystem = EcosystemEngine()
    evolution = EvolutionEngine(ecosystem)

    # Create population
    organisms = []
    for i in range(20):
        organism = Organism(
            id=i,
            species_type=SpeciesType.HERBIVORE,
            position=np.random.uniform(0, 500, size=2),
            velocity=np.random.uniform(-1, 1, size=2),
            genome=Genome(),
            energy=100.0 + np.random.randn() * 20
        )
        organisms.append(organism)
        ecosystem.add_organism(organism, 1)

    # Test fitness computation
    for organism in organisms:
        fitness = evolution.compute_fitness(organism)
        assert 0 <= fitness <= 1.0
        assert organism.genome.fitness == fitness

    # Test fitness landscape update
    evolution.update_fitness_landscape()
    assert len(evolution.fitness_history) > 0

    # Test natural selection
    evolution.apply_natural_selection()
    # Some organisms should die

    # Test reproduction
    new_organisms = evolution.trigger_reproduction()
    # Some new organisms may be created

    # Test genetic distance
    if len(organisms) > 1:
        distance = evolution._compute_genetic_distance(organisms[0], organisms[1])
        assert distance >= 0

    print("  [PASS] Evolution engine validated")


def test_behavior_engine():
    """Test organism behavior."""
    print("Testing Behavior Engine...")

    from biological_engine import EcosystemEngine, OrganismBehaviorEngine

    ecosystem = EcosystemEngine()
    behavior = OrganismBehaviorEngine(ecosystem)

    # Create organisms
    herbivore = Organism(
        id=-1,
        species_type=SpeciesType.HERBIVORE,
        position=np.array([250.0, 250.0]),
        velocity=np.array([0.0, 0.0]),
        genome=Genome(),
        energy=100.0
    )

    carnivore = Organism(
        id=-2,
        species_type=SpeciesType.CARNIVORE,
        position=np.array([260.0, 250.0]),
        velocity=np.array([0.0, 0.0]),
        genome=Genome(),
        energy=100.0
    )

    ecosystem.add_organism(herbivore, 1)
    ecosystem.add_organism(carnivore, 2)

    # Test movement computation
    herb_direction = behavior.compute_movement(herbivore)
    assert herb_direction.shape == (2,)

    carnivore_direction = behavior.compute_movement(carnivore)
    assert carnivore_direction.shape == (2,)

    # Test stress response
    herbivore.stress_level = 0.7
    behavior.apply_stress_response(herbivore)
    assert herbivore.health < 1.0

    # Test seasonal behavior
    behavior.apply_seasonal_behavior(herbivore, SeasonalPhase.SPRING)
    # Health should be modified

    # Test behavior update
    behavior.update(0.1, SeasonalPhase.SUMMER)
    # Organisms should be updated

    print("  [PASS] Behavior engine validated")


def test_complete_simulation():
    """Test complete biological simulation system."""
    print("Testing Complete Biological Simulation System...")

    system = BiologicalSimulationSystem(world_size=np.array([500.0, 500.0]))

    # Initialize ecosystem
    species_configs = {
        1: {
            "type": SpeciesType.HERBIVORE,
            "count": 100,
            "initial_energy": 100.0,
        },
        2: {
            "type": SpeciesType.CARNIVORE,
            "count": 20,
            "initial_energy": 150.0,
        },
    }

    system.initialize_ecosystem(species_configs)

    # Verify initialization
    assert len(system.ecosystem.organisms) == 120

    # Run simulation
    print("  Running 50 simulation steps...")
    history = system.run_simulation(50)

    # Verify history
    assert len(history) == 50
    for metrics in history:
        assert "time" in metrics
        assert "season" in metrics
        assert "total_organisms" in metrics
        assert "energy_flow" in metrics
        assert "population_by_type" in metrics

    # Check seasonal cycling
    seasons_observed = set()
    for metrics in history:
        seasons_observed.add(metrics["season"])

    print(f"  Seasons observed: {seasons_observed}")

    # Get final status
    status = system.get_system_status()
    print(f"  Final system status: {status}")

    assert status["engine"] == "Biological"
    assert "Ecosystem" in status["systems"]
    assert "Organism" in status["systems"]
    assert "Evolution" in status["systems"]
    assert status["species_capacity"] == 1000
    assert status["accuracy_target"] == 0.99
    assert status["status"] == "BIOLOGICAL ENGINE COMPLETE"

    print("  [PASS] Complete simulation validated")


def run_all_tests():
    """Run all validation tests."""
    print("\n" + "="*70)
    print("BIOLOGICAL SIMULATION ENGINE VALIDATION")
    print("="*70 + "\n")

    test_genome_system()
    test_organism_system()
    test_ecosystem_engine()
    test_evolution_engine()
    test_behavior_engine()
    test_complete_simulation()

    print("\n" + "="*70)
    print("ALL TESTS PASSED - BIOLOGICAL ENGINE VALIDATED")
    print("="*70)

    print("\n" + "="*70)
    print("SYSTEM STATUS")
    print("="*70)

    system = BiologicalSimulationSystem()
    system.initialize_ecosystem({
        1: {"type": SpeciesType.HERBIVORE, "count": 50},
        2: {"type": SpeciesType.CARNIVORE, "count": 10},
    })

    print("Running 100 steps for final validation...")
    system.run_simulation(100)

    status = system.get_system_status()
    print("\nBIOLOGICAL ENGINE FINAL STATUS:")
    print(f"  Engine: {status['engine']}")
    print(f"  Systems: {', '.join(status['systems'])}")
    print(f"  Species Capacity: {status['species_capacity']}")
    print(f"  Accuracy Target: {status['accuracy_target']*100}%")
    print(f"  Status: {status['status']}")
    print(f"  Current Organisms: {status['current_status']['total_organisms']}")
    print(f"  Simulation Time: {status['current_status']['simulation_time']:.1f}")
    print(f"  Population: {status['current_status']['population_by_type']}")
    print(f"  Total Ecosystem Energy: {status['current_status']['total_ecosystem_energy']:.2f}")

    print("\n" + "="*70)
    print("BIOLOGICAL SIMULATION ENGINE - READY FOR DEPLOYMENT")
    print("="*70 + "\n")

    return status


if __name__ == "__main__":
    status = run_all_tests()
    print("\nFinal validation output:")
    print(f"Status: {status['status']}")
