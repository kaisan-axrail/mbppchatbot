#!/usr/bin/env python3
"""
WebSocket Automation Testing from CSV
Reads questions from CSV first column (after header) and tests chatbot
"""

import asyncio
import websockets
import json
import csv
from datetime import datetime
import sys

# WebSocket endpoint
WS_URL = "wss://i75sc6a4ul.execute-api.ap-southeast-1.amazonaws.com/prod"

async def test_question(question, session_id):
    """Test a single question"""
    try:
        async with websockets.connect(WS_URL) as websocket:
            # Send message
            message = {
                "action": "sendMessage",
                "sessionId": session_id,
                "message": question,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            
            await websocket.send(json.dumps(message))
            
            # Wait for response (with timeout)
            response = await asyncio.wait_for(websocket.recv(), timeout=30)
            response_data = json.loads(response)
            
            # Extract response from various possible formats
            bot_response = (
                response_data.get("message") or 
                response_data.get("content") or 
                response_data.get("response") or
                json.dumps(response_data)
            )
            
            return {
                "question": question,
                "response": bot_response,
                "status": "success"
            }
    except asyncio.TimeoutError:
        return {
            "question": question,
            "response": "TIMEOUT",
            "status": "timeout"
        }
    except Exception as e:
        return {
            "question": question,
            "response": str(e),
            "status": "error"
        }

async def run_tests(csv_file):
    """Run all tests from CSV file"""
    results = []
    session_id = f"test-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    # Read CSV
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader)  # Skip header
        
        questions = [row[0] for row in reader if row and row[0].strip()]
    
    print(f"Testing {len(questions)} questions...")
    print(f"Session ID: {session_id}\n")
    
    # Test each question
    for i, question in enumerate(questions, 1):
        print(f"[{i}/{len(questions)}] Testing: {question[:50]}...")
        
        result = await test_question(question, session_id)
        results.append(result)
        
        print(f"  Status: {result['status']}")
        if result['status'] == 'success':
            print(f"  Response: {result['response'][:100]}...")
        print()
        
        # Small delay between requests
        await asyncio.sleep(1)
    
    # Save results
    output_file = f"test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Question', 'Response', 'Status'])
        
        for result in results:
            writer.writerow([
                result['question'],
                result['response'],
                result['status']
            ])
    
    print(f"\nResults saved to: {output_file}")
    
    # Summary
    success = sum(1 for r in results if r['status'] == 'success')
    print(f"\nSummary:")
    print(f"  Total: {len(results)}")
    print(f"  Success: {success}")
    print(f"  Failed: {len(results) - success}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_websocket_csv.py <csv_file>")
        print("\nCSV format:")
        print("  First row: header (will be skipped)")
        print("  First column: questions to test")
        sys.exit(1)
    
    csv_file = sys.argv[1]
    asyncio.run(run_tests(csv_file))
