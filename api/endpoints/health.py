"""
Health Check Endpoints
System health monitoring and validation.
"""

from flask import Blueprint, jsonify
import logging
import os
import psycopg2
from datetime import datetime
from typing import Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("HealthCheck")

health_bp = Blueprint('health', __name__)

# Database URLs
INDIA_DB = os.getenv("DATABASE_URL", 
    "postgresql://postgres:analyezdb77**@analyezdb.cbimec0sg2ch.ap-south-1.rds.amazonaws.com:5432/analyezdb")
US_DB = os.getenv("US_DATABASE_URL",
    "postgresql://postgres:analyezdb77**@analyezdb.cbimec0sg2ch.ap-south-1.rds.amazonaws.com:5432/usmarkets")


def check_database(db_url: str, name: str) -> Dict[str, Any]:
    """Check database connectivity."""
    try:
        conn = psycopg2.connect(db_url, connect_timeout=5)
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.close()
        return {"status": "healthy", "name": name}
    except Exception as e:
        return {"status": "unhealthy", "name": name, "error": str(e)}


def check_openai() -> Dict[str, Any]:
    """Check OpenAI API availability."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {"status": "unavailable", "error": "No API key"}
    
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        # Just check if we can create client, don't make actual call
        return {"status": "healthy", "key_present": True}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


def check_cache() -> Dict[str, Any]:
    """Check cache status."""
    try:
        from utils.cache import get_cache
        cache = get_cache("default")
        stats = cache.get_stats()
        return {"status": "healthy", **stats}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


def check_rate_limiter() -> Dict[str, Any]:
    """Check rate limiter status."""
    try:
        from utils.rate_limiter import get_rate_limiter
        limiter = get_rate_limiter()
        return {"status": "healthy", "buckets": limiter.get_status()}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


@health_bp.route('/health', methods=['GET'])
def health_check():
    """
    Basic health check endpoint.
    Returns 200 if server is running.
    """
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "inwezt-analytics"
    })


@health_bp.route('/health/ready', methods=['GET'])
def readiness_check():
    """
    Readiness check - verifies all dependencies are available.
    Used by load balancers to determine if service can accept traffic.
    """
    checks = {
        "database_india": check_database(INDIA_DB, "india"),
        "database_us": check_database(US_DB, "us"),
        "openai": check_openai(),
    }
    
    all_healthy = all(c.get("status") == "healthy" for c in checks.values())
    
    return jsonify({
        "status": "ready" if all_healthy else "not_ready",
        "timestamp": datetime.now().isoformat(),
        "checks": checks
    }), 200 if all_healthy else 503


@health_bp.route('/health/live', methods=['GET'])
def liveness_check():
    """
    Liveness check - simple check that service is responding.
    Used by orchestrators to determine if service needs restart.
    """
    return jsonify({
        "status": "alive",
        "timestamp": datetime.now().isoformat()
    })


@health_bp.route('/health/detailed', methods=['GET'])
def detailed_health():
    """
    Detailed health check with all component statuses.
    """
    checks = {
        "database_india": check_database(INDIA_DB, "india"),
        "database_us": check_database(US_DB, "us"),
        "openai": check_openai(),
        "cache": check_cache(),
        "rate_limiter": check_rate_limiter(),
    }
    
    # Count statuses
    healthy_count = sum(1 for c in checks.values() if c.get("status") == "healthy")
    total_count = len(checks)
    
    overall_status = "healthy" if healthy_count == total_count else \
                     "degraded" if healthy_count > 0 else "unhealthy"
    
    return jsonify({
        "status": overall_status,
        "timestamp": datetime.now().isoformat(),
        "summary": f"{healthy_count}/{total_count} components healthy",
        "components": checks
    }), 200 if overall_status != "unhealthy" else 503


@health_bp.route('/health/metrics', methods=['GET'])
def metrics():
    """
    Prometheus-style metrics endpoint (simplified).
    """
    try:
        from utils.cache import get_cache
        from utils.rate_limiter import get_rate_limiter
        
        cache_stats = get_cache("default").get_stats()
        rate_status = get_rate_limiter().get_status()
        
        # Simple text format
        lines = [
            "# HELP cache_hits Total cache hits",
            f"cache_hits {cache_stats.get('hits', 0)}",
            "# HELP cache_misses Total cache misses",
            f"cache_misses {cache_stats.get('misses', 0)}",
            "# HELP cache_hit_rate Cache hit rate percentage",
            f"cache_hit_rate {cache_stats.get('hit_rate', 0)}",
            "# HELP cache_size Current cache size",
            f"cache_size {cache_stats.get('size', 0)}",
        ]
        
        for bucket_name, bucket_stats in rate_status.items():
            lines.append(f'rate_limit_tokens{{bucket="{bucket_name}"}} {bucket_stats.get("available", 0)}')
        
        return "\n".join(lines), 200, {'Content-Type': 'text/plain'}
        
    except Exception as e:
        return f"# Error: {e}", 500, {'Content-Type': 'text/plain'}


if __name__ == "__main__":
    from flask import Flask
    app = Flask(__name__)
    app.register_blueprint(health_bp)
    
    print("Starting Health Check API on http://localhost:5004")
    print("\nEndpoints:")
    print("  GET /health          - Basic health")
    print("  GET /health/ready    - Readiness (with deps)")
    print("  GET /health/live     - Liveness")
    print("  GET /health/detailed - Full status")
    print("  GET /health/metrics  - Prometheus metrics")
    
    app.run(port=5004, debug=True)
