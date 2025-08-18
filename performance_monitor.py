#!/usr/bin/env python3
"""
Performance Monitor for JD Parser & Resume Tailoring Pipeline

Tracks and displays performance metrics:
1. Response times for LLM calls
2. PDF compilation times
3. Cache hit rates
4. Task queue statistics
5. Memory usage
6. System resource utilization

Provides both real-time monitoring and historical analytics.
"""

import json
import psutil
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional
import threading

from cache_manager import get_cache_stats
from task_queue import get_queue_stats


class PerformanceMonitor:
    """Real-time performance monitoring system"""

    def __init__(self, history_size: int = 1000):
        self.history_size = history_size
        self.metrics_history = deque(maxlen=history_size)
        self.response_times = defaultdict(list)
        self.error_counts = defaultdict(int)
        self.start_time = datetime.now()
        self.lock = threading.Lock()

        # Start background monitoring
        self.monitoring = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()

    def _monitor_loop(self):
        """Background monitoring loop"""
        while self.monitoring:
            try:
                metrics = self._collect_metrics()
                with self.lock:
                    self.metrics_history.append(metrics)
                time.sleep(5)  # Collect metrics every 5 seconds
            except Exception as e:
                print(f"Performance monitoring error: {e}")
                time.sleep(10)

    def _collect_metrics(self) -> Dict[str, Any]:
        """Collect current system metrics"""
        return {
            'timestamp': datetime.now().isoformat(),
            'system': self._get_system_metrics(),
            'cache': get_cache_stats(),
            'tasks': get_queue_stats(),
            'response_times': dict(self.response_times),
            'errors': dict(self.error_counts)
        }

    def _get_system_metrics(self) -> Dict[str, Any]:
        """Get system resource metrics"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            return {
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'memory_available_gb': memory.available / (1024**3),
                'disk_percent': disk.percent,
                'disk_free_gb': disk.free / (1024**3)
            }
        except Exception as e:
            return {'error': str(e)}

    def record_response_time(self, operation: str, duration: float):
        """Record response time for an operation"""
        with self.lock:
            self.response_times[operation].append(duration)
            # Keep only last 100 measurements
            if len(self.response_times[operation]) > 100:
                self.response_times[operation] = self.response_times[operation][-100:]

    def record_error(self, operation: str, error: str):
        """Record an error occurrence"""
        with self.lock:
            self.error_counts[operation] += 1

    def get_current_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics"""
        with self.lock:
            if not self.metrics_history:
                return self._collect_metrics()
            return self.metrics_history[-1]

    def get_metrics_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get metrics history for the last N hours"""
        cutoff = datetime.now() - timedelta(hours=hours)

        with self.lock:
            return [
                metrics for metrics in self.metrics_history
                if datetime.fromisoformat(metrics['timestamp']) >= cutoff
            ]

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary statistics"""
        with self.lock:
            if not self.metrics_history:
                return {}

            # Calculate averages for response times
            avg_response_times = {}
            for operation, times in self.response_times.items():
                if times:
                    avg_response_times[operation] = {
                        'avg': sum(times) / len(times),
                        'min': min(times),
                        'max': max(times),
                        'count': len(times)
                    }

            # Get recent metrics (last hour)
            recent_metrics = self.get_metrics_history(1)

            # Calculate cache hit rate
            cache_stats = get_cache_stats()
            total_cache_requests = sum(
                stats.get('files', 0) for stats in cache_stats.get('by_type', {}).values()
            )
            cache_hit_rate = 0.0
            if total_cache_requests > 0:
                cache_hit_rate = (
                    total_cache_requests - cache_stats.get('expired_files', 0)) / total_cache_requests

            return {
                'uptime_hours': (datetime.now() - self.start_time).total_seconds() / 3600,
                'avg_response_times': avg_response_times,
                'error_summary': dict(self.error_counts),
                'cache_hit_rate': cache_hit_rate,
                'recent_metrics_count': len(recent_metrics),
                'system_health': self._assess_system_health()
            }

    def _assess_system_health(self) -> Dict[str, str]:
        """Assess overall system health"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()

            health = {
                'cpu': 'good' if cpu_percent < 80 else 'warning' if cpu_percent < 95 else 'critical',
                'memory': 'good' if memory.percent < 80 else 'warning' if memory.percent < 95 else 'critical',
                'overall': 'good'
            }

            # Determine overall health
            if 'critical' in health.values():
                health['overall'] = 'critical'
            elif 'warning' in health.values():
                health['overall'] = 'warning'

            return health
        except Exception:
            return {'overall': 'unknown'}

    def export_metrics(self, file_path: str):
        """Export metrics to JSON file"""
        with self.lock:
            metrics_data = {
                'export_timestamp': datetime.now().isoformat(),
                'history': list(self.metrics_history),
                'response_times': dict(self.response_times),
                'errors': dict(self.error_counts)
            }

        with open(file_path, 'w') as f:
            json.dump(metrics_data, f, indent=2)

    def shutdown(self):
        """Shutdown the performance monitor"""
        self.monitoring = False
        if self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)


# Global performance monitor instance
_performance_monitor = None


def get_performance_monitor() -> PerformanceMonitor:
    """Get the global performance monitor instance"""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
    return _performance_monitor


def record_operation_time(operation: str, duration: float):
    """Record operation duration"""
    monitor = get_performance_monitor()
    monitor.record_response_time(operation, duration)


def record_operation_error(operation: str, error: str):
    """Record operation error"""
    monitor = get_performance_monitor()
    monitor.record_error(operation, error)


def get_performance_dashboard_data() -> Dict[str, Any]:
    """Get data for performance dashboard"""
    monitor = get_performance_monitor()

    return {
        'current': monitor.get_current_metrics(),
        'summary': monitor.get_performance_summary(),
        'recent_history': monitor.get_metrics_history(1)  # Last hour
    }


def create_performance_report() -> Dict[str, Any]:
    """Create a comprehensive performance report"""
    monitor = get_performance_monitor()

    # Get 24-hour history
    history = monitor.get_metrics_history(24)

    # Calculate trends
    if len(history) >= 2:
        first_metrics = history[0]
        last_metrics = history[-1]

        # Calculate CPU trend
        cpu_trend = 0
        if 'system' in first_metrics and 'system' in last_metrics:
            first_cpu = first_metrics['system'].get('cpu_percent', 0)
            last_cpu = last_metrics['system'].get('cpu_percent', 0)
            cpu_trend = last_cpu - first_cpu

        # Calculate memory trend
        memory_trend = 0
        if 'system' in first_metrics and 'system' in last_metrics:
            first_mem = first_metrics['system'].get('memory_percent', 0)
            last_mem = last_metrics['system'].get('memory_percent', 0)
            memory_trend = last_mem - first_mem
    else:
        cpu_trend = memory_trend = 0

    return {
        'report_timestamp': datetime.now().isoformat(),
        'summary': monitor.get_performance_summary(),
        'trends': {
            'cpu_trend': cpu_trend,
            'memory_trend': memory_trend
        },
        'recommendations': _generate_recommendations(monitor.get_performance_summary())
    }


def _generate_recommendations(summary: Dict[str, Any]) -> List[str]:
    """Generate performance recommendations"""
    recommendations = []

    # Check response times
    for operation, times in summary.get('avg_response_times', {}).items():
        avg_time = times.get('avg', 0)
        if avg_time > 30:  # More than 30 seconds
            recommendations.append(
                f"Consider optimizing {operation} (avg: {avg_time:.1f}s)")

    # Check cache hit rate
    cache_hit_rate = summary.get('cache_hit_rate', 0)
    if cache_hit_rate < 0.5:  # Less than 50%
        recommendations.append(
            "Low cache hit rate - consider expanding cache coverage")

    # Check error rates
    total_errors = sum(summary.get('error_summary', {}).values())
    if total_errors > 10:
        recommendations.append("High error rate detected - review error logs")

    # Check system resources
    if not recommendations:
        recommendations.append(
            "System performance is within normal parameters")

    return recommendations


def cleanup_performance_data():
    """Clean up old performance data"""
    monitor = get_performance_monitor()
    # This is handled automatically by the deque maxlen
    pass
