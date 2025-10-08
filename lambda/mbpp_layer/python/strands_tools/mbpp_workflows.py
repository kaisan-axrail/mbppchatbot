"""
MBPP Workflow Tool - DynamoDB Integration
"""

from typing import Dict, Any, Optional
from datetime import datetime
import json
import uuid
import os
import boto3
import base64

class MBPPWorkflowManager:
    def __init__(self):
        self.workflows = {}
        self.dynamodb = boto3.resource('dynamodb')
        self.s3 = boto3.client('s3')
        
        reports_table_name = os.environ.get('REPORTS_TABLE', 'mbpp-reports')
        events_table_name = os.environ.get('EVENTS_TABLE', 'mbpp-events')
        
        print(f"Initializing MBPPWorkflowManager with tables: {reports_table_name}, {events_table_name}")
        
        self.reports_table = self.dynamodb.Table(reports_table_name)
        self.events_table = self.dynamodb.Table(events_table_name)
        self.images_bucket = os.environ.get('IMAGES_BUCKET', 'mbpp-incident-images')
    
    def classify_incident(self, description: str) -> Dict[str, str]:
        """Classify incident from description into feedback, category, and sub_category."""
        desc_lower = description.lower()
        
        # Default classification
        classification = {
            "feedback": "Aduan",
            "category": "Lain-lain",
            "sub_category": "--"
        }
        
        # Natural Disaster (Bencana Alam)
        if any(k in desc_lower for k in ['fallen tree', 'pokok tumbang', 'tree fall', 'pohon tumbang']):
            classification.update({"category": "Bencana Alam", "sub_category": "Pokok Tumbang"})
        elif any(k in desc_lower for k in ['flood', 'banjir', 'water overflow', 'flooded']):
            classification.update({"category": "Bencana Alam", "sub_category": "Banjir"})
        elif any(k in desc_lower for k in ['landslide', 'tanah runtuh', 'soil collapse']):
            classification.update({"category": "Bencana Alam", "sub_category": "Tanah Runtuh"})
        
        # Road Issues (Jalan Raya)
        elif any(k in desc_lower for k in ['pothole', 'lubang jalan', 'road hole', 'damaged road']):
            classification.update({"category": "Jalan Raya", "sub_category": "Lubang Jalan"})
        elif any(k in desc_lower for k in ['crack', 'retak jalan', 'road crack']):
            classification.update({"category": "Jalan Raya", "sub_category": "Jalan Retak"})
        
        # Infrastructure (Infrastruktur)
        elif any(k in desc_lower for k in ['street light', 'lampu jalan', 'lamp', 'lighting']):
            classification.update({"category": "Infrastruktur", "sub_category": "Lampu Jalan"})
        elif any(k in desc_lower for k in ['drain', 'longkang', 'parit', 'drainage']):
            classification.update({"category": "Infrastruktur", "sub_category": "Longkang"})
        elif any(k in desc_lower for k in ['traffic light', 'lampu isyarat', 'signal']):
            classification.update({"category": "Infrastruktur", "sub_category": "Lampu Isyarat"})
        
        # Waste Management (Pengurusan Sampah)
        elif any(k in desc_lower for k in ['garbage', 'sampah', 'trash', 'rubbish', 'waste']):
            classification.update({"category": "Pengurusan Sampah", "sub_category": "Sampah Berserakan"})
        
        # Service/System Error
        elif any(k in desc_lower for k in ['website', 'system', 'service', 'app', 'online', 'portal']):
            classification.update({"category": "Service/ System Error", "sub_category": "--"})
        
        return classification
    
    def detect_workflow_type(self, message: str, has_image: bool = False) -> str:
        message_lower = message.lower()
        incident_keywords = ['incident', 'report', 'emergency', 'hazard', 'fallen tree', 'pothole', 'flood', 'accident', 'blocking']
        complaint_keywords = ['complaint', 'feedback', 'service error', 'system down', 'website', 'not working', 'issue']
        
        has_incident = any(k in message_lower for k in incident_keywords)
        has_complaint = any(k in message_lower for k in complaint_keywords)
        
        if has_image and has_incident:
            return "image_incident"
        elif has_incident:
            return "text_incident"
        elif has_complaint:
            return "complaint"
        return "general"
    
    def create_workflow(self, workflow_type: str, workflow_id: str, initial_data: Dict[str, Any]) -> Dict[str, Any]:
        workflow = {
            "workflow_id": workflow_id,
            "type": workflow_type,
            "status": "initiated",
            "current_step": 1,
            "data": initial_data,
            "created_at": datetime.now().isoformat(),
            "ticket_number": None
        }
        self.workflows[workflow_id] = workflow
        return workflow
    
    def _generate_ticket_number(self) -> str:
        date_str = datetime.now().strftime("%Y/%m/%d")
        timestamp = int(datetime.now().timestamp() * 1000)
        ticket_id = 20000 + (timestamp % 10000)
        return f"{ticket_id}/{date_str}"
    
    def _save_image(self, image_data: str, ticket_number: str) -> Optional[str]:
        try:
            if image_data.startswith('data:image'):
                image_data = image_data.split(',')[1]
            
            image_bytes = base64.b64decode(image_data)
            key = f"incidents/{ticket_number}/{uuid.uuid4()}.jpg"
            
            self.s3.put_object(
                Bucket=self.images_bucket,
                Key=key,
                Body=image_bytes,
                ContentType='image/jpeg'
            )
            return f"s3://{self.images_bucket}/{key}"
        except Exception as e:
            print(f"Error saving image: {e}")
            return None
    
    def _save_report(self, ticket: Dict[str, Any]) -> bool:
        try:
            item = {
                'ticket_number': ticket['ticket_number'],
                'subject': ticket.get('subject', ''),
                'details': ticket.get('details', ''),
                'location': ticket.get('location', ''),
                'feedback': ticket.get('feedback', 'Aduan'),
                'category': ticket.get('category', ''),
                'sub_category': ticket.get('sub_category', ''),
                'blocked_road': str(ticket.get('blocked_road', False)),
                'created_at': ticket['created_at'],
                'status': 'open',
                'ttl': int(datetime.now().timestamp()) + (90 * 24 * 60 * 60)
            }
            
            if ticket.get('image_url'):
                item['image_url'] = ticket['image_url']
            
            print(f"[SAVE_REPORT] Table: {self.reports_table.table_name}")
            print(f"[SAVE_REPORT] Item: {json.dumps(item, default=str)}")
            
            response = self.reports_table.put_item(Item=item)
            print(f"[SAVE_REPORT] DynamoDB Response: {json.dumps(response, default=str)}")
            print(f"[SAVE_REPORT] SUCCESS - Ticket {ticket['ticket_number']} saved")
            return True
        except Exception as e:
            print(f"[SAVE_REPORT] ERROR: {str(e)}")
            print(f"[SAVE_REPORT] Table name: {self.reports_table.table_name}")
            print(f"[SAVE_REPORT] Ticket data: {json.dumps(ticket, default=str)}")
            import traceback
            traceback.print_exc()
            return False
    
    def _create_event(self, event_type: str, ticket_number: str, data: Dict[str, Any]) -> bool:
        try:
            event_id = str(uuid.uuid4())
            self.events_table.put_item(Item={
                'event_id': event_id,
                'ticket_number': ticket_number,
                'event_type': event_type,
                'timestamp': datetime.now().isoformat(),
                'data': json.dumps(data),
                'ttl': int(datetime.now().timestamp()) + (90 * 24 * 60 * 60)
            })
            return True
        except Exception as e:
            print(f"Error creating event: {e}")
            return False
    
    def complaint_workflow(self, workflow_id: str, action: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        if action == "start":
            workflow = self.create_workflow("complaint", workflow_id, data or {})
            return {"status": "success", "step": 1, "message": "Thank you for your feedback. Could you please describe the issue or service/system error?\n\n(e.g. I want to complain about slow response times on a government website.)", "workflow_id": workflow_id}
        
        elif action == "step2_describe":
            workflow = self.workflows.get(workflow_id)
            if not workflow:
                return {"status": "error", "message": "Workflow not found"}
            workflow["current_step"] = 2
            workflow["data"]["description"] = data.get("description")
            return {"status": "success", "step": 2, "message": "Can you please confirm if your internet connection is working properly?", "workflow_id": workflow_id}
        
        elif action == "step3_verify":
            workflow = self.workflows.get(workflow_id)
            workflow["current_step"] = 3
            workflow["data"]["verification"] = data.get("verification")
            
            ticket_number = self._generate_ticket_number()
            ticket = {
                "ticket_number": ticket_number,
                "subject": "Service Error",
                "details": workflow["data"]["description"],
                "feedback": "Aduan",
                "category": "Service/ System Error",
                "sub_category": "-",
                "created_at": datetime.now().isoformat()
            }
            
            workflow["ticket_number"] = ticket_number
            workflow["ticket_details"] = ticket
            
            preview = (
                "Please confirm these details:\n\n"
                f"**Subject:** {ticket['subject']}\n\n"
                f"**Details:** {ticket['details']}\n\n"
                f"**Category:** {ticket['category']}\n\n"
                f"**Internet verified:** {'Yes' if workflow['data'].get('verification') else 'No'}\n\n"
                "Is this correct?"
            )
            
            return {"status": "success", "step": 3, "message": preview, "workflow_id": workflow_id}
        
        elif action == "confirm":
            workflow = self.workflows.get(workflow_id)
            confirmation = data.get("confirmation")
            
            if confirmation == "no":
                workflow["current_step"] = 2
                workflow["data"] = {}
                return {"status": "success", "message": "Let's start over. Please describe the issue.", "workflow_id": workflow_id}
            
            ticket = workflow["ticket_details"]
            self._save_report(ticket)
            self._create_event('complaint_created', ticket["ticket_number"], workflow["data"])
            workflow["status"] = "completed"
            
            return {"status": "success", "message": f"Thank you for your submission! Your reference number is {workflow['ticket_number']}", "ticket_number": workflow["ticket_number"], "workflow_id": workflow_id}
    
    def text_incident_workflow(self, workflow_id: str, action: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        if action == "start":
            workflow = self.create_workflow("text_incident", workflow_id, data or {})
            return {"status": "success", "step": 1, "message": "Please describe what happened.", "workflow_id": workflow_id}
        
        elif action == "step2_submit_info":
            workflow = self.workflows.get(workflow_id)
            workflow["current_step"] = 2
            workflow["data"]["description"] = data.get("description")
            workflow["data"]["image"] = data.get("image")
            return {"status": "success", "step": 2, "message": "Where is this? You can share your live location or type the address.", "workflow_id": workflow_id}
        
        elif action == "step3_confirm":
            workflow = self.workflows.get(workflow_id)
            workflow["current_step"] = 3
            workflow["data"]["location"] = data.get("location")
            
            # Use AI to generate contextual hazard question
            description = workflow["data"]["description"]
            try:
                bedrock = boto3.client('bedrock-runtime', region_name=os.environ.get('BEDROCK_REGION', 'us-east-1'))
                prompt = f"""Based on this incident: "{description}"

Generate a short yes/no question asking if it's causing immediate danger or blocking access. Keep it under 15 words.
Examples:
- "Is it blocking the road?"
- "Is it causing immediate danger?"
- "Is access blocked?"

Respond with ONLY the question, nothing else."""
                
                response = bedrock.invoke_model(
                    modelId='anthropic.claude-3-5-sonnet-20240620-v1:0',
                    body=json.dumps({
                        "anthropic_version": "bedrock-2023-05-31",
                        "max_tokens": 50,
                        "messages": [{"role": "user", "content": prompt}]
                    })
                )
                result = json.loads(response['body'].read())
                hazard_question = result['content'][0]['text'].strip()
            except:
                hazard_question = "Is it blocking the road or causing immediate danger?"
            
            return {"status": "success", "step": 3, "message": hazard_question, "workflow_id": workflow_id}
        
        elif action == "step4_location":
            workflow = self.workflows.get(workflow_id)
            workflow["current_step"] = 4
            workflow["data"]["hazard_confirmation"] = data.get("hazard_confirmation")
            
            # Classify incident and prepare ticket (don't save yet)
            classification = self.classify_incident(workflow["data"]["description"])
            
            ticket_number = self._generate_ticket_number()
            ticket = {
                "ticket_number": ticket_number,
                "subject": "Incident Report",
                "details": workflow["data"]["description"],
                "location": workflow["data"]["location"],
                "feedback": classification["feedback"],
                "category": classification["category"],
                "sub_category": classification["sub_category"],
                "blocked_road": workflow["data"]["hazard_confirmation"],
                "created_at": datetime.now().isoformat()
            }
            
            # Store ticket in workflow context (not DynamoDB yet)
            workflow["ticket_number"] = ticket_number
            workflow["ticket_details"] = ticket
            
            # Show ticket details for confirmation
            confirmation_msg = f"""Please confirm these details:

Ticket #: {ticket_number}
Description: {ticket['details']}
Location: {ticket['location']}
Category: {ticket['category']} - {ticket['sub_category']}
Blocking Road: {'Yes' if ticket['blocked_road'] else 'No'}

Is this correct? (Yes to submit / No to restart)"""
            
            return {"status": "success", "step": 4, "message": confirmation_msg, "workflow_id": workflow_id}
        
        elif action == "confirm":
            workflow = self.workflows.get(workflow_id)
            confirmation = data.get("confirmation")
            
            if confirmation == "no":
                # Restart workflow
                workflow["current_step"] = 1
                workflow["data"] = {}
                return {"status": "success", "message": "Let's start over. Please describe what happened.", "workflow_id": workflow_id}
            
            # Save to DynamoDB only after confirmation
            ticket = workflow["ticket_details"]
            
            if workflow["data"].get("image"):
                image_url = self._save_image(workflow["data"]["image"], ticket["ticket_number"])
                if image_url:
                    ticket["image_url"] = image_url
            
            self._save_report(ticket)
            self._create_event('incident_created', ticket["ticket_number"], workflow["data"])
            workflow["status"] = "completed"
            
            return {"status": "success", "message": f"Thank you for your submission! Your reference number is {workflow['ticket_number']}", "ticket_number": workflow["ticket_number"], "workflow_id": workflow_id}
    
    def image_incident_workflow(self, workflow_id: str, action: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        if action == "start":
            workflow = self.create_workflow("image_incident", workflow_id, data or {})
            workflow["data"]["image"] = data.get("image")
            return {"status": "success", "step": 1, "message": "Image detected. Can you confirm you would like to report an incident?", "options": ["Yes, report an incident", "Not an incident (Service Complaint / Feedback)"], "workflow_id": workflow_id}
        
        elif action == "step2_describe":
            workflow = self.workflows.get(workflow_id)
            workflow["current_step"] = 2
            workflow["data"]["confirmation"] = data.get("confirmation")
            return {"status": "success", "step": 2, "message": "Please describe what happened and tell us the location. You may also share your live location to make it easier (eg. i would like to complain about a pot hole at Jalan Penang ,10000,Georgetown.)", "workflow_id": workflow_id}
        
        elif action == "step3_details":
            workflow = self.workflows.get(workflow_id)
            workflow["current_step"] = 3
            workflow["data"]["description"] = data.get("description")
            workflow["data"]["location"] = data.get("location")
            return {"status": "success", "step": 3, "message": "Could you confirm if its blocking the road and causing hazard?", "workflow_id": workflow_id}
        
        elif action == "step4_hazard":
            workflow = self.workflows.get(workflow_id)
            workflow["current_step"] = 4
            workflow["data"]["hazard_confirmation"] = data.get("hazard_confirmation")
            
            # Classify incident from description
            classification = self.classify_incident(workflow["data"]["description"])
            
            ticket_number = self._generate_ticket_number()
            ticket = {
                "ticket_number": ticket_number,
                "subject": data.get("subject", "Incident Report"),
                "details": workflow["data"]["description"],
                "location": workflow["data"]["location"],
                "feedback": classification["feedback"],
                "category": classification["category"],
                "sub_category": classification["sub_category"],
                "blocked_road": workflow["data"]["hazard_confirmation"],
                "created_at": datetime.now().isoformat()
            }
            
            if workflow["data"].get("image"):
                image_url = self._save_image(workflow["data"]["image"], ticket_number)
                if image_url:
                    ticket["image_url"] = image_url
            
            self._save_report(ticket)
            self._create_event('incident_created', ticket_number, workflow["data"])
            workflow["ticket_number"] = ticket_number
            
            return {"status": "success", "step": 4, "message": "Logging the ticket...", "ticket": ticket, "workflow_id": workflow_id}
        
        elif action == "confirm":
            workflow = self.workflows.get(workflow_id)
            workflow["status"] = "completed"
            return {"status": "success", "message": f"Thank you for your submission, a complaint ticket has been logged and the reference number is {workflow['ticket_number']}", "ticket_number": workflow["ticket_number"], "workflow_id": workflow_id}
    
    def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            return {"status": "error", "message": "Workflow not found"}
        return {"status": "success", "workflow": workflow}


def mbpp_workflow(action: str, workflow_type: Optional[str] = None, workflow_id: Optional[str] = None, data: Optional[Dict[str, Any]] = None, message: Optional[str] = None, has_image: bool = False) -> Dict[str, Any]:
    manager = MBPPWorkflowManager()
    
    if action == "detect":
        detected_type = manager.detect_workflow_type(message or "", has_image)
        return {"status": "success", "workflow_type": detected_type, "message": f"Detected workflow type: {detected_type}"}
    
    elif action == "start":
        if not workflow_id:
            workflow_id = str(uuid.uuid4())
        
        if workflow_type == "complaint":
            return manager.complaint_workflow(workflow_id, "start", data)
        elif workflow_type == "text_incident":
            return manager.text_incident_workflow(workflow_id, "start", data)
        elif workflow_type == "image_incident":
            return manager.image_incident_workflow(workflow_id, "start", data)
        return {"status": "error", "message": "Invalid workflow type"}
    
    elif action == "status":
        return manager.get_workflow_status(workflow_id)
    
    else:
        if workflow_type == "complaint":
            return manager.complaint_workflow(workflow_id, action, data)
        elif workflow_type == "text_incident":
            return manager.text_incident_workflow(workflow_id, action, data)
        elif workflow_type == "image_incident":
            return manager.image_incident_workflow(workflow_id, action, data)
        return {"status": "error", "message": "Invalid workflow type"}
