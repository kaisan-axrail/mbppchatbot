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
            
            CRITICAL INSTRUCTION: You MUST use the retrieve tool for EVERY user question before answering.
            
            Process:
            1. User asks a question
            2. IMMEDIATELY call retrieve tool with the user's question as the text parameter
            3. Wait for retrieve results
            4. If results found: Answer based on the retrieved information
            5. If no results found: Say "I don't have information about that in the MBPP knowledge base."
            
            IMPORTANT: DO NOT include source citations, references, or document numbers in your response. Just provide the answer directly.
            
            NEVER answer without calling retrieve first.
            The knowledge base contains MBPP services, events, programs, policies, and procedures.""",
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
        
        # For text incident, always show the standard initial message
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
        print(f"[DEBUG] Continue workflow - step: {current_step}, waiting_for_location: {collected_data.get('waiting_for_location')}, has description: {'description' in collected_data}")
        
        # Handle image incident confirmation (step 0)
        if current_step == 0 and collected_data.get('has_image'):
            if 'yes' in message.lower() and 'incident' in message.lower():
                workflow_context['current_step'] = 1
                # Ensure image_data is preserved from initial upload
                if not collected_data.get('image_data') and workflow_context['data'].get('image_data'):
                    collected_data['image_data'] = workflow_context['data']['image_data']
                return {
                    "type": "workflow",
                    "workflow_type": workflow_type,
                    "workflow_id": workflow_id,
                    "response": "Please describe what happened and tell us the location. You may also share your live location to make it easier.\n\n(e.g. I want to complain about a pothole at Jalan Penang, 10000, Georgetown)",
                    "session_id": session_id
                }
            else:
                # User selected service complaint - keep as incident workflow, just continue
                image_data = collected_data.get('image_data') or workflow_context['data'].get('image_data')
                workflow_context['current_step'] = 1
                workflow_context['data'] = {'image_data': image_data, 'has_image': True}
                return {
                    "type": "workflow",
                    "workflow_type": workflow_type,
                    "workflow_id": workflow_id,
                    "response": "Please describe what happened and tell us the location. You may also share your live location to make it easier.\n\n(e.g. I want to complain about a pothole at Jalan Penang, 10000, Georgetown)",
                    "session_id": session_id
                }
        
        # Handle text_incident workflow step 1: image upload after text trigger
        if workflow_type == 'text_incident' and current_step == 1 and has_image and image_data:
            collected_data['image_data'] = image_data
            collected_data['has_image'] = True
            workflow_context['current_step'] = 1  # Stay at step 1 to get description
            return {
                "type": "workflow",
                "workflow_type": "text_incident",
                "workflow_id": workflow_id,
                "response": "Please describe what happened and tell us the location. You may also share your live location to make it easier.\n\n(e.g. I want to complain about a pothole at Jalan Penang, 10000, Georgetown)",
                "session_id": session_id
            }
        
        # Handle combined description+location for both text_incident and image_incident
        # Step 1: Get description (if not already collected)
        if current_step == 1 and 'description' not in collected_data:
            # Use AI to extract ONLY location, keep description as-is from user
            extraction_prompt = f"""Extract ONLY the specific location/address from this message:
"{message}"

A valid Malaysian location MUST include AT LEAST ONE of:
- Specific street name with prefix: Jalan/Lorong/Lebuh/Persiaran + street name
- Specific area/place name: Georgetown, Bayan Lepas, Tanjung Tokong, etc.
- Postal code: 5 digits (10xxx, 11xxx, etc.)

VALID examples:
- "Jalan Penang, Georgetown"
- "Bayan Lepas, 11900"
- "Lebuh Chulia"
- "Tanjung Tokong"

INVALID (DO NOT extract these):
- Generic terms: "main road", "the road", "the street"
- Descriptive words: "tree", "pothole", "blocking"
- Phrases like: "blocking the main road", "on the road"

If NO specific location/address is mentioned, respond with empty string.
Respond with ONLY the location or empty string, nothing else."""
            
            try:
                response = self.bedrock_runtime.invoke_model(
                    modelId='anthropic.claude-3-5-sonnet-20240620-v1:0',
                    body=json.dumps({
                        "anthropic_version": "bedrock-2023-05-31",
                        "max_tokens": 100,
                        "messages": [{"role": "user", "content": extraction_prompt}]
                    })
                )
                result = json.loads(response['body'].read())
                location = result['content'][0]['text'].strip()
                collected_data['description'] = message  # Keep user's exact message as description
                collected_data['location'] = location if location and location.lower() != 'empty string' else ""
            except Exception as e:
                print(f"AI extraction error: {e}")
                collected_data['description'] = message
                collected_data['location'] = ""
            
            # If location is empty or just whitespace, ask for it
            if not collected_data.get('location', '').strip():
                workflow_context['current_step'] = 2
                collected_data['waiting_for_location'] = True
                print(f"[DEBUG] Location empty, setting waiting_for_location=True, step=2")
                print(f"[DEBUG] collected_data: {collected_data}")
                return {
                    "type": "workflow",
                    "workflow_type": workflow_type,
                    "workflow_id": workflow_id,
                    "response": "What is the exact location?",
                    "session_id": session_id
                }
            
            # Location was provided, classify first
            from strands_tools.mbpp_workflows import MBPPWorkflowManager
            manager = MBPPWorkflowManager()
            classification = manager.classify_incident(collected_data['description'], collected_data.get('image_data'))
            
            # Only ask blocked road question for BENCANA ALAM category
            if classification['category'] == 'BENCANA ALAM':
                workflow_context['current_step'] = 3
                return {
                    "type": "workflow",
                    "workflow_type": workflow_type,
                    "workflow_id": workflow_id,
                    "response": "Is it blocking the road?",
                    "session_id": session_id,
                    "quick_replies": ["Yes", "No"]
                }
            else:
                # Skip hazard question, go directly to confirmation
                workflow_context['current_step'] = 4
                collected_data['hazard_confirmation'] = False
                
                preview = (
                    "Please confirm these details:\n\n"
                    f"**Subject:** Incident Report\n\n"
                    f"**Details:** {collected_data['description']}\n\n"
                    f"**Feedback:** {classification['feedback']}\n\n"
                    f"**Category:** {classification['category']}\n\n"
                    f"**Sub-category:** {classification['sub_category']}\n\n"
                    f"**Location:** {collected_data['location']}"
                )
                
                collected_data['preview_classification'] = classification
                return {
                    "type": "workflow",
                    "workflow_type": workflow_type,
                    "workflow_id": workflow_id,
                    "response": preview,
                    "session_id": session_id,
                    "quick_replies": ["Yes", "No"]
                }
        # Step 2: Waiting for location after description was provided
        elif collected_data.get('waiting_for_location'):
            print(f"[DEBUG] Step 2: User provided location: {message}")
            # User provided location after being asked
            collected_data['location'] = message
            del collected_data['waiting_for_location']
            workflow_context['current_step'] = 3
            
            # Classify first
            from strands_tools.mbpp_workflows import MBPPWorkflowManager
            manager = MBPPWorkflowManager()
            classification = manager.classify_incident(collected_data['description'], collected_data.get('image_data'))
            
            # Only ask blocked road question for BENCANA ALAM category
            if classification['category'] == 'BENCANA ALAM':
                workflow_context['current_step'] = 3
                return {
                    "type": "workflow",
                    "workflow_type": workflow_type,
                    "workflow_id": workflow_id,
                    "response": "Is it blocking the road?",
                    "session_id": session_id,
                    "quick_replies": ["Yes", "No"]
                }
            else:
                # Skip hazard question, go directly to confirmation
                workflow_context['current_step'] = 4
                collected_data['hazard_confirmation'] = False
                
                preview = (
                    "Please confirm these details:\n\n"
                    f"**Subject:** Incident Report\n\n"
                    f"**Details:** {collected_data['description']}\n\n"
                    f"**Feedback:** {classification['feedback']}\n\n"
                    f"**Category:** {classification['category']}\n\n"
                    f"**Sub-category:** {classification['sub_category']}\n\n"
                    f"**Location:** {collected_data['location']}"
                )
                
                collected_data['preview_classification'] = classification
                return {
                    "type": "workflow",
                    "workflow_type": workflow_type,
                    "workflow_id": workflow_id,
                    "response": preview,
                    "session_id": session_id,
                    "quick_replies": ["Yes", "No"]
                }
        # Step 3: Answer hazard question
        elif current_step == 3 and 'hazard_confirmation' not in collected_data:
            collected_data['hazard_confirmation'] = 'yes' in message.lower()
            workflow_context['current_step'] = 4
            
            # Show preview
            from strands_tools.mbpp_workflows import MBPPWorkflowManager
            manager = MBPPWorkflowManager()
            classification = manager.classify_incident(collected_data['description'], collected_data.get('image_data'))
            
            # Only show blocked road field for BENCANA ALAM
            if classification['category'] == 'BENCANA ALAM':
                preview = (
                    "Please confirm these details:\n\n"
                    f"**Subject:** Incident Report\n\n"
                    f"**Details:** {collected_data['description']}\n\n"
                    f"**Feedback:** {classification['feedback']}\n\n"
                    f"**Category:** {classification['category']}\n\n"
                    f"**Sub-category:** {classification['sub_category']}\n\n"
                    f"**Blocked road:** {'Yes' if collected_data.get('hazard_confirmation') else 'No'}\n\n"
                    f"**Location:** {collected_data['location']}"
                )
            else:
                preview = (
                    "Please confirm these details:\n\n"
                    f"**Subject:** Incident Report\n\n"
                    f"**Details:** {collected_data['description']}\n\n"
                    f"**Feedback:** {classification['feedback']}\n\n"
                    f"**Category:** {classification['category']}\n\n"
                    f"**Sub-category:** {classification['sub_category']}\n\n"
                    f"**Location:** {collected_data['location']}"
                )
            
            collected_data['preview_classification'] = classification
            return {
                "type": "workflow",
                "workflow_type": workflow_type,
                "workflow_id": workflow_id,
                "response": preview,
                "session_id": session_id,
                "quick_replies": ["Yes", "No"]
            }
        else:
            # Check if user wants to edit a field
            msg_lower = message.lower()
            if 'edit description' in msg_lower:
                collected_data['editing_field'] = 'description'
                return {
                    "type": "workflow",
                    "workflow_type": workflow_type,
                    "workflow_id": workflow_id,
                    "response": "Please provide the new description:",
                    "session_id": session_id
                }
            elif 'edit location' in msg_lower:
                collected_data['editing_field'] = 'location'
                return {
                    "type": "workflow",
                    "workflow_type": workflow_type,
                    "workflow_id": workflow_id,
                    "response": "Please provide the new location:",
                    "session_id": session_id
                }
            elif collected_data.get('editing_field'):
                # User provided new value for field
                field = collected_data['editing_field']
                if field == 'description':
                    collected_data['description'] = message
                elif field == 'location':
                    collected_data['location'] = message
                
                # Re-classify with updated data
                from strands_tools.mbpp_workflows import MBPPWorkflowManager
                manager = MBPPWorkflowManager()
                classification = manager.classify_incident(collected_data['description'], collected_data.get('image_data'))
                collected_data['preview_classification'] = classification
                collected_data.pop('editing_field', None)
                
                # Show updated preview - only show blocked road for BENCANA ALAM
                if classification['category'] == 'BENCANA ALAM':
                    preview = (
                        "Please confirm these details:\n\n"
                        f"**Subject:** Incident Report\n\n"
                        f"**Details:** {collected_data['description']}\n\n"
                        f"**Feedback:** {classification['feedback']}\n\n"
                        f"**Category:** {classification['category']}\n\n"
                        f"**Sub-category:** {classification['sub_category']}\n\n"
                        f"**Blocked road:** {'Yes' if collected_data.get('hazard_confirmation') else 'No'}\n\n"
                        f"**Location:** {collected_data['location']}"
                    )
                else:
                    preview = (
                        "Please confirm these details:\n\n"
                        f"**Subject:** Incident Report\n\n"
                        f"**Details:** {collected_data['description']}\n\n"
                        f"**Feedback:** {classification['feedback']}\n\n"
                        f"**Category:** {classification['category']}\n\n"
                        f"**Sub-category:** {classification['sub_category']}\n\n"
                        f"**Location:** {collected_data['location']}"
                    )
                
                return {
                    "type": "workflow",
                    "workflow_type": workflow_type,
                    "workflow_id": workflow_id,
                    "response": preview,
                    "session_id": session_id,
                    "quick_replies": ["Yes", "No"]
                }
            elif 'no' in msg_lower:
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
                "status": "open",
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
        
        # Let the agent call retrieve tool itself
        agent_result = self.rag_agent(message)
        
        # Extract text from AgentResult object
        if hasattr(agent_result, 'data'):
            response = agent_result.data
        elif hasattr(agent_result, 'content'):
            response = agent_result.content
        else:
            response = str(agent_result)
        
        # Strip source citations from response
        response = self._strip_source_citations(response)
        
        return {
            "type": "rag",
            "response": response,
            "session_id": session_id
        }
    
    def _strip_source_citations(self, text: str) -> str:
        """Remove source citations from response text"""
        import re
        # Remove patterns like "Sources: Document 1" or "Sumber: Document 1"
        text = re.sub(r'\n*(Sources?|Sumber):\s*Document[^\n]*', '', text, flags=re.IGNORECASE)
        # Remove patterns like "(Document 1)" or "[Document 1]"
        text = re.sub(r'[\(\[]Document\s+\d+[\)\]]', '', text)
        # Remove trailing whitespace
        return text.strip()
    

    
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
