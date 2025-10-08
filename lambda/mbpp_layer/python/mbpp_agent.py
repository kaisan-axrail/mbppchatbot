"""
MBPP Strands Agent with Workflow and RAG Integration
Handles:
1. Normal RAG questions
2. Complaint/Service Error Workflow
3. Text-Driven Incident Report Workflow
4. Image-Driven Incident Report Workflow
"""

import os
import json
from typing import Dict, Any, Optional
from datetime import datetime
from strands import Agent
from strands_tools import workflow
from strands_tools.mbpp_workflows import mbpp_workflow
import boto3

class MBPPAgent:
    """Main MBPP Agent that handles workflows and RAG queries"""
    
    def __init__(self, session_id: str = None):
        # Initialize Bedrock client
        self.bedrock_runtime = boto3.client(
            'bedrock-runtime',
            region_name=os.environ.get('BEDROCK_REGION', 'us-east-1')
        )
        
        # Initialize DynamoDB for workflow state persistence
        self.dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('BEDROCK_REGION', 'us-east-1'))
        self.sessions_table = self.dynamodb.Table(os.environ.get('SESSIONS_TABLE', 'mbpp-sessions'))
        self.session_id = session_id
        
        # Create specialized agents
        self.workflow_agent = Agent(
            system_prompt="""You are an MBPP incident and complaint management assistant. Communicate ONLY in English.
            
            When an image is uploaded:
            - DO NOT analyze the image content
            - Simply detect that an image was uploaded
            - Ask: "Image detected. Can you confirm you would like to report an incident?"
            - Provide options: "Yes, report an incident" or "Not an incident (Service Complaint / Feedback)"
            
            Guide users through:
            1. Service/System complaints (website down, service errors)
            2. Text-based incident reports (user describes incident)
            3. Image-based incident reports (user uploads image)
            
            Always communicate in English. Be polite, clear, and guide users step-by-step.""",
            tools=[mbpp_workflow],
            model="anthropic.claude-3-5-sonnet-20240620-v1:0"
        )
        
        # Import Strands retrieve tool for RAG
        from strands_tools import retrieve
        
        self.rag_agent = Agent(
            system_prompt="""You are an MBPP (Majlis Bandaraya Pulau Pinang) knowledge assistant. Communicate ONLY in English.
            
            IMPORTANT: For ANY question the user asks, ALWAYS use the retrieve tool to search the knowledge base first.
            The knowledge base contains information about MBPP services, events, programs, policies, and general information.
            
            Steps for every question:
            1. Use retrieve tool to search the knowledge base
            2. If relevant information is found, provide a clear answer based on the retrieved content
            3. If no relevant information is found, politely inform the user that the information is not available in the knowledge base
            
            Provide accurate, helpful responses in English only.""",
            tools=[retrieve],
            model="anthropic.claude-3-5-sonnet-20240620-v1:0"
        )
        
        # Load workflow state from DynamoDB
        self.active_workflows = self._load_workflow_state(session_id) if session_id else {}
    
    def process_message(
        self,
        message: str,
        session_id: str,
        has_image: bool = False,
        image_data: Optional[str] = None,
        location: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process incoming message and route to appropriate handler
        
        Args:
            message: User message
            session_id: Session identifier
            has_image: Whether message includes an image
            image_data: Base64 encoded image data
            location: GPS location data
        
        Returns:
            Response dictionary
        """
        # Check if there's an active workflow for this session
        if session_id in self.active_workflows:
            result = self._continue_workflow(session_id, message, has_image, image_data, location)
            self._save_workflow_state(session_id)
            return result
        
        # Detect if this is a workflow trigger or RAG question
        workflow_type = self._detect_intent(message, has_image)
        
        if workflow_type in ["complaint", "text_incident", "image_incident"]:
            result = self._start_workflow(session_id, workflow_type, message, has_image, image_data)
            self._save_workflow_state(session_id)
            return result
        else:
            return self._handle_rag_query(message, session_id)
    
    def _detect_intent(self, message: str, has_image: bool) -> str:
        """Detect user intent - workflow or RAG query"""
        # If image is uploaded, trigger image incident workflow immediately
        if has_image:
            return "image_incident"
        
        message_lower = message.lower()
        
        # Service/System error keywords (highest priority)
        service_keywords = ['website', 'system', 'service', 'portal', 'online', 'app', 'down', 'not working', 'cannot access']
        
        # Physical incident keywords
        incident_keywords = ['report incident', 'report an incident', 'fallen tree', 'pothole', 'flood', 'accident', 'blocking', 'hazard', 'emergency', 'incident']
        
        has_service_issue = any(keyword in message_lower for keyword in service_keywords)
        has_incident = any(keyword in message_lower for keyword in incident_keywords)
        
        if has_service_issue:
            return "complaint"
        elif has_incident:
            return "text_incident"
        else:
            return "rag"
    
    def _start_workflow(
        self,
        session_id: str,
        workflow_type: str,
        message: str,
        has_image: bool,
        image_data: Optional[str]
    ) -> Dict[str, Any]:
        """Start a new workflow using AI"""
        import uuid
        workflow_id = str(uuid.uuid4())
        
        # Store workflow context
        self.active_workflows[session_id] = {
            "workflow_id": workflow_id,
            "workflow_type": workflow_type,
            "current_step": 0 if has_image else 1,
            "data": {
                "initial_message": message,
                "has_image": has_image,
                "image_data": image_data
            }
        }
        
        # For image uploads, ask for incident confirmation first
        if has_image:
            return {
                "type": "workflow",
                "workflow_type": workflow_type,
                "workflow_id": workflow_id,
                "response": "Image detected. Can you confirm you would like to report an incident?",
                "session_id": session_id
            }
        
        # Use AI to start workflow intelligently for text
        prompt = f"""You are helping a user report an incident. The user said: "{message}"

You need to collect:
1. Description of what happened
2. Location
3. A contextual yes/no question about immediate danger/hazard

Analyze the user's message and respond with ONLY a JSON:
{{"has_description": true/false, "has_location": true/false, "next_question": "what to ask next"}}

If they provided description, extract it and ask for location. If they provided both, extract both and ask contextual hazard question. If neither, ask for description."""
        
        try:
            response = self.bedrock_runtime.invoke_model(
                modelId='anthropic.claude-3-5-sonnet-20240620-v1:0',
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 300,
                    "messages": [{"role": "user", "content": prompt}]
                })
            )
            result = json.loads(response['body'].read())
            ai_response = json.loads(result['content'][0]['text'])
            
            # Update workflow data - store actual message as description
            if ai_response.get('has_description'):
                self.active_workflows[session_id]['data']['description'] = message
                self.active_workflows[session_id]['current_step'] = 2
            
            if ai_response.get('has_location'):
                # Extract location from message using AI
                try:
                    loc_prompt = f'Extract ONLY the location from: "{message}". Return just the location text, nothing else.'
                    loc_response = self.bedrock_runtime.invoke_model(
                        modelId='anthropic.claude-3-5-sonnet-20240620-v1:0',
                        body=json.dumps({
                            "anthropic_version": "bedrock-2023-05-31",
                            "max_tokens": 100,
                            "messages": [{"role": "user", "content": loc_prompt}]
                        })
                    )
                    loc_result = json.loads(loc_response['body'].read())
                    location = loc_result['content'][0]['text'].strip()
                    self.active_workflows[session_id]['data']['location'] = location
                except:
                    self.active_workflows[session_id]['data']['location'] = message
                self.active_workflows[session_id]['current_step'] = 3
            
            response_text = ai_response.get('next_question', 'Please describe what happened.')
            
        except Exception as e:
            print(f"AI extraction error: {e}")
            response_text = "Please share an image of the incident, the location and describe what happened. You may also share your location to make it easier.\n\n(e.g. I would like to complain about a pothole at Jalan Penang, 10000, Georgetown)"
        
        return {
            "type": "workflow",
            "workflow_type": workflow_type,
            "workflow_id": workflow_id,
            "response": response_text,
            "session_id": session_id
        }
    
    def _continue_workflow(
        self,
        session_id: str,
        message: str,
        has_image: bool,
        image_data: Optional[str],
        location: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Continue an existing workflow using AI"""
        workflow_context = self.active_workflows[session_id]
        workflow_id = workflow_context["workflow_id"]
        workflow_type = workflow_context["workflow_type"]
        current_step = workflow_context["current_step"]
        
        collected_data = workflow_context["data"]
        
        # Handle complaint workflow
        if workflow_type == "complaint":
            if current_step == 1 and 'description' not in collected_data:
                collected_data['description'] = message
                workflow_context['current_step'] = 2
                return {
                    "type": "workflow",
                    "workflow_type": "complaint",
                    "workflow_id": workflow_id,
                    "response": "Can you please confirm if your internet connection is working properly?",
                    "session_id": session_id,
                    "quick_replies": [
                        {"text": "✅ Yes", "value": "yes"},
                        {"text": "❌ No", "value": "no"}
                    ]
                }
            elif current_step == 2:
                collected_data['verification'] = 'yes' in message.lower()
                workflow_context['current_step'] = 3
                
                from strands_tools.mbpp_workflows import MBPPWorkflowManager
                manager = MBPPWorkflowManager()
                ticket_number = manager._generate_ticket_number()
                
                ticket = {
                    "ticket_number": ticket_number,
                    "subject": "Service Error",
                    "details": collected_data['description'],
                    "feedback": "Aduan",
                    "category": "Service/ System Error",
                    "sub_category": "-",
                    "created_at": datetime.now().isoformat()
                }
                
                collected_data['ticket_details'] = ticket
                
                preview = (
                    "Please confirm these details:\n\n"
                    f"**Subject:** {ticket['subject']}\n\n"
                    f"**Details:** {ticket['details']}\n\n"
                    f"**Category:** {ticket['category']}\n\n"
                    f"**Internet verified:** {'Yes' if collected_data.get('verification') else 'No'}\n\n"
                    "Is this correct?"
                )
                
                return {
                    "type": "workflow",
                    "workflow_type": "complaint",
                    "workflow_id": workflow_id,
                    "response": preview,
                    "session_id": session_id,
                    "quick_replies": [
                        {"text": "✅ Yes, submit", "value": "yes"},
                        {"text": "❌ No, start over", "value": "no"}
                    ]
                }
            elif current_step == 3:
                if 'no' in message.lower():
                    workflow_context['current_step'] = 1
                    workflow_context['data'] = {}
                    return {
                        "type": "workflow",
                        "workflow_type": "complaint",
                        "workflow_id": workflow_id,
                        "response": "Let's start over. Please describe the issue.",
                        "session_id": session_id
                    }
                
                from strands_tools.mbpp_workflows import MBPPWorkflowManager
                manager = MBPPWorkflowManager()
                ticket = collected_data['ticket_details']
                manager._save_report(ticket)
                manager._create_event('complaint_created', ticket['ticket_number'], collected_data)
                
                del self.active_workflows[session_id]
                self._save_workflow_state(session_id)
                return {
                    "type": "workflow_complete",
                    "workflow_type": "complaint",
                    "workflow_id": workflow_id,
                    "response": f"Thank you for your submission! Your reference number is {ticket['ticket_number']}",
                    "session_id": session_id
                }
        
        # Handle image incident confirmation (step 0)
        if current_step == 0 and collected_data.get('has_image'):
            if 'yes' in message.lower() and 'incident' in message.lower():
                workflow_context['current_step'] = 1
                return {
                    "type": "workflow",
                    "workflow_type": workflow_type,
                    "workflow_id": workflow_id,
                    "response": "Please describe what happened and tell us the location.",
                    "session_id": session_id
                }
            else:
                # User selected service complaint - switch to complaint workflow
                workflow_context['workflow_type'] = 'complaint'
                workflow_context['current_step'] = 1
                workflow_context['data'] = {}
                return {
                    "type": "workflow",
                    "workflow_type": "complaint",
                    "workflow_id": workflow_id,
                    "response": "Thank you for your feedback. Could you please describe the issue or service/system error?\n\n(e.g. I want to complain about slow response times on a government website.)",
                    "session_id": session_id
                }
        
        # Update workflow data based on what field user is providing
        if 'description' not in collected_data:
            collected_data['description'] = message
            
            # Check if image was provided - switch to image_incident workflow
            if has_image and image_data:
                collected_data['image_data'] = image_data
                collected_data['has_image'] = True
                workflow_context['workflow_type'] = 'image_incident'
                workflow_context['current_step'] = 0
                return {
                    "type": "workflow",
                    "workflow_type": "image_incident",
                    "workflow_id": workflow_id,
                    "response": "Image detected. Can you confirm you would like to report an incident?",
                    "session_id": session_id,
                    "quick_replies": [
                        {"text": "Yes, report an incident", "value": "yes_incident"},
                        {"text": "Not an incident (Service Complaint / Feedback)", "value": "no_complaint"}
                    ]
                }
            
            workflow_context['current_step'] = 2
            return {
                "type": "workflow",
                "workflow_type": workflow_type,
                "workflow_id": workflow_id,
                "response": "What is the exact location?",
                "session_id": session_id
            }
        elif 'location' not in collected_data:
            collected_data['location'] = message
            workflow_context['current_step'] = 3
            
            # Generate contextual hazard question
            desc = collected_data['description'].lower()
            if 'tree' in desc or 'fallen' in desc:
                hazard_q = "Is the fallen tree blocking the road?"
            elif 'pothole' in desc:
                hazard_q = "Is the pothole causing traffic issues?"
            elif 'flood' in desc:
                hazard_q = "Is the flooding blocking access?"
            else:
                hazard_q = "Is this causing immediate danger or blocking access?"
            
            return {
                "type": "workflow",
                "workflow_type": workflow_type,
                "workflow_id": workflow_id,
                "response": hazard_q,
                "session_id": session_id,
                "quick_replies": ["Yes", "No"]
            }
        elif 'hazard_confirmation' not in collected_data:
            collected_data['hazard_confirmation'] = 'yes' in message.lower()
            workflow_context['current_step'] = 4
            
            # Show preview
            from strands_tools.mbpp_workflows import MBPPWorkflowManager
            manager = MBPPWorkflowManager()
            classification = manager.classify_incident(collected_data['description'])
            
            preview = (
                "Please confirm these details:\n\n"
                f"**Subject:** Incident Report\n\n"
                f"**Details:** {collected_data['description']}\n\n"
                f"**Feedback:** {classification['feedback']}\n\n"
                f"**Category:** {classification['category']}\n\n"
                f"**Sub-category:** {classification['sub_category']}\n\n"
                f"**Blocked road:** {'Yes' if collected_data.get('hazard_confirmation') else 'No'}\n\n"
                f"**Location:** {collected_data['location']}\n\n"
                "Is this correct?"
            )
            
            collected_data['preview_classification'] = classification
            return {
                "type": "workflow",
                "workflow_type": workflow_type,
                "workflow_id": workflow_id,
                "response": preview,
                "session_id": session_id,
                "quick_replies": [
                    {"text": "✅ Yes, submit", "value": "yes"},
                    {"text": "❌ No, start over", "value": "no"}
                ]
            }
        else:
            # Final confirmation
            if 'no' in message.lower():
                workflow_context['current_step'] = 1
                workflow_context['data'] = {}
                return {
                    "type": "workflow",
                    "workflow_type": workflow_type,
                    "workflow_id": workflow_id,
                    "response": "Let's start over. Please describe what happened.",
                    "session_id": session_id
                }
            
            # Save ticket
            from strands_tools.mbpp_workflows import MBPPWorkflowManager
            manager = MBPPWorkflowManager()
            
            ticket_number = manager._generate_ticket_number()
            classification = collected_data['preview_classification']
            
            ticket = {
                "ticket_number": ticket_number,
                "subject": "Incident Report",
                "details": collected_data['description'],
                "location": collected_data['location'],
                "feedback": classification["feedback"],
                "category": classification["category"],
                "sub_category": classification["sub_category"],
                "blocked_road": collected_data.get('hazard_confirmation', False),
                "created_at": datetime.now().isoformat()
            }
            
            # Save image to S3 if present
            if collected_data.get('image_data'):
                print(f"Saving image to S3 for ticket: {ticket_number}")
                image_url = manager._save_image(collected_data['image_data'], ticket_number)
                if image_url:
                    ticket['image_url'] = image_url
                    print(f"Image saved to S3: {image_url}")
                else:
                    print(f"Failed to save image to S3")
            
            # Save ticket to DynamoDB
            print(f"Attempting to save ticket: {ticket}")
            print(f"Reports table: {os.environ.get('REPORTS_TABLE', 'mbpp-reports')}")
            save_success = manager._save_report(ticket)
            print(f"Ticket save result: {save_success}, ticket_number: {ticket_number}")
            
            if save_success:
                manager._create_event('incident_created', ticket_number, collected_data)
                print(f"Event created for ticket: {ticket_number}")
            else:
                print(f"ERROR: Failed to save ticket {ticket_number} to DynamoDB")
            
            del self.active_workflows[session_id]
            self._save_workflow_state(session_id)
            return {
                "type": "workflow_complete",
                "workflow_type": workflow_type,
                "workflow_id": workflow_id,
                "response": f"Thank you for your submission! Your reference number is {ticket_number}",
                "session_id": session_id
            }
        
        return {
            "type": "workflow",
            "workflow_type": workflow_type,
            "workflow_id": workflow_id,
            "response": response_text,
            "session_id": session_id
        }
    
    def _get_workflow_action(self, workflow_type: str, step: int, message: str) -> str:
        """Determine workflow action based on type and step"""
        if workflow_type == "text_incident":
            if step == 1: return "step2_submit_info"
            if step == 2: return "step3_confirm"
            if step == 3: return "step4_location"
            if step >= 4: return "confirm"
        elif workflow_type == "image_incident":
            if step == 1: return "step2_describe"
            if step == 2: return "step3_details"
            if step == 3: return "step4_hazard"
            if step == 4: return "confirm"
        return "start"
    
    def _extract_workflow_data(self, workflow_type: str, step: int, message: str, context: dict) -> dict:
        """Extract data from user message"""
        data = {}
        
        if workflow_type == "text_incident":
            if step == 1:
                data = {"description": message, "image": context["data"].get("image_data")}
            elif step == 2:
                data = {"location": message}
            elif step == 3:
                data = {"hazard_confirmation": "yes" in message.lower()}
            elif step >= 4:
                data = {"confirmation": "yes" if "yes" in message.lower() else "no"}
        elif workflow_type == "image_incident":
            if step == 1:
                data = {"confirmation": "yes" if "yes" in message.lower() else "no"}
            elif step == 2:
                # Use AI to extract description and location
                extraction_prompt = f"""Extract the incident description and location from this message:
"{message}"

Respond ONLY with JSON format:
{{"description": "what happened", "location": "where it happened"}}

If location is not mentioned, use empty string for location."""
                
                try:
                    response = self.bedrock_runtime.invoke_model(
                        modelId='anthropic.claude-3-5-sonnet-20240620-v1:0',
                        body=json.dumps({
                            "anthropic_version": "bedrock-2023-05-31",
                            "max_tokens": 200,
                            "messages": [{"role": "user", "content": extraction_prompt}]
                        })
                    )
                    result = json.loads(response['body'].read())
                    extracted = json.loads(result['content'][0]['text'])
                    data = {
                        "description": extracted.get("description", message),
                        "location": extracted.get("location", "")
                    }
                except:
                    data = {"description": message, "location": ""}
            elif step == 3:
                data = {"hazard_confirmation": "yes" in message.lower()}
        
        return data
    
    def _handle_rag_query(self, message: str, session_id: str) -> Dict[str, Any]:
        """Handle RAG-based question answering using Strands retrieve tool"""
        # Set environment variables for retrieve tool
        os.environ['KNOWLEDGE_BASE_ID'] = 'U6EAI0DHJC'  # Primary KB
        os.environ['AWS_REGION'] = os.environ.get('BEDROCK_REGION', 'us-east-1')
        os.environ['MIN_SCORE'] = '0.6'
        
        # Let the agent use retrieve tool automatically
        response = self.rag_agent(message)
        
        return {
            "type": "rag",
            "response": response,
            "session_id": session_id
        }
    

    
    def get_workflow_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get status of active workflow for a session"""
        return self.active_workflows.get(session_id)
    
    def cancel_workflow(self, session_id: str) -> bool:
        """Cancel an active workflow"""
        if session_id in self.active_workflows:
            del self.active_workflows[session_id]
            self._save_workflow_state(session_id)
            return True
        return False
    
    def _save_workflow_state(self, session_id: str) -> None:
        """Save workflow state to DynamoDB (fast: 5-20ms)"""
        if not session_id:
            return
        try:
            workflow_state = self.active_workflows.get(session_id, {})
            self.sessions_table.update_item(
                Key={'sessionId': session_id},
                UpdateExpression='SET workflowState = :state, updatedAt = :updated',
                ExpressionAttributeValues={
                    ':state': workflow_state,
                    ':updated': datetime.now().isoformat()
                }
            )
        except Exception as e:
            print(f"Failed to save workflow state: {e}")
    
    def _load_workflow_state(self, session_id: str) -> dict:
        """Load workflow state from DynamoDB (fast: 1-10ms)"""
        if not session_id:
            return {}
        try:
            response = self.sessions_table.get_item(Key={'sessionId': session_id})
            item = response.get('Item', {})
            return {session_id: item.get('workflowState', {})} if item.get('workflowState') else {}
        except Exception as e:
            print(f"Failed to load workflow state: {e}")
            return {}


# Lambda handler integration
def lambda_handler(event, context):
    """AWS Lambda handler for MBPP Agent"""
    try:
        # Parse request
        body = json.loads(event.get('body', '{}'))
        
        message = body.get('message', '')
        session_id = body.get('sessionId', '')
        has_image = body.get('hasImage', False)
        image_data = body.get('imageData')
        location = body.get('location')
        
        # Initialize agent with session ID
        agent = MBPPAgent(session_id=session_id)
        
        # Process message
        result = agent.process_message(
            message=message,
            session_id=session_id,
            has_image=has_image,
            image_data=image_data,
            location=location
        )
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(result)
        }
    
    except Exception as e:
        print(f"Error in lambda_handler: {e}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': str(e),
                'message': 'Internal server error'
            })
        }
