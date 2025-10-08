#!/usr/bin/env python3
"""
Test script for image upload feature via WebSocket
"""

import asyncio
import websockets
import json
import base64
from datetime import datetime
import uuid

# WebSocket endpoint
WEBSOCKET_URL = "wss://i75sc6a4ul.execute-api.ap-southeast-1.amazonaws.com/prod"

def encode_image(image_path):
    """Encode image to base64"""
    with open(image_path, 'rb') as f:
        return base64.b64encode(f.read()).decode('utf-8')

async def test_image_upload(image_path, message):
    """Test sending image with message"""
    session_id = str(uuid.uuid4())
    
    print(f"🔌 Connecting to WebSocket...")
    print(f"📍 URL: {WEBSOCKET_URL}")
    print(f"🆔 Session ID: {session_id}\n")
    
    async with websockets.connect(WEBSOCKET_URL) as websocket:
        print("✅ Connected!\n")
        
        # Encode image
        print(f"📸 Encoding image: {image_path}")
        image_data = encode_image(image_path)
        print(f"✅ Image encoded ({len(image_data)} bytes)\n")
        
        # Send message with image
        payload = {
            "message": message,
            "sessionId": session_id,
            "timestamp": datetime.utcnow().isoformat(),
            "hasImage": True,
            "imageData": image_data
        }
        
        print(f"📤 Sending message: '{message}'")
        print(f"🖼️  With image attached\n")
        
        await websocket.send(json.dumps(payload))
        
        # Wait for responses
        print("⏳ Waiting for responses...\n")
        print("-" * 60)
        
        try:
            while True:
                response = await asyncio.wait_for(websocket.recv(), timeout=30)
                data = json.loads(response)
                
                print(f"\n📨 Response received:")
                print(f"   Type: {data.get('type')}")
                print(f"   Content: {data.get('content', '')[:200]}")
                
                if data.get('workflowType'):
                    print(f"   Workflow: {data.get('workflowType')}")
                if data.get('ticket_number'):
                    print(f"   🎫 Ticket: {data.get('ticket_number')}")
                
                print("-" * 60)
                
                # Stop if workflow complete
                if data.get('type') == 'workflow_complete':
                    print("\n✅ Workflow completed!")
                    break
                    
        except asyncio.TimeoutError:
            print("\n⏱️  Timeout - no more responses")

async def test_text_only(message):
    """Test sending text without image"""
    session_id = str(uuid.uuid4())
    
    print(f"🔌 Connecting to WebSocket...")
    print(f"🆔 Session ID: {session_id}\n")
    
    async with websockets.connect(WEBSOCKET_URL) as websocket:
        print("✅ Connected!\n")
        
        payload = {
            "message": message,
            "sessionId": session_id,
            "timestamp": datetime.utcnow().isoformat(),
            "hasImage": False
        }
        
        print(f"📤 Sending message: '{message}'\n")
        await websocket.send(json.dumps(payload))
        
        print("⏳ Waiting for response...\n")
        print("-" * 60)
        
        try:
            response = await asyncio.wait_for(websocket.recv(), timeout=30)
            data = json.loads(response)
            
            print(f"\n📨 Response:")
            print(f"   Type: {data.get('type')}")
            print(f"   Content: {data.get('content', '')}")
            print("-" * 60)
            
        except asyncio.TimeoutError:
            print("\n⏱️  Timeout")

def main():
    """Main test menu"""
    print("\n" + "="*60)
    print("🧪 CHATBOT IMAGE UPLOAD TEST")
    print("="*60 + "\n")
    
    print("Choose test:")
    print("1. Test with image (incident report)")
    print("2. Test text only (general question)")
    print("3. Exit\n")
    
    choice = input("Enter choice (1-3): ").strip()
    
    if choice == "1":
        image_path = input("\nEnter image path (e.g., test_image.jpg): ").strip()
        message = input("Enter message (e.g., 'Report fallen tree blocking road'): ").strip()
        
        if not message:
            message = "Report incident - fallen tree blocking road"
        
        print("\n" + "="*60)
        asyncio.run(test_image_upload(image_path, message))
        
    elif choice == "2":
        message = input("\nEnter message: ").strip()
        
        if not message:
            message = "What is MBPP?"
        
        print("\n" + "="*60)
        asyncio.run(test_text_only(message))
        
    else:
        print("\n👋 Goodbye!")
        return
    
    print("\n" + "="*60)
    print("✅ Test completed!")
    print("="*60 + "\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
