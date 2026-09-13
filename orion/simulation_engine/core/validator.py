"""
Parameter Validation
Input validation, constraint checking, boundary conditions,
and physical realism checks.
"""

from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Callable, Tuple
import numpy as np


@dataclass
class ValidationResult:
    """Result of parameter validation."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    corrected_params: Optional[Dict[str, Any]] = None

    def __bool__(self) -> bool:
        return self.is_valid


class ParameterValidator:
    """
    Validates simulation parameters for physical realism and constraints.
    Supports:
    - Type checking
    - Range validation
    - Constraint checking
    - Boundary condition validation
    - Physical realism checks
    """

    def __init__(self):
        """Initialize validator with default rules."""
        self.type_rules: Dict[str, type] = {}
        self.range_rules: Dict[str, Tuple[float, float]] = {}
        self.constraint_rules: Dict[str, Callable] = {}
        self.physical_rules: Dict[str, Callable] = {}
        self.custom_validators: List[Callable] = []

    def add_type_rule(self, param_name: str, param_type: type) -> None:
        """Add type checking rule."""
        self.type_rules[param_name] = param_type

    def add_range_rule(
        self, param_name: str, min_val: float, max_val: float
    ) -> None:
        """Add range constraint rule."""
        self.range_rules[param_name] = (min_val, max_val)

    def add_constraint(self, param_name: str, constraint_fn: Callable) -> None:
        """Add custom constraint function."""
        self.constraint_rules[param_name] = constraint_fn

    def add_physical_check(self, param_name: str, check_fn: Callable) -> None:
        """Add physical realism check."""
        self.physical_rules[param_name] = check_fn

    def add_custom_validator(self, validator_fn: Callable) -> None:
        """Add custom multi-parameter validator."""
        self.custom_validators.append(validator_fn)

    def validate(
        self,
        params: Dict[str, Any],
        auto_correct: bool = False,
    ) -> ValidationResult:
        """
        Validate parameters.

        Args:
            params: Parameter dictionary to validate
            auto_correct: Automatically correct common issues

        Returns:
            ValidationResult with any errors and corrections
        """
        errors: List[str] = []
        warnings: List[str] = []
        corrected = params.copy() if auto_correct else None

        # Type checking
        for param_name, expected_type in self.type_rules.items():
            if param_name not in params:
                errors.append(f"Missing required parameter: {param_name}")
                continue

            value = params[param_name]
            if not isinstance(value, expected_type):
                errors.append(
                    f"Parameter '{param_name}' has wrong type. "
                    f"Expected {expected_type.__name__}, "
                    f"got {type(value).__name__}"
                )

        # Range checking
        for param_name, (min_val, max_val) in self.range_rules.items():
            if param_name not in params:
                continue

            value = params[param_name]
            if isinstance(value, (int, float)):
                if value < min_val or value > max_val:
                    msg = (
                        f"Parameter '{param_name}' out of range "
                        f"[{min_val}, {max_val}]. Got {value}"
                    )
                    if auto_correct:
                        corrected[param_name] = np.clip(value, min_val, max_val)
                        warnings.append(f"{msg} (auto-corrected to {corrected[param_name]})")
                    else:
                        errors.append(msg)

        # Constraint checking
        for param_name, constraint_fn in self.constraint_rules.items():
            if param_name not in params:
                continue

            try:
                if not constraint_fn(params[param_name]):
                    errors.append(
                        f"Parameter '{param_name}' violates constraint"
                    )
            except Exception as e:
                errors.append(
                    f"Error checking constraint for '{param_name}': {str(e)}"
                )

        # Physical realism checks
        for param_name, check_fn in self.physical_rules.items():
            if param_name not in params:
                continue

            try:
                result = check_fn(params[param_name])
                if isinstance(result, tuple):
                    is_valid, message = result
                    if not is_valid:
                        errors.append(
                            f"Physical check failed for '{param_name}': {message}"
                        )
                elif not result:
                    errors.append(
                        f"Physical realism check failed for '{param_name}'"
                    )
            except Exception as e:
                errors.append(
                    f"Error in physical check for '{param_name}': {str(e)}"
                )

        # Custom validators
        for validator_fn in self.custom_validators:
            try:
                result = validator_fn(params)
                if isinstance(result, tuple):
                    is_valid, messages = result
                    if not is_valid:
                        if isinstance(messages, list):
                            errors.extend(messages)
                        else:
                            errors.append(messages)
                elif not result:
                    errors.append("Custom validation failed")
            except Exception as e:
                errors.append(f"Error in custom validator: {str(e)}")

        is_valid = len(errors) == 0
        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            corrected_params=corrected if auto_correct else None,
        )


class PhysicsValidator(ParameterValidator):
    """Specialized validator for physics simulations."""

    def __init__(self):
        super().__init__()

        # Common physics parameters
        self.add_range_rule("mass", 0.001, 1e6)
        self.add_range_rule("gravity", -100.0, 100.0)
        self.add_range_rule("time_step", 1e-5, 1.0)
        self.add_range_rule("damping", 0.0, 1.0)
        self.add_range_rule("friction", 0.0, 1.0)

        # Physical realism checks
        self.add_physical_check("mass", self._check_mass_positive)
        self.add_physical_check("time_step", self._check_timestep_stability)

    @staticmethod
    def _check_mass_positive(mass: float) -> bool:
        """Mass must be positive."""
        return mass > 0

    @staticmethod
    def _check_timestep_stability(dt: float) -> Tuple[bool, str]:
        """Check time step is reasonable for stability."""
        if dt > 0.1:
            return False, "Large time steps may cause instability"
        if dt < 1e-6:
            return False, "Very small time steps may be inefficient"
        return True, "Time step reasonable"


class BiologyValidator(ParameterValidator):
    """Specialized validator for biological simulations."""

    def __init__(self):
        super().__init__()

        # Population parameters
        self.add_range_rule("birth_rate", 0.0, 10.0)
        self.add_range_rule("death_rate", 0.0, 1.0)
        self.add_range_rule("population", 1, 1e8)

        # Ecological parameters
        self.add_range_rule("carrying_capacity", 1, 1e8)

        self.add_custom_validator(self._validate_rates)

    @staticmethod
    def _validate_rates(params: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Birth rate should be >= death rate for stability."""
        errors = []
        if "birth_rate" in params and "death_rate" in params:
            if params["birth_rate"] < params["death_rate"] * 0.5:
                errors.append(
                    "Birth rate very low relative to death rate; "
                    "population will decline"
                )
        return len(errors) == 0, errors


class ChemistryValidator(ParameterValidator):
    """Specialized validator for chemical simulations."""

    def __init__(self):
        super().__init__()

        # Temperature in Kelvin
        self.add_range_rule("temperature", 1.0, 5000.0)

        # Pressure in atmospheres
        self.add_range_rule("pressure", 0.001, 10000.0)

        # Concentration in M
        self.add_range_rule("concentration", 0.0, 100.0)

        # Rate constants
        self.add_physical_check("rate_constant", self._check_rate_constant)

    @staticmethod
    def _check_rate_constant(k: float) -> Tuple[bool, str]:
        """Rate constants must be positive."""
        if k < 0:
            return False, "Rate constant must be non-negative"
        return True, "Rate constant valid"


class EconomicsValidator(ParameterValidator):
    """Specialized validator for economic simulations."""

    def __init__(self):
        super().__init__()

        # Economic parameters
        self.add_range_rule("price", 0.0, 1e10)
        self.add_range_rule("quantity", 0, 1e8)
        self.add_range_rule("interest_rate", -1.0, 1.0)
        self.add_range_rule("inflation_rate", -1.0, 1.0)

        # Elasticity bounds
        self.add_range_rule("elasticity", -10.0, 10.0)
