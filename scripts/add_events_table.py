#!/usr/bin/env python3
"""Script to add events table support and populate with mock data."""

import boto3
import json
from datetime import datetime, timedelta
import uuid

def add_mock_events():
    """Add mock event data to the events table."""
    dynamodb = boto3.resource('dynamodb', region_name='ap-southeast-1')
    table = dynamodb.Table('chatbot-events')
    
    # Mock events data
    events = [
        {
            'eventId': str(uuid.uuid4()),
            'eventName': 'AWS re:Invent 2025',
            'eventDate': '2025-12-01',
            'location': 'Las Vegas, NV',
            'description': 'Annual AWS conference with keynotes, sessions, and workshops',
            'category': 'conference',
            'registrationOpen': True,
            'created_at': datetime.now().isoformat()
        },
        {
            'eventId': str(uuid.uuid4()),
            'eventName': 'Cloud Security Summit',
            'eventDate': '2025-06-15',
            'location': 'Singapore',
            'description': 'Security best practices and compliance in cloud environments',
            'category': 'workshop',
            'registrationOpen': True,
            'created_at': datetime.now().isoformat()
        },
        {
            'eventId': str(uuid.uuid4()),
            'eventName': 'Serverless Architecture Meetup',
            'eventDate': '2025-03-20',
            'location': 'Kuala Lumpur, Malaysia',
            'description': 'Monthly meetup for serverless enthusiasts and practitioners',
            'category': 'meetup',
            'registrationOpen': True,
            'created_at': datetime.now().isoformat()
        },
        {
            'eventId': str(uuid.uuid4()),
            'eventName': 'AI/ML Workshop Series',
            'eventDate': '2025-04-10',
            'location': 'Virtual',
            'description': 'Hands-on workshop series on machine learning with AWS services',
            'category': 'workshop',
            'registrationOpen': True,
            'created_at': datetime.now().isoformat()
        },
        {
            'eventId': str(uuid.uuid4()),
            'eventName': 'DevOps Best Practices',
            'eventDate': '2025-05-05',
            'location': 'Bangkok, Thailand',
            'description': 'Learn CI/CD, infrastructure as code, and monitoring strategies',
            'category': 'conference',
            'registrationOpen': False,
            'created_at': datetime.now().isoformat()
        }
    ]
    
    # Insert events
    for event in events:
        try:
            table.put_item(Item=event)
            print(f"✓ Added event: {event['eventName']}")
        except Exception as e:
            print(f"✗ Failed to add {event['eventName']}: {str(e)}")
    
    print(f"\n✅ Successfully added {len(events)} mock events to the table")

if __name__ == '__main__':
    add_mock_events()
