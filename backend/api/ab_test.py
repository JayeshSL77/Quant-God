"""
Analyez - A/B Testing Endpoint for V1 vs V2 Comparison

This module provides an endpoint to compare responses from:
- V1: Current MVP orchestrator (working, operational)
- V2: Experimental institutional-grade orchestrator

Usage: POST /api/v1/ab-test with {"query": "Is HDFC Bank undervalued?"}
Returns both responses for side-by-side comparison.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
import time
import logging

# Import both orchestrators
from backend.agents.orchestrator import Orchestrator
from backend.agents.orchestrator_v2 import OrchestratorV2

logger = logging.getLogger("ABTest")

router = APIRouter()


class ABTestRequest(BaseModel):
    """Request model for A/B testing."""
    query: str
    session_id: Optional[str] = None


class ABTestResponse(BaseModel):
    """Response model showing both V1 and V2 outputs."""
    query: str
    v1_response: str
    v1_time_ms: int
    v1_agents_used: list
    v2_response: str
    v2_time_ms: int
    v2_agents_used: list


# Initialize orchestrators once
_v1_orchestrator = None
_v2_orchestrator = None


def get_v1_orchestrator():
    global _v1_orchestrator
    if _v1_orchestrator is None:
        _v1_orchestrator = Orchestrator()
    return _v1_orchestrator


def get_v2_orchestrator():
    global _v2_orchestrator
    if _v2_orchestrator is None:
        _v2_orchestrator = OrchestratorV2()
    return _v2_orchestrator


@router.post("/ab-test", response_model=ABTestResponse)
async def ab_test_query(request: ABTestRequest):
    """
    Run the same query through both V1 and V2 orchestrators.
    Returns both responses for comparison.
    """
    logger.info(f"[A/B Test] Query: {request.query}")
    
    context = {"session_id": request.session_id or "ab-test"}
    
    # Run V1
    v1_start = time.time()
    try:
        v1_result = get_v1_orchestrator().process(request.query, context.copy())
        v1_response = v1_result.get("response", "V1 Error")
        v1_agents = v1_result.get("agents_used", [])
    except Exception as e:
        logger.error(f"V1 Error: {e}")
        v1_response = f"V1 Error: {str(e)}"
        v1_agents = []
    v1_time = int((time.time() - v1_start) * 1000)
    
    # Run V2
    v2_start = time.time()
    try:
        v2_result = get_v2_orchestrator().process(request.query, context.copy())
        v2_response = v2_result.get("response", "V2 Error")
        v2_agents = v2_result.get("agents_used", [])
    except Exception as e:
        logger.error(f"V2 Error: {e}")
        v2_response = f"V2 Error: {str(e)}"
        v2_agents = []
    v2_time = int((time.time() - v2_start) * 1000)
    
    logger.info(f"[A/B Test] V1: {v1_time}ms, V2: {v2_time}ms")
    
    return ABTestResponse(
        query=request.query,
        v1_response=v1_response,
        v1_time_ms=v1_time,
        v1_agents_used=v1_agents,
        v2_response=v2_response,
        v2_time_ms=v2_time,
        v2_agents_used=v2_agents
    )


@router.get("/ab-test/health")
async def ab_test_health():
    """Health check for A/B test endpoint."""
    return {
        "status": "healthy",
        "v1_ready": get_v1_orchestrator() is not None,
        "v2_ready": get_v2_orchestrator() is not None
    }
