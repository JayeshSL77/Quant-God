"""
Generate Asset API Endpoint
REST API for creating custom stock indices (Generated Assets).
"""

from flask import Blueprint, request, jsonify
import logging
import sys
import os

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.index_builder import IndexBuilder, GeneratedIndex
from agents.metric_extractor import MetricExtractor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("GenerateAssetAPI")

# Create Blueprint
generate_asset_bp = Blueprint('generate_asset', __name__)


@generate_asset_bp.route('/api/generate-asset', methods=['POST'])
def generate_asset():
    """
    Generate a custom stock index from a natural language query.
    
    Request body:
    {
        "query": "AI-focused companies with positive cash flow",
        "market": "india" | "us" | "both",
        "max_stocks": 15
    }
    
    Response:
    {
        "success": true,
        "index": {
            "name": "Custom Index: AI-focused companies...",
            "stocks": [...],
            "average_score": 82.5,
            ...
        }
    }
    """
    try:
        data = request.get_json()
        
        if not data or 'query' not in data:
            return jsonify({
                "success": False,
                "error": "Missing 'query' in request body"
            }), 400
        
        query = data['query']
        market = data.get('market', 'india')
        max_stocks = data.get('max_stocks', 15)
        
        logger.info(f"Generating asset for: {query} (market={market})")
        
        # Build index
        builder = IndexBuilder(market=market)
        index = builder.build_index(query, max_stocks=max_stocks)
        
        # Convert to response format
        response = {
            "success": True,
            "index": {
                "name": index.name,
                "description": index.description,
                "query": index.query,
                "total_stocks": index.total_stocks,
                "average_score": index.average_score,
                "created_at": index.created_at,
                "stocks": [
                    {
                        "rank": i + 1,
                        "symbol": s.symbol,
                        "company_name": s.company_name,
                        "relevance_score": s.relevance_score,
                        "weight": s.weight,
                        "justification": s.justification,
                        "market": s.market
                    }
                    for i, s in enumerate(index.stocks)
                ]
            }
        }
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error generating asset: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@generate_asset_bp.route('/api/generate-asset/themes', methods=['GET'])
def get_themes():
    """Get list of available themes for filtering."""
    themes = [
        {"id": "ai_exposure", "name": "Artificial Intelligence", "description": "AI, ML, GenAI exposure"},
        {"id": "cloud_computing", "name": "Cloud Computing", "description": "Cloud services, SaaS"},
        {"id": "ev_exposure", "name": "Electric Vehicles", "description": "EV, batteries, charging"},
        {"id": "renewable_energy", "name": "Renewable Energy", "description": "Solar, wind, clean tech"},
        {"id": "healthcare_innovation", "name": "Healthcare Innovation", "description": "Biotech, medical devices"},
        {"id": "digital_transformation", "name": "Digital Transformation", "description": "Digitization, automation"},
        {"id": "ecommerce", "name": "E-Commerce", "description": "Online retail, digital commerce"},
        {"id": "high_roic", "name": "High ROIC", "description": "Capital-efficient compounders"},
        {"id": "cash_generators", "name": "Cash Generators", "description": "Strong operating cash flow"},
        {"id": "low_debt", "name": "Low Debt", "description": "Conservative balance sheets"},
    ]
    return jsonify({"themes": themes})


@generate_asset_bp.route('/api/generate-asset/examples', methods=['GET'])
def get_examples():
    """Get example queries to help users."""
    examples = [
        "AI-focused companies with positive operating cash flow",
        "High ROIC companies with low debt in the technology sector",
        "EV and battery exposure with revenue growth above 20%",
        "Cloud computing leaders with strong profit margins",
        "Healthcare innovation companies with consistent earnings growth",
        "Dividend paying companies with low volatility",
        "Small cap growth stocks with high insider ownership",
        "Export-oriented companies benefiting from weak rupee",
    ]
    return jsonify({"examples": examples})


@generate_asset_bp.route('/api/extract-metrics', methods=['POST'])
def extract_metrics():
    """
    Extract financial metrics from text (for debugging/testing).
    
    Request body:
    {
        "text": "Annual report excerpt...",
        "extract_themes": true
    }
    """
    try:
        data = request.get_json()
        
        if not data or 'text' not in data:
            return jsonify({
                "success": False,
                "error": "Missing 'text' in request body"
            }), 400
        
        text = data['text']
        extract_themes = data.get('extract_themes', False)
        
        extractor = MetricExtractor()
        
        result = {
            "success": True,
            "metrics": extractor.extract_metrics(text)
        }
        
        if extract_themes:
            result["themes"] = extractor.extract_themes(text)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error extracting metrics: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# Standalone test server
if __name__ == "__main__":
    from flask import Flask
    app = Flask(__name__)
    app.register_blueprint(generate_asset_bp)
    
    print("Starting Generate Asset API on http://localhost:5001")
    print("\nExample request:")
    print('''curl -X POST http://localhost:5001/api/generate-asset \\
  -H "Content-Type: application/json" \\
  -d '{"query": "AI companies with strong cash flow", "market": "india"}'
''')
    
    app.run(port=5001, debug=True)
