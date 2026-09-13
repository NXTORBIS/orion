"""
Simulation Engine Examples
Demonstrates usage of the core infrastructure for all 6 simulation types.
"""

import numpy as np
from pathlib import Path

# Import simulation types
from .simulations import (
    RigidBodySimulation,
    FluidDynamicsSimulation,
    BiologicalSimulation,
    MarketSimulation,
    PopulationDynamicsSimulation,
    ChemicalReactionSimulation,
    MechanicalSystemSimulation,
    GearSystemSimulation,
)
from .visualization.renderer import RenderConfig
from .data_export.exporter import ExportConfig


def example_rigid_body_dynamics():
    """Example: Rigid body simulation with collisions."""
    print("\n" + "="*60)
    print("EXAMPLE 1: Rigid Body Dynamics")
    print("="*60)

    # Create simulation
    sim = RigidBodySimulation("Bouncing Balls")
    sim.config.duration = 10.0
    sim.config.real_time_mode = False

    # Create particles
    n_particles = 50
    positions = np.random.rand(n_particles, 3) * 10.0
    velocities = (np.random.rand(n_particles, 3) - 0.5) * 5.0
    masses = np.ones(n_particles)
    radii = np.ones(n_particles) * 0.2

    # Initialize
    sim.initialize(positions, velocities, masses, radii)

    # Add visualization
    from .visualization.renderer import VisualizationRenderer
    renderer = VisualizationRenderer(RenderConfig(width=640, height=480))
    sim.set_renderer(renderer)

    # Run
    results = sim.run(steps=int(sim.config.duration / sim.config.dt))

    print(f"Simulation completed!")
    print(f"  Duration: {results['execution_time']:.2f}s")
    print(f"  Iterations: {results['iterations']}")
    print(f"  Final particles: {len(results['final_state']['positions'])}")
    print(f"  Frames: {renderer.get_frame_count()}")

    return sim, results


def example_ecosystem_simulation():
    """Example: Biological ecosystem with predator-prey."""
    print("\n" + "="*60)
    print("EXAMPLE 2: Ecosystem Dynamics")
    print("="*60)

    # Create simulation
    sim = BiologicalSimulation("Forest Ecosystem")
    sim.config.duration = 50.0

    # Create agents
    n_prey = 200
    n_predators = 20

    prey_pos = np.random.rand(n_prey, 2) * 100.0
    prey_vel = (np.random.rand(n_prey, 2) - 0.5) * 2.0
    prey_energy = np.ones(n_prey) * 50.0
    prey_species = np.zeros(n_prey, dtype=int)

    pred_pos = np.random.rand(n_predators, 2) * 100.0
    pred_vel = (np.random.rand(n_predators, 2) - 0.5) * 1.0
    pred_energy = np.ones(n_predators) * 100.0
    pred_species = np.ones(n_predators, dtype=int)

    # Combine
    positions = np.vstack([prey_pos, pred_pos])
    velocities = np.vstack([prey_vel, pred_vel])
    energies = np.concatenate([prey_energy, pred_energy])
    species = np.concatenate([prey_species, pred_species])

    # Initialize
    sim.add_agents(positions, velocities, energies, species)

    # Run
    results = sim.run(steps=500)

    print(f"Simulation completed!")
    print(f"  Duration: {results['execution_time']:.2f}s")
    print(f"  Final animals: {len(results['final_state']['positions'])}")
    if "energies" in results["final_state"]:
        print(f"  Average energy: {np.mean(results['final_state']['energies']):.2f}")

    return sim, results


def example_market_simulation():
    """Example: Supply-demand market equilibrium."""
    print("\n" + "="*60)
    print("EXAMPLE 3: Market Dynamics")
    print("="*60)

    # Create simulation
    sim = MarketSimulation("Widget Market")
    sim.config.duration = 20.0

    # Initialize market
    initial_qty = np.array([100.0])
    initial_price = np.array([10.0])
    demand_params = {"p0": 20.0}
    supply_params = {"p0": 5.0}

    sim.initialize_market(initial_qty, initial_price, demand_params, supply_params)

    # Add callback to track prices
    prices_history = []
    def track_prices(step, state, time):
        if step % 100 == 0:
            prices = state.get("prices")
            if prices is not None:
                prices_history.append((time, prices[0]))

    sim.add_step_callback(track_prices)

    # Run
    results = sim.run(steps=2000)

    print(f"Simulation completed!")
    print(f"  Duration: {results['execution_time']:.2f}s")
    if prices_history:
        print(f"  Initial price: {prices_history[0][1]:.2f}")
        print(f"  Final price: {prices_history[-1][1]:.2f}")

    return sim, results


def example_predator_prey():
    """Example: Lotka-Volterra predator-prey dynamics."""
    print("\n" + "="*60)
    print("EXAMPLE 4: Predator-Prey Dynamics")
    print("="*60)

    # Create simulation
    sim = PopulationDynamicsSimulation("Lynx-Hare Population")
    sim.config.duration = 50.0

    # Initialize
    sim.initialize(
        prey_population=100.0,
        predator_population=20.0,
        prey_birth_rate=0.5,
        predator_death_rate=0.2,
        predation_rate=0.01,
        predator_efficiency=0.1,
    )

    # Track populations
    prey_history = []
    pred_history = []
    times = []

    def track_pops(step, state, time):
        if step % 50 == 0:
            prey = state.get("prey")
            preds = state.get("predators")
            if prey is not None and preds is not None:
                prey_history.append(prey[0])
                pred_history.append(preds[0])
                times.append(time)

    sim.add_step_callback(track_pops)

    # Run
    results = sim.run()

    print(f"Simulation completed!")
    print(f"  Duration: {results['execution_time']:.2f}s")
    if prey_history and pred_history:
        print(f"  Prey range: {min(prey_history):.1f} - {max(prey_history):.1f}")
        print(f"  Predator range: {min(pred_history):.1f} - {max(pred_history):.1f}")

    return sim, results


def example_chemical_reaction():
    """Example: Chemical reaction kinetics."""
    print("\n" + "="*60)
    print("EXAMPLE 5: Chemical Reactions")
    print("="*60)

    # Create simulation
    sim = ChemicalReactionSimulation("A ⟷ B + C Reaction")
    sim.config.duration = 5.0

    # Add reactions
    # A -> B + C (decomposition)
    sim.add_reaction(
        name="Decomposition",
        reactants={"A": 1},
        products={"B": 1, "C": 1},
        rate_constant=0.1,
    )

    # Set initial concentrations
    sim.set_initial_concentrations({
        "A": 1.0,  # 1 M
        "B": 0.0,
        "C": 0.0,
    })

    # Track concentrations
    conc_history = {}
    def track_conc(step, state, time):
        if step % 100 == 0:
            conc = sim.get_concentrations()
            for species, c in conc.items():
                if species not in conc_history:
                    conc_history[species] = []
                conc_history[species].append((time, c))

    sim.add_step_callback(track_conc)

    # Run
    results = sim.run()

    print(f"Simulation completed!")
    print(f"  Duration: {results['execution_time']:.2f}s")
    print(f"  Final concentrations: {sim.get_concentrations()}")

    return sim, results


def example_mechanical_system():
    """Example: Mechanical system with springs."""
    print("\n" + "="*60)
    print("EXAMPLE 6: Mechanical System")
    print("="*60)

    # Create simulation
    sim = MechanicalSystemSimulation("Mass-Spring System")
    sim.config.duration = 10.0

    # Create structure: 3 nodes connected by springs
    positions = np.array([
        [0.0, 0.0, 0.0],
        [1.0, 0.0, 0.0],
        [2.0, 0.0, 0.0],
    ])

    # Connections: (node_i, node_j, natural_length)
    connections = [
        (0, 1, 1.0),  # Spring between node 0 and 1
        (1, 2, 1.0),  # Spring between node 1 and 2
    ]

    masses = np.array([1.0, 1.0, 1.0])

    # Initialize
    sim.initialize_structure(positions, connections, masses)

    # Apply initial displacement
    init_pos = sim.state.get_state("positions")
    init_pos[1, 1] = 0.5  # Displace node 1 in y direction
    sim.state.set_state("positions", init_pos)

    # Run
    results = sim.run()

    print(f"Simulation completed!")
    print(f"  Duration: {results['execution_time']:.2f}s")
    print(f"  Final positions:\n{results['final_state']['positions']}")

    return sim, results


def example_with_data_export():
    """Example: Simulation with data export."""
    print("\n" + "="*60)
    print("EXAMPLE 7: Data Export")
    print("="*60)

    # Create simple simulation
    sim = BiologicalSimulation("Export Test")
    sim.config.duration = 5.0

    positions = np.random.rand(10, 2) * 100.0
    velocities = (np.random.rand(10, 2) - 0.5) * 2.0
    energies = np.ones(10) * 50.0

    sim.add_agents(positions, velocities, energies)

    # Set up exporter
    from .data_export.exporter import DataExporter
    exporter = DataExporter(ExportConfig(format="csv"))
    sim.set_exporter(exporter)

    # Run
    results = sim.run()

    # Export data
    output_dir = Path("simulation_results")
    output_dir.mkdir(exist_ok=True)

    export_path = output_dir / "ecosystem_data.csv"
    sim.export_data(export_path, format="csv")

    print(f"Simulation completed!")
    print(f"  Data exported to: {export_path}")
    if export_path.exists():
        print(f"  File size: {export_path.stat().st_size} bytes")

    return sim, results


def run_all_examples():
    """Run all example simulations."""
    print("\n" + "="*80)
    print("ORION SIMULATION ENGINE - INFRASTRUCTURE EXAMPLES")
    print("="*80)

    examples = [
        ("Rigid Body Dynamics", example_rigid_body_dynamics),
        ("Ecosystem Simulation", example_ecosystem_simulation),
        ("Market Dynamics", example_market_simulation),
        ("Predator-Prey", example_predator_prey),
        ("Chemical Reactions", example_chemical_reaction),
        ("Mechanical System", example_mechanical_system),
        ("Data Export", example_with_data_export),
    ]

    results = {}
    for name, example_fn in examples:
        try:
            results[name] = example_fn()
            print("✓ Example completed successfully")
        except Exception as e:
            print(f"✗ Example failed: {e}")
            results[name] = None

    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    successful = sum(1 for r in results.values() if r is not None)
    print(f"Completed: {successful}/{len(examples)} examples")
    print("\nSimulation Engine Infrastructure Test Complete!")

    return results


if __name__ == "__main__":
    run_all_examples()
