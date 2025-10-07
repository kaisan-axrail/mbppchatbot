"""
Enhanced circuit breaker implementation for service-specific failure handling.

This module provides comprehensive circuit breaker functionality with:
- Service-specific circuit breakers for Bedrock and DynamoDB
- Configurable failure thresholds and recovery timeouts
- Circuit breaker reset mechanism after successful operations
- Circuit breaker status reporting for monitoring
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, asdict
import threading
import json

# Configure logging
logger = logging.getLogger(__name__)


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "CLOSED"      # Normal operation
    OPEN = "OPEN"          # Circuit is open, requests fail fast
    HALF_OPEN = "HALF_OPEN"  # Testing if service has recovered


class ServiceType(Enum):
    """Supported service types for circuit breakers."""
    BEDROCK = "bedrock"
    DYNAMODB = "dynamodb"
    ANALYTICS = "analytics"
    MCP = "mcp"
    OPENSEARCH = "opensearch"


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""
    failure_threshold: int = 5
    recovery_timeout: int = 30  # seconds
    success_threshold: int = 2  # successful calls needed to close from half-open
    monitoring_window: int = 300  # seconds to track failure rate
    max_failure_rate: float = 0.5  # 50% failure rate threshold


@dataclass
class CircuitBreakerMetrics:
    """Metrics for circuit breaker monitoring."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    state_change_time: Optional[datetime] = None
    total_state_changes: int = 0


class EnhancedCircuitBreaker:
    """
    Enhanced circuit breaker with comprehensive monitoring and configuration.
    
    Features:
    - Configurable failure thresholds and timeouts
    - Success-based recovery mechanism
    - Detailed metrics and monitoring
    - Thread-safe operations
    - State change notifications
    """
    
    def __init__(
        self,
        service_name: str,
        config: Optional[CircuitBreakerConfig] = None
    ):
        """
        Initialize circuit breaker for a specific service.
        
        Args:
            service_name: Name of the service this circuit breaker protects
            config: Circuit breaker configuration
        """
        self.service_name = service_name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitBreakerState.CLOSED
        self.metrics = CircuitBreakerMetrics()
        self._lock = threading.RLock()
        self._state_change_callbacks: list[Callable] = []
        
        # Initialize state change time
        self.metrics.state_change_time = datetime.now(timezone.utc)
        
        logger.info(
            f"Circuit breaker initialized for {service_name}",
            extra={
                "service": service_name,
                "config": asdict(self.config),
                "initial_state": self.state.value
            }
        )
    
    def is_request_allowed(self) -> bool:
        """
        Check if a request should be allowed through the circuit breaker.
        
        Returns:
            True if request is allowed, False if circuit is open
        """
        with self._lock:
            if self.state == CircuitBreakerState.CLOSED:
                return True
            elif self.state == CircuitBreakerState.OPEN:
                # Check if recovery timeout has passed
                if self._should_attempt_reset():
                    self._transition_to_half_open()
                    return True
                return False
            elif self.state == CircuitBreakerState.HALF_OPEN:
                # Allow limited requests in half-open state
                return True
            
            return False
    
    def record_success(self) -> None:
        """Record a successful operation."""
        with self._lock:
            now = datetime.now(timezone.utc)
            
            self.metrics.total_requests += 1
            self.metrics.successful_requests += 1
            self.metrics.consecutive_successes += 1
            self.metrics.consecutive_failures = 0
            self.metrics.last_success_time = now
            
            # Handle state transitions based on success
            if self.state == CircuitBreakerState.HALF_OPEN:
                if self.metrics.consecutive_successes >= self.config.success_threshold:
                    self._transition_to_closed()
            elif self.state == CircuitBreakerState.OPEN:
                # Shouldn't happen, but handle gracefully
                logger.warning(f"Success recorded while circuit breaker is OPEN for {self.service_name}")
            
            logger.debug(
                f"Success recorded for {self.service_name}",
                extra={
                    "service": self.service_name,
                    "state": self.state.value,
                    "consecutive_successes": self.metrics.consecutive_successes,
                    "total_requests": self.metrics.total_requests
                }
            )
    
    def record_failure(self, error: Exception) -> None:
        """
        Record a failed operation.
        
        Args:
            error: The exception that caused the failure
        """
        with self._lock:
            now = datetime.now(timezone.utc)
            
            self.metrics.total_requests += 1
            self.metrics.failed_requests += 1
            self.metrics.consecutive_failures += 1
            self.metrics.consecutive_successes = 0
            self.metrics.last_failure_time = now
            
            # Handle state transitions based on failure
            if self.state == CircuitBreakerState.CLOSED:
                if self.metrics.consecutive_failures >= self.config.failure_threshold:
                    self._transition_to_open()
            elif self.state == CircuitBreakerState.HALF_OPEN:
                # Any failure in half-open state should open the circuit
                self._transition_to_open()
            
            logger.warning(
                f"Failure recorded for {self.service_name}",
                extra={
                    "service": self.service_name,
                    "state": self.state.value,
                    "consecutive_failures": self.metrics.consecutive_failures,
                    "error_type": type(error).__name__,
                    "error_message": str(error),
                    "total_requests": self.metrics.total_requests
                }
            )
    
    def force_open(self, reason: str = "Manual intervention") -> None:
        """
        Force the circuit breaker to open state.
        
        Args:
            reason: Reason for forcing the circuit open
        """
        with self._lock:
            if self.state != CircuitBreakerState.OPEN:
                logger.warning(
                    f"Circuit breaker forced open for {self.service_name}",
                    extra={
                        "service": self.service_name,
                        "reason": reason,
                        "previous_state": self.state.value
                    }
                )
                self._transition_to_open()
    
    def force_close(self, reason: str = "Manual intervention") -> None:
        """
        Force the circuit breaker to closed state.
        
        Args:
            reason: Reason for forcing the circuit closed
        """
        with self._lock:
            if self.state != CircuitBreakerState.CLOSED:
                logger.info(
                    f"Circuit breaker forced closed for {self.service_name}",
                    extra={
                        "service": self.service_name,
                        "reason": reason,
                        "previous_state": self.state.value
                    }
                )
                self._reset_metrics()
                self._transition_to_closed()
    
    def reset(self) -> None:
        """Reset the circuit breaker to initial state."""
        with self._lock:
            logger.info(f"Resetting circuit breaker for {self.service_name}")
            self._reset_metrics()
            self._transition_to_closed()
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get comprehensive status information about the circuit breaker.
        
        Returns:
            Dictionary containing circuit breaker status and metrics
        """
        with self._lock:
            failure_rate = (
                self.metrics.failed_requests / self.metrics.total_requests
                if self.metrics.total_requests > 0 else 0.0
            )
            
            success_rate = (
                self.metrics.successful_requests / self.metrics.total_requests
                if self.metrics.total_requests > 0 else 0.0
            )
            
            time_since_last_failure = None
            if self.metrics.last_failure_time:
                time_since_last_failure = (
                    datetime.now(timezone.utc) - self.metrics.last_failure_time
                ).total_seconds()
            
            time_since_last_success = None
            if self.metrics.last_success_time:
                time_since_last_success = (
                    datetime.now(timezone.utc) - self.metrics.last_success_time
                ).total_seconds()
            
            time_in_current_state = None
            if self.metrics.state_change_time:
                time_in_current_state = (
                    datetime.now(timezone.utc) - self.metrics.state_change_time
                ).total_seconds()
            
            return {
                "service_name": self.service_name,
                "state": self.state.value,
                "is_request_allowed": self.is_request_allowed(),
                "config": asdict(self.config),
                "metrics": {
                    "total_requests": self.metrics.total_requests,
                    "successful_requests": self.metrics.successful_requests,
                    "failed_requests": self.metrics.failed_requests,
                    "consecutive_failures": self.metrics.consecutive_failures,
                    "consecutive_successes": self.metrics.consecutive_successes,
                    "failure_rate": failure_rate,
                    "success_rate": success_rate,
                    "total_state_changes": self.metrics.total_state_changes,
                    "time_since_last_failure_seconds": time_since_last_failure,
                    "time_since_last_success_seconds": time_since_last_success,
                    "time_in_current_state_seconds": time_in_current_state
                },
                "timestamps": {
                    "last_failure_time": self.metrics.last_failure_time.isoformat() if self.metrics.last_failure_time else None,
                    "last_success_time": self.metrics.last_success_time.isoformat() if self.metrics.last_success_time else None,
                    "state_change_time": self.metrics.state_change_time.isoformat() if self.metrics.state_change_time else None,
                    "current_time": datetime.now(timezone.utc).isoformat()
                }
            }
    
    def add_state_change_callback(self, callback: Callable[[str, str, str], None]) -> None:
        """
        Add a callback to be notified of state changes.
        
        Args:
            callback: Function that takes (service_name, old_state, new_state)
        """
        self._state_change_callbacks.append(callback)
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset from OPEN state."""
        if not self.metrics.last_failure_time:
            return True
        
        time_since_failure = (
            datetime.now(timezone.utc) - self.metrics.last_failure_time
        ).total_seconds()
        
        return time_since_failure >= self.config.recovery_timeout
    
    def _transition_to_open(self) -> None:
        """Transition circuit breaker to OPEN state."""
        old_state = self.state.value
        self.state = CircuitBreakerState.OPEN
        self.metrics.state_change_time = datetime.now(timezone.utc)
        self.metrics.total_state_changes += 1
        
        logger.warning(
            f"Circuit breaker opened for {self.service_name}",
            extra={
                "service": self.service_name,
                "old_state": old_state,
                "new_state": self.state.value,
                "consecutive_failures": self.metrics.consecutive_failures,
                "failure_threshold": self.config.failure_threshold
            }
        )
        
        self._notify_state_change(old_state, self.state.value)
    
    def _transition_to_half_open(self) -> None:
        """Transition circuit breaker to HALF_OPEN state."""
        old_state = self.state.value
        self.state = CircuitBreakerState.HALF_OPEN
        self.metrics.state_change_time = datetime.now(timezone.utc)
        self.metrics.total_state_changes += 1
        self.metrics.consecutive_successes = 0  # Reset for half-open testing
        
        logger.info(
            f"Circuit breaker transitioning to half-open for {self.service_name}",
            extra={
                "service": self.service_name,
                "old_state": old_state,
                "new_state": self.state.value,
                "recovery_timeout": self.config.recovery_timeout
            }
        )
        
        self._notify_state_change(old_state, self.state.value)
    
    def _transition_to_closed(self) -> None:
        """Transition circuit breaker to CLOSED state."""
        old_state = self.state.value
        self.state = CircuitBreakerState.CLOSED
        self.metrics.state_change_time = datetime.now(timezone.utc)
        self.metrics.total_state_changes += 1
        
        logger.info(
            f"Circuit breaker closed for {self.service_name}",
            extra={
                "service": self.service_name,
                "old_state": old_state,
                "new_state": self.state.value,
                "consecutive_successes": self.metrics.consecutive_successes,
                "success_threshold": self.config.success_threshold
            }
        )
        
        self._notify_state_change(old_state, self.state.value)
    
    def _reset_metrics(self) -> None:
        """Reset circuit breaker metrics."""
        self.metrics.consecutive_failures = 0
        self.metrics.consecutive_successes = 0
    
    def _notify_state_change(self, old_state: str, new_state: str) -> None:
        """Notify registered callbacks of state changes."""
        for callback in self._state_change_callbacks:
            try:
                callback(self.service_name, old_state, new_state)
            except Exception as e:
                logger.error(f"Error in state change callback: {e}")


class CircuitBreakerManager:
    """
    Manager for service-specific circuit breakers with centralized configuration.
    """
    
    def __init__(self):
        """Initialize circuit breaker manager."""
        self._circuit_breakers: Dict[str, EnhancedCircuitBreaker] = {}
        self._lock = threading.RLock()
        self._load_configurations()
        
        logger.info("Circuit breaker manager initialized")
    
    def _load_configurations(self) -> None:
        """Load circuit breaker configurations from environment variables."""
        # Bedrock circuit breaker configuration
        bedrock_config = CircuitBreakerConfig(
            failure_threshold=int(os.environ.get('BEDROCK_CIRCUIT_BREAKER_THRESHOLD', '5')),
            recovery_timeout=int(os.environ.get('BEDROCK_CIRCUIT_BREAKER_TIMEOUT', '30')),
            success_threshold=int(os.environ.get('BEDROCK_CIRCUIT_BREAKER_SUCCESS_THRESHOLD', '2')),
            monitoring_window=int(os.environ.get('BEDROCK_CIRCUIT_BREAKER_MONITORING_WINDOW', '300')),
            max_failure_rate=float(os.environ.get('BEDROCK_CIRCUIT_BREAKER_MAX_FAILURE_RATE', '0.5'))
        )
        
        # DynamoDB circuit breaker configuration
        dynamodb_config = CircuitBreakerConfig(
            failure_threshold=int(os.environ.get('DYNAMODB_CIRCUIT_BREAKER_THRESHOLD', '3')),
            recovery_timeout=int(os.environ.get('DYNAMODB_CIRCUIT_BREAKER_TIMEOUT', '10')),
            success_threshold=int(os.environ.get('DYNAMODB_CIRCUIT_BREAKER_SUCCESS_THRESHOLD', '2')),
            monitoring_window=int(os.environ.get('DYNAMODB_CIRCUIT_BREAKER_MONITORING_WINDOW', '300')),
            max_failure_rate=float(os.environ.get('DYNAMODB_CIRCUIT_BREAKER_MAX_FAILURE_RATE', '0.3'))
        )
        
        # Analytics circuit breaker configuration (more lenient)
        analytics_config = CircuitBreakerConfig(
            failure_threshold=int(os.environ.get('ANALYTICS_CIRCUIT_BREAKER_THRESHOLD', '10')),
            recovery_timeout=int(os.environ.get('ANALYTICS_CIRCUIT_BREAKER_TIMEOUT', '60')),
            success_threshold=int(os.environ.get('ANALYTICS_CIRCUIT_BREAKER_SUCCESS_THRESHOLD', '3')),
            monitoring_window=int(os.environ.get('ANALYTICS_CIRCUIT_BREAKER_MONITORING_WINDOW', '600')),
            max_failure_rate=float(os.environ.get('ANALYTICS_CIRCUIT_BREAKER_MAX_FAILURE_RATE', '0.7'))
        )
        
        # Store configurations
        self._service_configs = {
            ServiceType.BEDROCK.value: bedrock_config,
            ServiceType.DYNAMODB.value: dynamodb_config,
            ServiceType.ANALYTICS.value: analytics_config,
        }
        
        logger.info(
            "Circuit breaker configurations loaded",
            extra={"configurations": {k: asdict(v) for k, v in self._service_configs.items()}}
        )
    
    def get_circuit_breaker(self, service_name: str) -> EnhancedCircuitBreaker:
        """
        Get or create circuit breaker for a service.
        
        Args:
            service_name: Name of the service
            
        Returns:
            Circuit breaker instance for the service
        """
        with self._lock:
            if service_name not in self._circuit_breakers:
                config = self._service_configs.get(service_name)
                self._circuit_breakers[service_name] = EnhancedCircuitBreaker(
                    service_name, config
                )
                
                # Add logging callback for state changes
                self._circuit_breakers[service_name].add_state_change_callback(
                    self._log_state_change
                )
            
            return self._circuit_breakers[service_name]
    
    def get_all_statuses(self) -> Dict[str, Any]:
        """
        Get status of all circuit breakers.
        
        Returns:
            Dictionary with status of all circuit breakers
        """
        with self._lock:
            statuses = {}
            for service_name, circuit_breaker in self._circuit_breakers.items():
                statuses[service_name] = circuit_breaker.get_status()
            
            # Add overall health summary
            total_services = len(statuses)
            healthy_services = sum(
                1 for status in statuses.values()
                if status["state"] == CircuitBreakerState.CLOSED.value
            )
            
            return {
                "circuit_breakers": statuses,
                "summary": {
                    "total_services": total_services,
                    "healthy_services": healthy_services,
                    "unhealthy_services": total_services - healthy_services,
                    "overall_health_percentage": (healthy_services / total_services * 100) if total_services > 0 else 100,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }
    
    def reset_all(self) -> None:
        """Reset all circuit breakers."""
        with self._lock:
            for circuit_breaker in self._circuit_breakers.values():
                circuit_breaker.reset()
            
            logger.info("All circuit breakers reset")
    
    def reset_service(self, service_name: str) -> bool:
        """
        Reset circuit breaker for a specific service.
        
        Args:
            service_name: Name of the service to reset
            
        Returns:
            True if service was found and reset, False otherwise
        """
        with self._lock:
            if service_name in self._circuit_breakers:
                self._circuit_breakers[service_name].reset()
                logger.info(f"Circuit breaker reset for service: {service_name}")
                return True
            
            logger.warning(f"Circuit breaker not found for service: {service_name}")
            return False
    
    def _log_state_change(self, service_name: str, old_state: str, new_state: str) -> None:
        """Log circuit breaker state changes."""
        logger.info(
            f"Circuit breaker state change for {service_name}: {old_state} -> {new_state}",
            extra={
                "service": service_name,
                "old_state": old_state,
                "new_state": new_state,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )


# Global circuit breaker manager instance
circuit_breaker_manager = CircuitBreakerManager()


def get_circuit_breaker(service_name: str) -> EnhancedCircuitBreaker:
    """
    Get circuit breaker for a service.
    
    Args:
        service_name: Name of the service
        
    Returns:
        Circuit breaker instance
    """
    return circuit_breaker_manager.get_circuit_breaker(service_name)


def get_all_circuit_breaker_statuses() -> Dict[str, Any]:
    """
    Get status of all circuit breakers.
    
    Returns:
        Dictionary with all circuit breaker statuses
    """
    return circuit_breaker_manager.get_all_statuses()


def reset_circuit_breaker(service_name: str) -> bool:
    """
    Reset circuit breaker for a service.
    
    Args:
        service_name: Name of the service
        
    Returns:
        True if reset successful, False otherwise
    """
    return circuit_breaker_manager.reset_service(service_name)


def reset_all_circuit_breakers() -> None:
    """Reset all circuit breakers."""
    circuit_breaker_manager.reset_all()