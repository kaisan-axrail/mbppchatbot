#!/usr/bin/env python3
"""
Automated test for all 3 MBPP workflows
"""

import asyncio
import websockets
import json
import base64
from datetime import datetime
import uuid
import time

WEBSOCKET_URL = "wss://i75sc6a4ul.execute-api.ap-southeast-1.amazonaws.com/prod"

def create_test_image():
    """Create a small test image (1x1 red pixel PNG)"""
    # Minimal PNG: 1x1 red pixel
    png_data = (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
        b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf'
        b'\xc0\x00\x00\x00\x03\x00\x01\x00\x18\xdd\x8d\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
    )
    return base64.b64encode(png_data).decode('utf-8')

async def send_and_receive(websocket, message, session_id, has_image=False, image_data=None):
    """Send message and collect responses"""
    payload = {
        "message": message,
        "sessionId": session_id,
        "timestamp": datetime.utcnow().isoformat(),
        "hasImage": has_image
    }
    
    if has_image and image_data:
        payload["imageData"] = image_data
    
    await websocket.send(json.dumps(payload))
    print(f"   📤 Sent: {message[:50]}...")
    
    # Collect responses for 5 seconds
    responses = []
    try:
        while True:
            response = await asyncio.wait_for(websocket.recv(), timeout=5)
            data = json.loads(response)
            responses.append(data)
            
            content = data.get('content', '')[:100]
            print(f"   📨 Bot: {content}...")
            
            if data.get('type') == 'workflow_complete':
                break
    except asyncio.TimeoutError:
        pass
    
    return responses

async def test_workflow_1_complaint():
    """Test Workflow 1: Service/System Complaint"""
    print("\n" + "="*70)
    print("🧪 TEST 1: SERVICE/SYSTEM COMPLAINT WORKFLOW")
    print("="*70)
    
    session_id = str(uuid.uuid4())
    
    async with websockets.connect(WEBSOCKET_URL) as ws:
        print(f"✅ Connected (Session: {session_id[:8]}...)")
        
        # Step 1: Initial complaint
        print("\n📍 Step 1: Report service error")
        responses = await send_and_receive(
            ws, 
            "MBPP website is down, cannot access it",
            session_id
        )
        
        # Step 2: Describe issue
        print("\n📍 Step 2: Describe the issue")
        await asyncio.sleep(1)
        responses = await send_and_receive(
            ws,
            "The website shows error 500 when I try to login",
            session_id
        )
        
        # Step 3: Verify internet
        print("\n📍 Step 3: Confirm internet connection")
        await asyncio.sleep(1)
        responses = await send_and_receive(
            ws,
            "Yes, my internet is working fine",
            session_id
        )
        
        # Check for ticket number
        ticket = None
        for r in responses:
            if r.get('ticket_number'):
                ticket = r['ticket_number']
                break
        
        if ticket:
            print(f"\n✅ WORKFLOW 1 PASSED - Ticket: {ticket}")
        else:
            print("\n⚠️  WORKFLOW 1 INCOMPLETE - No ticket generated")
        
        return ticket is not None

async def test_workflow_2_text_incident():
    """Test Workflow 2: Text-Driven Incident Report"""
    print("\n" + "="*70)
    print("🧪 TEST 2: TEXT-DRIVEN INCIDENT REPORT WORKFLOW")
    print("="*70)
    
    session_id = str(uuid.uuid4())
    
    async with websockets.connect(WEBSOCKET_URL) as ws:
        print(f"✅ Connected (Session: {session_id[:8]}...)")
        
        # Step 1: Report incident
        print("\n📍 Step 1: Report incident")
        responses = await send_and_receive(
            ws,
            "I want to report a fallen tree blocking the road",
            session_id
        )
        
        # Step 2: Confirm incident
        print("\n📍 Step 2: Confirm it's an incident")
        await asyncio.sleep(1)
        responses = await send_and_receive(
            ws,
            "Yes, report an incident",
            session_id
        )
        
        # Step 3: Provide location
        print("\n📍 Step 3: Provide location")
        await asyncio.sleep(1)
        responses = await send_and_receive(
            ws,
            "Jalan Tun Razak, near the traffic light",
            session_id
        )
        
        # Step 4: Confirm hazard
        print("\n📍 Step 4: Confirm road blockage")
        await asyncio.sleep(1)
        responses = await send_and_receive(
            ws,
            "Yes, it's blocking the road and causing hazard",
            session_id
        )
        
        # Check for ticket
        ticket = None
        for r in responses:
            if r.get('ticket_number'):
                ticket = r['ticket_number']
                break
        
        if ticket:
            print(f"\n✅ WORKFLOW 2 PASSED - Ticket: {ticket}")
        else:
            print("\n⚠️  WORKFLOW 2 INCOMPLETE - No ticket generated")
        
        return ticket is not None

async def test_workflow_3_image_incident():
    """Test Workflow 3: Image-Driven Incident Report"""
    print("\n" + "="*70)
    print("🧪 TEST 3: IMAGE-DRIVEN INCIDENT REPORT WORKFLOW")
    print("="*70)
    
    session_id = str(uuid.uuid4())
    image_data = create_test_image()
    
    async with websockets.connect(WEBSOCKET_URL) as ws:
        print(f"✅ Connected (Session: {session_id[:8]}...)")
        
        # Step 1: Send image with incident message
        print("\n📍 Step 1: Send image with incident report")
        responses = await send_and_receive(
            ws,
            "Report incident - fallen tree",
            session_id,
            has_image=True,
            image_data=image_data
        )
        
        # Step 2: Confirm incident
        print("\n📍 Step 2: Confirm it's an incident")
        await asyncio.sleep(1)
        responses = await send_and_receive(
            ws,
            "Yes, report an incident",
            session_id
        )
        
        # Step 3: Provide details and location
        print("\n📍 Step 3: Provide description and location")
        await asyncio.sleep(1)
        responses = await send_and_receive(
            ws,
            "Large tree fell across Jalan Sultan, blocking both lanes",
            session_id
        )
        
        # Step 4: Confirm hazard
        print("\n📍 Step 4: Confirm road blockage")
        await asyncio.sleep(1)
        responses = await send_and_receive(
            ws,
            "Yes, blocking the road completely",
            session_id
        )
        
        # Check for ticket
        ticket = None
        for r in responses:
            if r.get('ticket_number'):
                ticket = r['ticket_number']
                break
        
        if ticket:
            print(f"\n✅ WORKFLOW 3 PASSED - Ticket: {ticket}")
        else:
            print("\n⚠️  WORKFLOW 3 INCOMPLETE - No ticket generated")
        
        return ticket is not None

async def run_all_tests():
    """Run all workflow tests"""
    print("\n" + "="*70)
    print("🚀 MBPP CHATBOT WORKFLOW TESTS")
    print("="*70)
    print(f"📍 Endpoint: {WEBSOCKET_URL}")
    print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = {}
    
    try:
        # Test 1: Complaint Workflow
        results['complaint'] = await test_workflow_1_complaint()
        await asyncio.sleep(2)
        
        # Test 2: Text Incident Workflow
        results['text_incident'] = await test_workflow_2_text_incident()
        await asyncio.sleep(2)
        
        # Test 3: Image Incident Workflow
        results['image_incident'] = await test_workflow_3_image_incident()
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
    
    # Summary
    print("\n" + "="*70)
    print("📊 TEST SUMMARY")
    print("="*70)
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    
    print(f"\n{'Workflow':<30} {'Status':<20}")
    print("-" * 50)
    print(f"{'1. Service/System Complaint':<30} {'✅ PASSED' if results.get('complaint') else '❌ FAILED':<20}")
    print(f"{'2. Text-Driven Incident':<30} {'✅ PASSED' if results.get('text_incident') else '❌ FAILED':<20}")
    print(f"{'3. Image-Driven Incident':<30} {'✅ PASSED' if results.get('image_incident') else '❌ FAILED':<20}")
    print("-" * 50)
    print(f"{'TOTAL':<30} {passed}/{total} PASSED")
    
    print("\n" + "="*70)
    
    if passed == total:
        print("🎉 ALL TESTS PASSED!")
    else:
        print(f"⚠️  {total - passed} TEST(S) FAILED")
    
    print("="*70 + "\n")
    
    return passed == total

if __name__ == "__main__":
    try:
        success = asyncio.run(run_all_tests())
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        exit(1)
