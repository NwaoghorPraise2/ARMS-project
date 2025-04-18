import json
import time
import logging
from datetime import datetime, date
from pathlib import Path
import os
from typing import Dict, Any, Union
from enum import Enum

def setup_logging(name, level=logging.INFO):
    """Configure and return a logger with the given name and level"""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(level)
    return logger

def get_timestamp():
    """Get current timestamp in seconds"""
    return time.time()

def json_serialize(obj):
    """Custom JSON serializer for objects not serializable by default json code"""
    from types import MappingProxyType
    
    if hasattr(obj, '__dict__'):
        return obj.__dict__
    elif isinstance(obj, MappingProxyType):
        return dict(obj)  # Convert mappingproxy to regular dict
    elif isinstance(obj, Enum):
        return obj.value
    elif isinstance(obj, (set, frozenset)):
        return list(obj)  # Convert sets to lists
    elif isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

def send_message(topic: str, message: Dict[str, Any], producer):
    """Send message to Kafka topic"""
    serialized = json.dumps(message, default=json_serialize)
    producer.produce(topic, value=serialized.encode('utf-8'))
    producer.flush()

def receive_message(consumer, timeout_ms: int = 1000) -> Dict:
    """Receive message from Kafka with timeout"""
    msg = consumer.poll(timeout_ms)
    
    if msg is None:
        return None
        
    if msg.error():
        logging.error(f"Consumer error: {msg.error()}")
        return None
        
    return json.loads(msg.value().decode('utf-8'))