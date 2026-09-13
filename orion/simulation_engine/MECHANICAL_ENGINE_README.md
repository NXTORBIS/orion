# Mechanical Simulation Engine - Documentation

## Overview

The Mechanical Simulation Engine is a comprehensive physics-based simulation system for modeling machine dynamics, engineering systems, and mechanical design optimization. It is experimental: its 48 unit tests pass, but its physical accuracy has not been benchmarked against reference data.

**Key Features:**
- Real-time rigid body dynamics
- Gear systems and power transmission
- Linkage mechanisms with constraints
- PID control systems
- Vibration analysis and frequency response
- Stress analysis and failure prediction
- Thermal dynamics and heat transfer
- Multi-physics coupling

---

## Architecture

### Core Components

#### 1. Vector3D
Three-dimensional vector mathematics
- Basic operations: addition, subtraction, scaling
- Dot and cross products
- Magnitude and normalization
- Foundation for all spatial calculations

#### 2. RigidBody
Represents physical objects with mass and inertia
- Position, velocity, acceleration tracking
- Force and torque application
- Velocity Verlet integration
- Kinetic energy calculation
- Moment of inertia tensor

**Key Methods:**
```python
body = RigidBody(mass=5.0, name="Body1")
body.apply_force(Vector3D(100, 0, 0))
body.update(dt=0.01)
ke = body.kinetic_energy()
```

#### 3. Gear
Models gear teeth, meshing, and power transmission
- Pitch circle calculations
- Gear ratio determination
- Meshing contact analysis
- Efficiency losses
- Angular dynamics

**Key Methods:**
```python
gear = Gear("Gear1", radius=0.05, teeth=20, body=body)
gear.apply_torque(50.0)
contact = gear1.mesh_with(gear2)
```

#### 4. LinkageMechanism
Linkage mechanisms with multiple joints
- 4-bar mechanisms
- Slider-crank systems
- Constraint force application
- Complex kinematics

**Key Methods:**
```python
mech = LinkageMechanism("FourBar")
mech.add_body("Link1", body1)
mech.add_joint("Joint1", "Link1", "Link2", "revolute")
```

#### 5. ControlSystem
PID feedback control for mechanical systems
- Proportional, Integral, Derivative gains
- Anti-windup saturation
- Real-time performance tracking
- Convergence analysis

**Key Methods:**
```python
ctrl = ControlSystem(kp=2.0, ki=0.1, kd=0.05)
ctrl.set_target(100.0)
output = ctrl.calculate_output(current_value, dt)
```

#### 6. VibrationAnalyzer
Frequency domain and time domain vibration analysis
- FFT-based frequency detection
- Amplitude tracking
- Damping ratio calculation
- Phase angle measurement

**Key Methods:**
```python
analyzer = VibrationAnalyzer()
analyzer.record_sample(position, velocity, time)
freq_response = analyzer.calculate_frequency_response()
```

#### 7. PowerTransmission
Models power transfer through mechanical systems
- Input/output power tracking
- Efficiency losses
- Heat generation calculation

**Key Methods:**
```python
transmission = PowerTransmission("Motor", "Pump")
transmission.efficiency = 0.95
output = transmission.transmit_power(10000.0)
```

#### 8. StressAnalyzer
Structural stress analysis and failure prediction
- Stress from force and area
- Strain from stress (linear elastic)
- Safety factor calculation
- Failure risk assessment

**Key Methods:**
```python
analyzer = StressAnalyzer(yield_strength=400e6)
stress = analyzer.calculate_stress(force, area)
analyzer.record_stress(stress)
sf = analyzer.calculate_safety_factor()
```

#### 9. ThermalDynamics
Heat transfer and thermal management
- Heat capacity modeling
- Convection cooling
- Temperature evolution
- Thermal equilibrium

**Key Methods:**
```python
thermal = ThermalDynamics(initial_temp=293.15)
thermal.apply_heat(power_watts, dt)
thermal.update(dissipation, surface_area, dt)
```

#### 10. MechanicalEngine
Main simulation engine orchestrating all components
- Component management
- Time stepping
- Energy tracking
- Accuracy metrics

**Key Methods:**
```python
engine = MechanicalEngine()
body = engine.add_body("Motor", 2.0)
gear = engine.add_gear("Gear1", 0.05, 20, "Motor")
engine.step()
status = engine.get_status()
```

---

## Usage Examples

### Example 1: Simple Gear Train

```python
from mechanical_engine import MechanicalEngine, Vector3D

engine = MechanicalEngine()

# Create gears
motor_gear = engine.add_gear("Motor", 0.1, 40, "MotorBody")
load_gear = engine.add_gear("Load", 0.05, 20, "LoadBody")

# Apply torque and simulate
for step in range(1000):
    motor_gear.apply_torque(50.0)
    contact = motor_gear.mesh_with(load_gear)
    engine.step()

print(f"Motor Speed: {motor_gear.angular_velocity:.2f} rad/s")
print(f"Gear Ratio: {contact['gear_ratio']:.2f}")
print(f"Efficiency: {contact['efficiency']:.2%}")
```

### Example 2: Four-Bar Mechanism

```python
engine = MechanicalEngine()

# Create mechanism
mech = engine.add_mechanism("FourBar")
crank = engine.add_body("Crank", 0.5)
coupler = engine.add_body("Coupler", 0.4)
rocker = engine.add_body("Rocker", 0.5)
frame = engine.add_body("Frame", 2.0)

mech.add_body("Crank", crank)
mech.add_body("Coupler", coupler)
mech.add_body("Rocker", rocker)
mech.add_body("Frame", frame)

mech.add_joint("J1", "Crank", "Frame")
mech.add_joint("J2", "Crank", "Coupler")
mech.add_joint("J3", "Coupler", "Rocker")
mech.add_joint("J4", "Rocker", "Frame")

# Simulate
for step in range(500):
    crank.apply_force(Vector3D(10, 0, 0))
    mech.update(0.01)
```

### Example 3: PID Speed Control

```python
engine = MechanicalEngine()
motor_gear = engine.add_gear("Motor", 0.1, 40, "Motor")

# Create controller
controller = engine.add_control_system("SpeedCtrl", kp=2.0, ki=0.5, kd=0.1)
controller.set_target(50.0)  # Target: 50 rad/s

# Simulate control loop
for step in range(500):
    current_speed = motor_gear.angular_velocity
    output = controller.calculate_output(current_speed, 0.01)
    motor_gear.apply_torque(output)
    engine.step()
```

### Example 4: Vibration Analysis

```python
engine = MechanicalEngine()
mass = engine.add_body("Mass", 1.0)

analyzer = engine.add_vibration_analyzer("Mass")

# Free oscillation
for step in range(500):
    # Apply spring force
    spring_force = -100 * mass.position.x
    mass.apply_force(Vector3D(spring_force, 0, 0))
    
    engine.step()
    analyzer.record_sample(mass.position.x, mass.velocity.x, engine.time)

freq = analyzer.calculate_frequency_response()
damping = analyzer.calculate_damping()
print(f"Frequency: {freq['frequency']:.2f} rad/s")
print(f"Damping: {damping:.4f}")
```

### Example 5: Stress Analysis

```python
analyzer = StressAnalyzer(yield_strength=400e6)

# Analyze shaft under load
shaft_area = 0.0001  # m^2
applied_load = 200000  # N

stress = analyzer.calculate_stress(applied_load, shaft_area)
analyzer.record_stress(stress)

sf = analyzer.calculate_safety_factor()
prediction = analyzer.predict_failure()

print(f"Stress: {stress/1e6:.1f} MPa")
print(f"Safety Factor: {sf:.2f}")
print(f"Risk: {prediction['failure_risk']}")
```

### Example 6: Thermal Analysis

```python
thermal = engine.add_thermal_system("Motor")
thermal.set_ambient_temperature(293.15)

# Motor dissipating heat
for step in range(1000):
    thermal.update(power_dissipation=5000, surface_area=0.5, dt=0.01)

print(f"Temperature: {thermal.temperature:.1f} K")
print(f"Rise: {thermal.temperature - 293.15:.1f} K")
```

---

## Physical Accuracy

### Implemented Physics

#### Rigid Body Dynamics
- Newton's second law (F = ma)
- Rotational dynamics (τ = Iα)
- Velocity Verlet integration
- Damping and energy dissipation

#### Gear Mechanics
- Involute gear geometry
- Pitch circle calculations
- Contact stress (simplified Hertzian)
- Friction losses
- Power efficiency

#### Linkage Kinematics
- Constraint force application
- Joint reactions
- Closed-loop mechanism solving

#### Control Systems
- PID feedback control
- Anti-windup saturation
- Integral action tracking
- Derivative term filtering

#### Vibration Analysis
- FFT frequency detection
- Damping ratio calculation
- Natural frequency determination

#### Stress Analysis
- Uniaxial stress calculation
- Linear elastic stress-strain
- Safety factor determination
- Failure prediction

#### Thermal Management
- Heat capacity and conduction
- Convection cooling
- Temperature evolution
- Steady-state analysis

---

## Performance

Not benchmarked. No speed, scalability, memory, or conservation measurements have been recorded.

---

## Mathematical Foundations

### Integration Method

**Velocity Verlet:**
```
v(t + dt/2) = v(t) + a(t) * dt/2
x(t + dt) = x(t) + v(t + dt/2) * dt
a(t + dt) = F(t + dt) / m
v(t + dt) = v(t + dt/2) + a(t + dt) * dt/2
```

### Gear Contact
```
Gear Ratio = N2 / N1 = r2 / r1
Transmitted Torque = T1 / GR
Contact Stress = σ = F / A (simplified)
Efficiency = 1 - friction_loss
```

### PID Control
```
u(t) = Kp*e(t) + Ki*∫e(τ)dτ + Kd*de/dt
e(t) = setpoint - current_value
Anti-windup: |∫e(τ)dτ| ≤ I_max
```

### VibrationAnalysis
```
FFT-based frequency detection
f_dominant = argmax(|FFT(signal)|)
Damping: ζ = ln(decay_rate) / ln(time_constant)
```

---

## File Structure

```
simulation_engine/
├── mechanical_engine.py          # Core implementation (1200+ lines)
├── mechanical_engine_test.py     # Test suite (48 tests)
├── mechanical_examples.py         # 7 working examples
└── MECHANICAL_ENGINE_README.md   # This documentation
```

---

## Testing

Run the comprehensive test suite:

```python
from mechanical_engine_test import run_all_tests

passed, failed = run_all_tests()
```

**Test Coverage:**
- Vector operations: 4 tests
- Rigid body dynamics: 4 tests
- Gear mechanics: 4 tests
- Mechanisms: 3 tests
- Control systems: 3 tests
- Vibration analysis: 3 tests
- Power transmission: 2 tests
- Stress analysis: 5 tests
- Thermal systems: 4 tests
- Engine integration: 13 tests
- Accuracy validation: 3 tests

**Total: 48 tests, all passing** (`cd simulation_engine && python -m pytest mechanical_engine_test.py`, 2026-09-14). They check that components run and meet their own thresholds, not physical accuracy against reference data.

---

## Deployment

### Requirements
- Python 3.8+
- NumPy library
- Standard library only for core functionality

### Installation
```bash
# Copy files to simulation_engine directory
cp mechanical_engine*.py /path/to/orion/simulation_engine/
```

### Verification
```python
from mechanical_engine import MechanicalEngine
engine = MechanicalEngine()
print("Mechanical Engine Ready")
```

---

## Future Enhancements

Potential extensions:
- Nonlinear control systems
- Fluid-structure interaction
- Advanced constraint solvers
- Machine learning integration
- Real-time optimization
- Parallel processing
- GPU acceleration

---

## Support and Troubleshooting

### Common Issues

**Energy not conserving:**
- Reduce timestep size
- Check for excessive damping
- Verify force applications

**Constraints not satisfied:**
- Increase constraint iteration count
- Adjust constraint stiffness
- Check joint definitions

**Control not converging:**
- Tune PID gains (start with Kp)
- Reduce integral windup limit
- Check for physical constraints

---

## References

1. Goldstein, H. Classical Mechanics (3rd ed.)
2. Norton, R. L. Design of Machinery
3. Harris, T. A. Rolling Bearing Analysis
4. Åström, K. J., & Murray, R. M. Feedback Systems
5. Clipped Noise

---

## License and Attribution

ORION Mechanical Simulation Engine  
Part of ORION  
Date: September 14, 2026  
Status: Experimental; unit tests pass, physical accuracy not benchmarked

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>

---

*Mechanical Simulation Engine - 11th Domain Specialist*  
*ORION AI Research Build*  
*September 14, 2026*
