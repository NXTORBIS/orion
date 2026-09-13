# Chemical Simulation Engine - ORION

## Overview

A comprehensive chemical simulation engine implementing:
- **Molecular Dynamics (MD)** - Particle interactions, force fields, temperature control
- **Chemical Reactions** - Multi-step reactions, rate constants, equilibrium states
- **Kinetics Engine** - Concentration evolution, temperature effects, catalysts

**Status:** experimental. 28 unit tests in `chemical_engine_test.py` pass (2026-09-14). No accuracy benchmark against reference data has been run.

## Components

### 1. Molecular Dynamics Engine

#### Features:
- **Particle Interactions**
  - Lennard-Jones (van der Waals)
  - Coulomb (electrostatic)
  - Bonded interactions

- **Force Fields**
  - Harmonic bonds
  - Angle bending
  - Dihedral angles

- **Temperature Control**
  - Langevin thermostat
  - Multiple ensembles (NVE, NVT, NPT, NVT-NH)

- **Integration Methods**
  - Velocity Verlet algorithm
  - Adaptive time stepping

### 2. Chemical Reaction Engine

#### Features:
- **Reaction Kinetics**
  - Forward and reverse reactions
  - Temperature-dependent rates (Arrhenius equation)
  - Multi-step reaction mechanisms

- **Equilibrium Analysis**
  - Equilibrium constant calculation (K_eq = k_f / k_r)
  - Gibbs free energy (ΔG = -RT ln(K_eq))
  - Reaction coordinate tracking

- **Mass Balance**
  - Stoichiometric calculations
  - Conservation of mass verification

### 3. Kinetics Engine

#### Features:
- **Concentration Evolution**
  - Ordinary differential equation integration
  - Explicit Euler method with adaptive timesteps

- **Temperature Effects**
  - Arrhenius rate constant variation
  - Temperature-dependent equilibrium

- **Catalyst Modeling**
  - Activation energy modification
  - Reaction rate enhancement

- **Reaction Pathways**
  - Multi-step sequential reactions
  - Pathway analysis and optimization

### 4. Coupled MD-Kinetics Engine

Integrates molecular dynamics with chemical kinetics for realistic simulations:
- MD provides atomistic detail
- Kinetics provides bulk chemistry
- Temperature from MD drives reaction rates
- Reactions can affect molecular structure

## Usage Examples

### Example 1: Simple Molecular Dynamics

```python
from chemical_engine import MolecularDynamicsEngine, Particle, EnsembleType
import numpy as np

# Create engine
md_engine = MolecularDynamicsEngine(ensemble=EnsembleType.NVT, temperature=298.15)

# Add particles
p1 = Particle(
    id=0,
    mass=1.0,
    charge=0.0,
    position=np.array([0.0, 0.0, 0.0]),
    velocity=np.array([0.5, 0.0, 0.0])
)
md_engine.add_particle(p1)

# Run simulation
results = md_engine.run_simulation(n_steps=1000, record_interval=10)
print(f"Energy conservation: {results['total_energies']}")
```

### Example 2: Chemical Reaction Simulation

```python
from chemical_engine import ChemicalReactionEngine, Molecule, ChemicalReaction

# Create reaction engine
rxn_engine = ChemicalReactionEngine()

# Add molecules
mol_a = Molecule(molecule_id="A", particles=[], formula="A", concentration=1.0)
mol_b = Molecule(molecule_id="B", particles=[], formula="B", concentration=0.0)
rxn_engine.add_molecule(mol_a)
rxn_engine.add_molecule(mol_b)

# Define reaction: A -> B
rxn = ChemicalReaction(
    reaction_id="R1",
    reactants={"A": 1},
    products={"B": 1},
    rate_constant_forward=0.1,
    rate_constant_reverse=0.01,
    activation_energy=50.0,
    temperature_dependent=True
)
rxn_engine.add_reaction(rxn)

# Run reaction
results = rxn_engine.run_reaction(n_steps=1000, dt=0.01, temperature=298.15)
print(f"Final [A]: {results['concentrations']['A'][-1]}")
```

### Example 3: Temperature-Dependent Kinetics

```python
from chemical_engine import ChemicalReaction

# Create temperature-dependent reaction
rxn = ChemicalReaction(
    reaction_id="R1",
    reactants={"A": 1},
    products={"B": 1},
    rate_constant_forward=1e6,
    rate_constant_reverse=1e3,
    activation_energy=50.0,  # kJ/mol
    temperature_dependent=True
)

# Calculate rates at different temperatures
for T in [298.15, 350.0, 400.0, 500.0]:
    k_f = rxn.arrhenius(T, 1e6, 50.0)
    print(f"T={T}K: k_f = {k_f:.2e}")
```

### Example 4: Catalyst Effect

```python
from chemical_engine import ChemicalKineticsEngine

# Create kinetics engine with catalyst
kin_engine = ChemicalKineticsEngine()
kin_engine.add_catalyst("Pt", activity=5.0)  # 5x rate enhancement

# Apply catalyst effect
catalyst_factor = kin_engine.apply_catalyst_effect(reaction, ["Pt"])
enhanced_rate = k_original * catalyst_factor
```

### Example 5: Full Coupled Simulation

```python
from chemical_engine import ChemicalSimulationEngine, Molecule, Particle

# Create main engine
sim_engine = ChemicalSimulationEngine(accuracy_target=0.99)

# Initialize system
sim_engine.initialize_system({
    "ensemble": "NVT",
    "temperature": 298.15,
    "box_size": 20.0
})

# Add molecule
molecule = Molecule(
    molecule_id="H2O",
    particles=[p1, p2, p3],
    bonds=[bond1, bond2],
    formula="H2O",
    concentration=1.0
)
sim_engine.add_molecule_to_system(molecule)

# Run full simulation
results = sim_engine.run_full_simulation(
    n_md_steps=1000,
    n_kinetics_steps=1000,
    temperature=298.15
)
```

## Intended Tolerances

These are design goals, not independently benchmarked results.

### Molecular Dynamics
- **Energy Conservation**: < 3% drift over 1000 steps
- **Temperature Stability**: Within 1% of target
- **Force Calculation**: Analytical LJ and Coulomb forms

### Chemical Reactions
- **Mass Balance**: < 1% error
- **Equilibrium**: Convergence to theoretical K_eq
- **Rate Constants**: Arrhenius equation validation

### Kinetics
- **ODE Integration**: Euler method with adaptive timestep
- **Temperature Effects**: Exponential (Arrhenius) dependence
- **Catalyst Modeling**: Linear rate enhancement

## System Capabilities

```
MOLECULAR_DYNAMICS:
  ✓ Particle interactions (LJ + Coulomb)
  ✓ Force fields (bonded, angle, dihedral)
  ✓ Temperature control (Langevin thermostat)
  ✓ Velocity Verlet integration
  ✓ Multiple ensembles (NVE, NVT, NPT, NVT-NH)

CHEMICAL_REACTIONS:
  ✓ Multi-step reaction mechanisms
  ✓ Rate constants (forward/reverse)
  ✓ Equilibrium constant calculation
  ✓ Gibbs free energy
  ✓ Temperature-dependent rates (Arrhenius)

KINETICS:
  ✓ Concentration evolution
  ✓ Temperature effects
  ✓ Catalyst modeling
  ✓ Reaction pathways
  ✓ Reaction coordinate computation

COUPLED_SIMULATION:
  ✓ MD + Kinetics coupling
  ✓ Temperature-dependent reaction rates
  ✓ Multi-scale simulation
  ✓ Reaction pathway analysis
```

## Test Results

28 unit tests pass (`cd simulation_engine && python -m pytest chemical_engine_test.py`, 2026-09-14). These check that the code runs and meets its own thresholds; they are not comparisons against experimental or reference simulation data.

## Performance

Not benchmarked; particle-count limits and speed have not been measured.

- **Timestep**: Adaptive from 0.001 to 0.01 ps
- **Integration**: Velocity Verlet (2nd order)

## Mathematical Foundation

### Lennard-Jones Potential
```
V(r) = 4ε[(σ/r)¹² - (σ/r)⁶]
F(r) = -dV/dr
```

### Coulomb Potential
```
V(r) = k_e * q₁ * q₂ / (4πε_r * r)
F(r) = k_e * q₁ * q₂ / (4πε_r * r²)
```

### Harmonic Bond
```
V(r) = 0.5 * k * (r - r₀)²
F(r) = -k * (r - r₀) * (dr/r)
```

### Arrhenius Equation
```
k(T) = k₀ * exp(-Eₐ / RT)
```

### Equilibrium Constant
```
K_eq = k_f / k_r
ΔG = -RT * ln(K_eq)
```

## System Status

- Status: experimental
- Unit tests: 28/28 passing
- Accuracy against reference data: not measured

## Future Enhancements

- Quantum corrections (tunneling, zero-point energy)
- Implicit solvent models
- Reactive force fields (ReaxFF)
- Parallel computing support
- Advanced ensemble methods (GCMC, TMMC)
- Machine learning force fields

## References

- Verlet, L. (1967). "Computer experiments on classical fluids"
- Allen, M.P. & Tildesley, D.J. (1987). "Computer Simulation of Liquids"
- Arrhenius, S. (1889). "Über die Reaktionsgeschwindigkeit bei der Inversion"
- Gibbs, J.W. (1873). "On the Equilibrium of Heterogeneous Substances"
