import os
import json
import logging
import requests
from flask import Flask, jsonify, request

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('ARMS-API')

app = Flask(__name__)

CLASSIFIER_HOST = os.environ.get("CLASSIFIER_HOST", "classifier")
STRATEGY_SELECTOR_HOST = os.environ.get("STRATEGY_SELECTOR_HOST", "strategy-selector")

@app.route('/api/recommend', methods=['GET'])
def recommend_strategy():
    """Recommend recovery strategy based on current metrics"""
    try:
        # Get the strategy from the strategy selector
        response = requests.get(f"http://{STRATEGY_SELECTOR_HOST}:5000/api/strategy")
        
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({"error": f"Strategy selector returned: {response.status_code}"}), 500
    
    except Exception as e:
        logger.error(f"Error in recommendation: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/recommend/manual', methods=['POST'])
def manual_recommendation():
    """Get recommendation based on manually specified workload type"""
    try:
        data = request.json
        
        if not data or 'workload_type' not in data:
            return jsonify({'error': 'workload_type is required'}), 400
        
        # Pass the request to the strategy selector
        response = requests.post(
            f"http://{STRATEGY_SELECTOR_HOST}:5000/api/strategy/manual",
            json=data
        )
        
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({"error": f"Strategy selector returned: {response.status_code}"}), 500
    
    except Exception as e:
        logger.error(f"Error in manual recommendation: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
