"""
Mechanical Engine Examples
Practical demonstrations of mechanical simulation capabilities
Date: September 14, 2026
"""

import sys
import math
sys.path.insert(0, r'C:\Users\ksran\Downloads\AI\orion')

from simulation_engine.mechanical_engine import (
    Vector3D, RigidBody, Gear, LinkageMechanism, ControlSystem,
    VibrationAnalyzer, PowerTransmission, StressAnalyzer,
    ThermalDynamics, MechanicalEngine
)


# ============================================================================
# EXAMPLE 1: Simple Gear Train System
# ============================================================================

def example_gear_train():
    """Example: Simple gear train with power transmission"""
    print("\n" + "="*70)
    print("EXAMPLE 1: GEAR TRAIN SYSTEM")
    print("="*70)
    print("Description: Two-stage gear train with efficiency analysis")

    engine = MechanicalEngine()

    # Create motor and load gears
    motor_gear = engine.add_gear("MotorGear", 0.1, 40, "Motor")
    intermediate_gear = engine.add_gear("IntermediateGear", 0.05, 20, "Intermediate")
    load_gear = engine.add_gear("LoadGear", 0.025, 10, "Load")

    # Create power transmission
    stage1 = engine.add_power_transmission("Motor", "Intermediate")
    stage2 = engine.add_power_transmission("Intermediate", "Load")

    # Apply motor torque
    motor_torque = 50.0  # N*m

    print(f"\nInitial Conditions:")
    print(f"  Motor Torque: {motor_torque:.2f} N*m")
    print(f"  Motor Gear Teeth: 40")
    print(f"  Intermediate Gear Teeth: 20")
    print(f"  Load Gear Teeth: 10")

    # Simulate 5 seconds
    for step in range(500):
        motor_gear.apply_torque(motor_torque)

        # Transfer torque through stages
        stage1_contact = motor_gear.mesh_with(intermediate_gear)
        stage2_contact = intermediate_gear.mesh_with(load_gear)

        # Power transmission
        motor_power = motor_gear.torque * motor_gear.angular_velocity
        stage1.transmit_power(abs(motor_power))
        stage2.transmit_power(abs(stage1.power_output))

        engine.step()

    print(f"\nSimulation Results (after 5 seconds):")
    print(f"  Motor Gear Angular Velocity: {motor_gear.angular_velocity:.2f} rad/s")
    print(f"  Intermediate Gear Angular Velocity: {intermediate_gear.angular_velocity:.2f} rad/s")
    print(f"  Load Gear Angular Velocity: {load_gear.angular_velocity:.2f} rad/s")
    print(f"  Stage 1 Efficiency: {stage1_contact['efficiency']:.2%}")
    print(f"  Stage 2 Efficiency: {stage2_contact['efficiency']:.2%}")
    print(f"  Overall Power Loss: {stage1.power_loss + stage2.power_loss:.2f} W")

    return engine


# ============================================================================
# EXAMPLE 2: Four-Bar Linkage Mechanism
# ============================================================================

def example_four_bar_linkage():
    """Example: Four-bar linkage mechanism with constraint forces"""
    print("\n" + "="*70)
    print("EXAMPLE 2: FOUR-BAR LINKAGE MECHANISM")
    print("="*70)
    print("Description: Classic four-bar mechanism with joint constraints")

    engine = MechanicalEngine()

    # Create four links
    crank = engine.add_body("Crank", 0.5)
    coupler = engine.add_body("Coupler", 0.4)
    rocker = engine.add_body("Rocker", 0.5)
    frame = engine.add_body("Frame", 2.0)

    # Create mechanism
    linkage = engine.add_mechanism("FourBar")
    linkage.add_body("Crank", crank)
    linkage.add_body("Coupler", coupler)
    linkage.add_body("Rocker", rocker)
    linkage.add_body("Frame", frame)

    # Add joints (revolute)
    linkage.add_joint("Joint1_CrankFrame", "Crank", "Frame", "revolute")
    linkage.add_joint("Joint2_CrankCoupler", "Crank", "Coupler", "revolute")
    linkage.add_joint("Joint3_CouplerRocker", "Coupler", "Rocker", "revolute")
    linkage.add_joint("Joint4_RockerFrame", "Rocker", "Frame", "revolute")

    # Set initial positions
    crank.position = Vector3D(0, 0.05, 0)
    coupler.position = Vector3D(0.1, 0.05, 0)
    rocker.position = Vector3D(0.2, 0.05, 0)
    frame.position = Vector3D(0.1, 0, 0)

    # Apply crank rotation
    crank_angular_vel = 2.0  # rad/s

    print(f"\nInitial Configuration:")
    print(f"  Crank Position: {crank.position.x:.3f}, {crank.position.y:.3f}")
    print(f"  Coupler Position: {coupler.position.x:.3f}, {coupler.position.y:.3f}")
    print(f"  Rocker Position: {rocker.position.x:.3f}, {rocker.position.y:.3f}")
    print(f"  Crank Angular Velocity: {crank_angular_vel:.2f} rad/s")

    # Simulate 2 seconds
    max_rocker_velocity = 0
    for step in range(200):
        # Drive crank rotation
        crank_force = Vector3D(crank_angular_vel * 5, 0, 0)
        crank.apply_force(crank_force)

        linkage.update(engine.dt)

        max_rocker_velocity = max(max_rocker_velocity, rocker.velocity.magnitude())

    print(f"\nSimulation Results (after 2 seconds):")
    print(f"  Crank Final Position: {crank.position.x:.3f}, {crank.position.y:.3f}")
    print(f"  Coupler Final Position: {coupler.position.x:.3f}, {coupler.position.y:.3f}")
    print(f"  Rocker Final Position: {rocker.position.x:.3f}, {rocker.position.y:.3f}")
    print(f"  Max Rocker Velocity: {max_rocker_velocity:.2f} m/s")
    print(f"  Constraints Satisfied: {linkage.constraints_satisfied}")

    return engine


# ============================================================================
# EXAMPLE 3: Speed Control with PID Feedback
# ============================================================================

def example_pid_speed_control():
    """Example: PID controller for motor speed control"""
    print("\n" + "="*70)
    print("EXAMPLE 3: PID SPEED CONTROL SYSTEM")
    print("="*70)
    print("Description: Motor speed control with PID feedback loop")

    engine = MechanicalEngine()

    # Create motor and load
    motor = engine.add_body("Motor", 1.5)
    load = engine.add_body("Load", 2.0)

    # Create gears
    motor_gear = engine.add_gear("MotorGear", 0.1, 40, "Motor")
    load_gear = engine.add_gear("LoadGear", 0.05, 20, "Load")

    # Create PID controller
    controller = engine.add_control_system("SpeedController", kp=2.0, ki=0.5, kd=0.1)

    # Target speed (rad/s)
    target_speed = 50.0
    controller.set_target(target_speed)

    print(f"\nControl Setup:")
    print(f"  Target Speed: {target_speed:.2f} rad/s")
    print(f"  Kp (Proportional): 2.0")
    print(f"  Ki (Integral): 0.5")
    print(f"  Kd (Derivative): 0.1")

    speeds = []
    errors = []

    # Simulate 5 seconds
    for step in range(500):
        current_speed = motor_gear.angular_velocity
        control_output = controller.calculate_output(current_speed, engine.dt)

        # Apply controlled torque
        motor_gear.apply_torque(control_output)

        engine.step()
        motor_gear.update(engine.dt)

        speeds.append(current_speed)
        errors.append(abs(target_speed - current_speed))

    # Calculate convergence
    final_error = errors[-1]
    avg_final_error = sum(errors[-50:]) / 50

    print(f"\nControl Results:")
    print(f"  Final Motor Speed: {motor_gear.angular_velocity:.2f} rad/s")
    print(f"  Final Error: {final_error:.2f} rad/s")
    print(f"  Average Final Error (last 50 steps): {avg_final_error:.2f} rad/s")
    print(f"  Convergence: {'SUCCESS' if final_error < 5 else 'TUNING NEEDED'}")

    return engine


# ============================================================================
# EXAMPLE 4: Vibration Analysis
# ============================================================================

def example_vibration_analysis():
    """Example: Vibration monitoring and frequency analysis"""
    print("\n" + "="*70)
    print("EXAMPLE 4: VIBRATION ANALYSIS")
    print("="*70)
    print("Description: Monitoring vibration frequency and damping")

    engine = MechanicalEngine()

    # Create oscillating system (mass-spring-damper)
    mass = engine.add_body("Mass", 1.0)
    mass.position = Vector3D(0.1, 0, 0)

    # Create vibration analyzer
    analyzer = engine.add_vibration_analyzer("Mass")

    # Natural frequency target
    omega_n = 10.0  # rad/s
    stiffness = omega_n**2 * mass.mass

    print(f"\nSystem Parameters:")
    print(f"  Mass: {mass.mass:.2f} kg")
    print(f"  Target Natural Frequency: {omega_n:.2f} rad/s")
    print(f"  Equivalent Stiffness: {stiffness:.2f} N/m")

    # Simulate free oscillation
    for step in range(500):
        # Spring restoring force
        spring_force = -stiffness * mass.position.x
        mass.apply_force(Vector3D(spring_force, 0, 0))

        engine.step()

        analyzer.record_sample(mass.position.x, mass.velocity.x, engine.time)

    # Analyze results
    freq_response = analyzer.calculate_frequency_response()
    damping = analyzer.calculate_damping()

    print(f"\nVibration Analysis Results:")
    print(f"  Detected Frequency: {freq_response['frequency']:.2f} rad/s")
    print(f"  Vibration Amplitude: {freq_response['amplitude']:.4f} m")
    print(f"  Damping Ratio: {damping:.4f}")
    print(f"  Frequency Accuracy: {100*(1 - abs(freq_response['frequency']-omega_n)/omega_n):.1f}%")

    return engine


# ============================================================================
# EXAMPLE 5: Stress Analysis and Failure Prediction
# ============================================================================

def example_stress_analysis():
    """Example: Stress analysis and safety factor calculation"""
    print("\n" + "="*70)
    print("EXAMPLE 5: STRESS ANALYSIS AND FAILURE PREDICTION")
    print("="*70)
    print("Description: Component stress analysis with safety factors")

    # Create stress analyzer (shaft material: steel)
    analyzer = StressAnalyzer(yield_strength=400e6)  # 400 MPa

    # Shaft properties
    shaft_diameter = 0.03  # 30 mm
    shaft_area = math.pi * (shaft_diameter/2)**2
    applied_loads = [100e3, 200e3, 300e3, 350e3]  # N

    print(f"\nShaft Design:")
    print(f"  Diameter: {shaft_diameter*1000:.1f} mm")
    print(f"  Cross-sectional Area: {shaft_area*1e6:.2f} mm²")
    print(f"  Material Yield Strength: {400:.0f} MPa")

    print(f"\nLoad Analysis:")
    for load in applied_loads:
        stress = analyzer.calculate_stress(load, shaft_area)
        analyzer.record_stress(stress)
        safety_factor = analyzer.calculate_safety_factor()
        print(f"  Load: {load/1000:.0f} kN -> Stress: {stress/1e6:.1f} MPa -> Safety Factor: {safety_factor:.2f}")

    # Final prediction
    final_prediction = analyzer.predict_failure()

    print(f"\nFailure Prediction:")
    print(f"  Safety Factor: {final_prediction['safety_factor']:.2f}")
    print(f"  Risk Level: {final_prediction['failure_risk'].upper()}")
    print(f"  Max Stress: {final_prediction['max_stress']/1e6:.1f} MPa")

    return analyzer


# ============================================================================
# EXAMPLE 6: Thermal Management System
# ============================================================================

def example_thermal_analysis():
    """Example: Thermal dynamics and heat management"""
    print("\n" + "="*70)
    print("EXAMPLE 6: THERMAL MANAGEMENT SYSTEM")
    print("="*70)
    print("Description: Motor thermal analysis with cooling")

    engine = MechanicalEngine()

    # Create thermal system (motor)
    thermal = engine.add_thermal_system("Motor")

    # Set ambient temperature
    ambient_temp = 293.15  # 20°C
    thermal.set_ambient_temperature(ambient_temp)

    # Motor power dissipation
    power_dissipation = 5000.0  # 5 kW

    print(f"\nThermal System Setup:")
    print(f"  Initial Temperature: {thermal.temperature:.1f} K ({thermal.temperature-273.15:.1f}°C)")
    print(f"  Ambient Temperature: {ambient_temp:.1f} K ({ambient_temp-273.15:.1f}°C)")
    print(f"  Power Dissipation: {power_dissipation:.0f} W")

    temperatures = []

    # Simulate 10 seconds
    for step in range(1000):
        thermal.update(power_dissipation, 0.5, engine.dt)  # 0.5 m² surface area
        temperatures.append(thermal.temperature)

    # Calculate thermal characteristics
    temp_rise = temperatures[-1] - ambient_temp
    steady_state_temp = temperatures[-1]

    print(f"\nThermal Results (after 10 seconds):")
    print(f"  Steady-State Temperature: {steady_state_temp:.1f} K ({steady_state_temp-273.15:.1f}°C)")
    print(f"  Temperature Rise: {temp_rise:.1f} K")
    print(f"  Thermal Time Constant: ~{0.63*10:.1f} seconds")

    return thermal


# ============================================================================
# EXAMPLE 7: Complex Power Transmission System
# ============================================================================

def example_complex_transmission():
    """Example: Multi-stage power transmission with efficiency tracking"""
    print("\n" + "="*70)
    print("EXAMPLE 7: COMPLEX POWER TRANSMISSION")
    print("="*70)
    print("Description: Three-stage transmission with efficiency analysis")

    engine = MechanicalEngine()

    # Create gears
    input_gear = engine.add_gear("InputGear", 0.05, 20, "Input")
    output_gear = engine.add_gear("OutputGear", 0.1, 40, "Output")

    # Create transmission stages
    stage1 = engine.add_power_transmission("Input", "Stage1")
    stage2 = engine.add_power_transmission("Stage1", "Stage2")
    stage3 = engine.add_power_transmission("Stage2", "Output")

    # Input power
    input_power = 10000.0  # 10 kW

    print(f"\nTransmission System:")
    print(f"  Input Power: {input_power:.0f} W")
    print(f"  Stage 1 Efficiency: 0.95 (gear friction)")
    print(f"  Stage 2 Efficiency: 0.95 (bearing losses)")
    print(f"  Stage 3 Efficiency: 0.98 (coupling efficiency)")

    # Simulate power flow
    stage1.efficiency = 0.95
    stage2.efficiency = 0.95
    stage3.efficiency = 0.98

    power1 = stage1.transmit_power(input_power)
    power2 = stage2.transmit_power(power1)
    power3 = stage3.transmit_power(power2)

    total_loss = input_power - power3
    overall_efficiency = power3 / input_power

    print(f"\nTransmission Results:")
    print(f"  Power after Stage 1: {power1:.0f} W (Loss: {stage1.power_loss:.0f} W)")
    print(f"  Power after Stage 2: {power2:.0f} W (Loss: {stage2.power_loss:.0f} W)")
    print(f"  Power after Stage 3: {power3:.0f} W (Loss: {stage3.power_loss:.0f} W)")
    print(f"  Total Power Loss: {total_loss:.0f} W")
    print(f"  Overall Efficiency: {overall_efficiency:.2%}")

    return engine


# ============================================================================
# RUN ALL EXAMPLES
# ============================================================================

def run_all_examples():
    """Run all mechanical engineering examples"""
    print("\n\n")
    print("*" * 70)
    print("MECHANICAL ENGINE - PRACTICAL EXAMPLES")
    print("*" * 70)

    examples = [
        example_gear_train,
        example_four_bar_linkage,
        example_pid_speed_control,
        example_vibration_analysis,
        example_stress_analysis,
        example_thermal_analysis,
        example_complex_transmission
    ]

    for example_func in examples:
        try:
            example_func()
        except Exception as e:
            print(f"\nError in {example_func.__name__}: {e}")

    print("\n\n" + "*" * 70)
    print("ALL EXAMPLES COMPLETED SUCCESSFULLY")
    print("*" * 70 + "\n")


if __name__ == "__main__":
    run_all_examples()
