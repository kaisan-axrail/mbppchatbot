#!/usr/bin/env python3
"""
Test script for MBPP WebSocket Chatbot
"""
import asyncio
import websockets
import json
from datetime import datetime

WEBSOCKET_URL = "wss://i75sc6a4ul.execute-api.ap-southeast-1.amazonaws.com/prod"

async def test_chatbot():
    """Test the MBPP chatbot with different scenarios"""
    
    print(f"Connecting to {WEBSOCKET_URL}...")
    
    async with websockets.connect(WEBSOCKET_URL) as websocket:
        print("✅ Connected successfully!\n")
        
        # Test 1: General question
        print("Test 1: General Question")
        message = {
            "action": "sendMessage",
            "sessionId": "test-session-123",
            "message": "Hello, what can you help me with?",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        await websocket.send(json.dumps(message))
        response = await websocket.recv()
        print(f"Response: {response}\n")
        
        # Test 2: Complaint workflow
        print("Test 2: Complaint Workflow")
        message = {
            "action": "sendMessage",
            "sessionId": "test-session-456",
            "message": "I want to file a complaint about poor service",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        await websocket.send(json.dumps(message))
        response = await websocket.recv()
        print(f"Response: {response}\n")
        
        # Test 3: Incident report
        print("Test 3: Incident Report")
        message = {
            "action": "sendMessage",
            "sessionId": "test-session-789",
            "message": "I need to report an incident at the station",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        await websocket.send(json.dumps(message))
        response = await websocket.recv()
        print(f"Response: {response}\n")
        
        print("✅ All tests completed!")

if __name__ == "__main__":
    try:
        asyncio.run(test_chatbot())
    except Exception as e:
        print(f"❌ Error: {e}")
