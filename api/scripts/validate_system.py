#!/usr/bin/env python3
"""
Startup Validation Script
Validates all dependencies and configurations before starting the system.
Run this before deploying to catch issues early.
"""

import os
import sys
import json
import logging
from datetime import datetime
from typing import Dict, List, Tuple

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("Validator")

# Colors for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"


def check(condition: bool, name: str, details: str = "") -> Tuple[bool, str]:
    """Helper to format check results."""
    if condition:
        return True, f"{GREEN}✓{RESET} {name}"
    else:
        return False, f"{RED}✗{RESET} {name}: {details}"


def validate_environment() -> List[Tuple[bool, str]]:
    """Check required environment variables."""
    results = []
    
    # Required vars
    required = [
        ("DATABASE_URL", "India database connection"),
        ("US_DATABASE_URL", "US database connection"),
    ]
    
    optional_but_important = [
        ("OPENAI_API_KEY", "Required for AI features"),
        ("MISTRAL_API_KEY", "Fallback LLM provider"),
        ("FMP_API_KEY", "Financial Modeling Prep API"),
    ]
    
    for var, desc in required:
        value = os.getenv(var)
        if value:
            results.append(check(True, f"ENV: {var}"))
        else:
            results.append(check(False, f"ENV: {var}", f"REQUIRED - {desc}"))
    
    for var, desc in optional_but_important:
        value = os.getenv(var)
        if value:
            results.append(check(True, f"ENV: {var}"))
        else:
            results.append((True, f"{YELLOW}!{RESET} ENV: {var} - Optional but recommended: {desc}"))
    
    return results


def validate_database_connections() -> List[Tuple[bool, str]]:
    """Test database connectivity."""
    import psycopg2
    results = []
    
    databases = [
        ("DATABASE_URL", "India (analyezdb)"),
        ("US_DATABASE_URL", "US (usmarkets)"),
    ]
    
    for env_var, name in databases:
        url = os.getenv(env_var)
        if not url:
            results.append(check(False, f"DB: {name}", "No connection URL"))
            continue
        
        try:
            conn = psycopg2.connect(url, connect_timeout=10)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'")
            table_count = cur.fetchone()[0]
            cur.close()
            conn.close()
            results.append(check(True, f"DB: {name} ({table_count} tables)"))
        except Exception as e:
            results.append(check(False, f"DB: {name}", str(e)[:50]))
    
    return results


def validate_required_tables() -> List[Tuple[bool, str]]:
    """Check that required tables exist."""
    import psycopg2
    results = []
    
    # India tables
    india_tables = [
        "annual_reports",
        "concalls", 
        "document_chunks",
    ]
    
    # US tables
    us_tables = [
        "company_metadata",
        "annual_reports_10k",
        "document_chunks",
    ]
    
    # Check India
    try:
        conn = psycopg2.connect(os.getenv("DATABASE_URL"), connect_timeout=10)
        cur = conn.cursor()
        for table in india_tables:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            results.append(check(True, f"TABLE: {table} ({count:,} rows)"))
    except Exception as e:
        results.append(check(False, "India tables", str(e)[:50]))
    
    # Check US
    try:
        conn = psycopg2.connect(os.getenv("US_DATABASE_URL"), connect_timeout=10)
        cur = conn.cursor()
        for table in us_tables:
            try:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                count = cur.fetchone()[0]
                results.append(check(True, f"TABLE: {table} ({count:,} rows)"))
            except:
                results.append(check(False, f"TABLE: {table}", "Does not exist"))
    except Exception as e:
        results.append(check(False, "US tables", str(e)[:50]))
    
    return results


def validate_python_packages() -> List[Tuple[bool, str]]:
    """Check required Python packages."""
    results = []
    
    packages = [
        ("flask", "Web framework"),
        ("psycopg2", "PostgreSQL driver"),
        ("openai", "OpenAI API"),
        ("yfinance", "Yahoo Finance data"),
        ("pandas", "Data analysis"),
        ("requests", "HTTP client"),
    ]
    
    for pkg, desc in packages:
        try:
            __import__(pkg)
            results.append(check(True, f"PKG: {pkg}"))
        except ImportError:
            results.append(check(False, f"PKG: {pkg}", f"pip install {pkg}"))
    
    return results


def validate_file_structure() -> List[Tuple[bool, str]]:
    """Check that key files exist."""
    results = []
    
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    critical_files = [
        "api/analytics.py",
        "api/advanced_analytics.py",
        "api/generate_asset.py",
        "api/health.py",
        "agents/agent_swarm.py",
        "agents/thesis_generator.py",
        "analytics/backtester.py",
        "analytics/risk_metrics.py",
        "utils/resilience.py",
        "utils/cache.py",
    ]
    
    for file_path in critical_files:
        full_path = os.path.join(base_path, file_path)
        exists = os.path.exists(full_path)
        results.append(check(exists, f"FILE: {file_path}"))
    
    return results


def validate_openai() -> List[Tuple[bool, str]]:
    """Test OpenAI API connectivity."""
    results = []
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        results.append((True, f"{YELLOW}!{RESET} OpenAI: No API key (AI features disabled)"))
        return results
    
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        
        # Simple test - just check models list
        models = client.models.list()
        results.append(check(True, "OpenAI: Connected"))
    except Exception as e:
        results.append(check(False, "OpenAI", str(e)[:50]))
    
    return results


def run_validation() -> bool:
    """Run all validation checks."""
    print("\n" + "="*60)
    print(f" INWEZT SYSTEM VALIDATION - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("="*60 + "\n")
    
    all_checks = []
    
    # Environment
    print("📋 Environment Variables:")
    for result in validate_environment():
        print(f"   {result[1]}")
        all_checks.append(result)
    
    # Python packages
    print("\n📦 Python Packages:")
    for result in validate_python_packages():
        print(f"   {result[1]}")
        all_checks.append(result)
    
    # Database
    print("\n🗄️  Database Connections:")
    for result in validate_database_connections():
        print(f"   {result[1]}")
        all_checks.append(result)
    
    # Tables
    print("\n📊 Database Tables:")
    for result in validate_required_tables():
        print(f"   {result[1]}")
        all_checks.append(result)
    
    # Files
    print("\n📁 File Structure:")
    for result in validate_file_structure():
        print(f"   {result[1]}")
        all_checks.append(result)
    
    # OpenAI
    print("\n🤖 AI Services:")
    for result in validate_openai():
        print(f"   {result[1]}")
        all_checks.append(result)
    
    # Summary
    passed = sum(1 for r in all_checks if r[0])
    total = len(all_checks)
    
    print("\n" + "="*60)
    if passed == total:
        print(f" {GREEN}ALL CHECKS PASSED ({passed}/{total}){RESET}")
        print(" System is ready to start!")
    else:
        print(f" {YELLOW}VALIDATION COMPLETE: {passed}/{total} passed{RESET}")
        failed = [r[1] for r in all_checks if not r[0]]
        if failed:
            print(f" {RED}Failed checks:{RESET}")
            for f in failed:
                print(f"   {f}")
    print("="*60 + "\n")
    
    return passed == total


if __name__ == "__main__":
    # Load .env if present
    try:
        from dotenv import load_dotenv
        load_dotenv()
        load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
    except ImportError:
        pass
    
    success = run_validation()
    sys.exit(0 if success else 1)
