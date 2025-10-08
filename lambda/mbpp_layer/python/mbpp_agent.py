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
from strands import Agent
from strands_tools import workflow
from strands_tools.mbpp_workflows import mbpp_workflow
import boto3

class MBPPAgent:
    """Main MBPP Agent that handles workflows and RAG queries"""
    
    def __init__(self):
        # Initialize Bedrock client
        self.bedrock_runtime = boto3.client(
            'bedrock-runtime',
            region_name=os.environ.get('BEDROCK_REGION', 'us-east-1')
        )
        
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
        
        self.rag_agent = Agent(
            system_prompt="""You are an MBPP knowledge assistant. Communicate ONLY in English.
            Help users find information from MBPP documents and answer general questions.
            Provide accurate, helpful responses in English only.
            If you don't know something, say so clearly.""",
            model="anthropic.claude-3-5-sonnet-20240620-v1:0"
        )
        
        # Track active workflows
        self.active_workflows = {}
    
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
            return self._continue_workflow(session_id, message, has_image, image_data, location)
        
        # Detect if this is a workflow trigger or RAG question
        workflow_type = self._detect_intent(message, has_image)
        
        if workflow_type in ["complaint", "text_incident", "image_incident"]:
            return self._start_workflow(session_id, workflow_type, message, has_image, image_data)
        else:
            return self._handle_rag_query(message, session_id)
    
    def _detect_intent(self, message: str, has_image: bool) -> str:
        """Detect user intent - workflow or RAG query"""
        # If image is uploaded, trigger image incident workflow immediately
        if has_image:
            return "image_incident"
        
        message_lower = message.lower()
        
        # Workflow triggers
        incident_keywords = ['incident', 'report', 'emergency', 'hazard', 'fallen tree', 
                            'pothole', 'flood', 'accident', 'blocking', 'complaint']
        
        complaint_keywords = ['complaint', 'feedback', 'service error', 'system down', 
                             'website', 'not working', 'issue', 'problem']
        
        has_incident = any(keyword in message_lower for keyword in incident_keywords)
        has_complaint = any(keyword in message_lower for keyword in complaint_keywords)
        
        if has_incident and not has_complaint:
            return "text_incident"
        elif has_complaint:
            return "complaint"
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
            response_text = "Please describe what happened."
        
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
        
        # Handle image incident confirmation (step 0)
        collected_data = workflow_context["data"]
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
                # User selected service complaint
                del self.active_workflows[session_id]
                return {
                    "type": "workflow",
                    "workflow_type": "complaint",
                    "workflow_id": workflow_id,
                    "response": "Please describe the service issue or feedback.",
                    "session_id": session_id
                }
        
        # Use AI to understand user response and determine next step
        prompt = f"""You are helping collect incident report information.

Collected so far:
- Description: {collected_data.get('description', 'NOT YET')}
- Location: {collected_data.get('location', 'NOT YET')}
- Hazard: {collected_data.get('hazard_confirmation', 'NOT YET')}

User just said: "{message}"

Respond with ONLY JSON:
{{"field": "description/location/hazard/confirmation", "value": "extracted value", "next_step": "description/location/hazard/confirm/complete", "next_question": "what to ask next or empty if complete"}}

Rules:
- If missing description, next_step=description
- If missing location, next_step=location
- If missing hazard, next_step=hazard (generate contextual yes/no question based on incident type - e.g., for fallen tree ask "Is it blocking the road?", for pothole ask "Is it causing danger to vehicles?", for flood ask "Is access blocked?")
- If all collected, next_step=confirm (show ticket preview)
- If user confirms ticket, next_step=complete"""
        
        try:
            response = self.bedrock_runtime.invoke_model(
                modelId='anthropic.claude-3-5-sonnet-20240620-v1:0',
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 400,
                    "messages": [{"role": "user", "content": prompt}]
                })
            )
            result = json.loads(response['body'].read())
            ai_response = json.loads(result['content'][0]['text'])
            
            # Update workflow data - store the actual user message
            field = ai_response.get('field')
            value = ai_response.get('value')
            next_step = ai_response.get('next_step')
            
            if field == 'description':
                workflow_context['data']['description'] = message  # Store actual message
            elif field == 'location':
                workflow_context['data']['location'] = message  # Store actual message
            elif field == 'hazard':
                workflow_context['data']['hazard_confirmation'] = 'yes' in message.lower()
            elif field == 'confirmation':
                if 'no' in value.lower():
                    # Restart
                    workflow_context['current_step'] = 1
                    workflow_context['data'] = {}
                    return {
                        "type": "workflow",
                        "workflow_type": workflow_type,
                        "workflow_id": workflow_id,
                        "response": "Let's start over. Please describe what happened.",
                        "session_id": session_id
                    }
            
            # Handle completion
            if next_step == 'complete':
                # Save ticket
                from strands_tools.mbpp_workflows import MBPPWorkflowManager
                manager = MBPPWorkflowManager()
                classification = manager.classify_incident(workflow_context['data']['description'])
                
                ticket_number = manager._generate_ticket_number()
                ticket = {
                    "ticket_number": ticket_number,
                    "subject": "Incident Report",
                    "details": workflow_context['data']['description'],
                    "location": workflow_context['data']['location'],
                    "feedback": classification["feedback"],
                    "category": classification["category"],
                    "sub_category": classification["sub_category"],
                    "blocked_road": workflow_context['data'].get('hazard_confirmation', False),
                    "created_at": datetime.now().isoformat()
                }
                
                manager._save_report(ticket)
                manager._create_event('incident_created', ticket_number, workflow_context['data'])
                
                del self.active_workflows[session_id]
                return {
                    "type": "workflow_complete",
                    "workflow_type": workflow_type,
                    "workflow_id": workflow_id,
                    "response": f"Thank you for your submission! Your reference number is {ticket_number}",
                    "session_id": session_id
                }
            
            # Handle ticket preview
            if next_step == 'confirm':
                from strands_tools.mbpp_workflows import MBPPWorkflowManager
                manager = MBPPWorkflowManager()
                classification = manager.classify_incident(workflow_context['data']['description'])
                ticket_number = manager._generate_ticket_number()
                
                preview = f"""Please confirm these details:

Ticket #: {ticket_number}
Description: {workflow_context['data']['description']}
Location: {workflow_context['data']['location']}
Category: {classification['category']} - {classification['sub_category']}
Blocking Road: {'Yes' if workflow_context['data'].get('hazard_confirmation') else 'No'}

Is this correct? (Yes/No)"""
                
                workflow_context['data']['preview_ticket'] = ticket_number
                return {
                    "type": "workflow",
                    "workflow_type": workflow_type,
                    "workflow_id": workflow_id,
                    "response": preview,
                    "session_id": session_id
                }
            
            response_text = ai_response.get('next_question', '')
            workflow_context["current_step"] += 1
            
        except Exception as e:
            print(f"AI workflow error: {e}")
            response_text = "Could you please provide more details?"
        
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
        """Handle RAG-based question answering"""
        # Check if we need to search knowledge base
        if self._needs_knowledge_base(message):
            # Perform vector search
            search_results = self._search_knowledge_base(message)
            
            # Build context with search results
            context = self._build_rag_context(search_results)
            
            prompt = f"""Answer the following question using the provided context.
            
Context:
{context}

Question: {message}

Provide a clear, accurate answer based on the context. If the context doesn't contain
relevant information, say so clearly."""
            
            response = self.rag_agent(prompt)
        else:
            # Direct question without knowledge base
            response = self.rag_agent(message)
        
        return {
            "type": "rag",
            "response": response,
            "session_id": session_id
        }
    
    def _needs_knowledge_base(self, message: str) -> bool:
        """Determine if query needs knowledge base search"""
        # Simple heuristic - can be enhanced
        question_words = ['what', 'how', 'when', 'where', 'who', 'why', 'which']
        message_lower = message.lower()
        return any(word in message_lower for word in question_words)
    
    def _search_knowledge_base(self, query: str) -> list:
        """Search Bedrock Knowledge Base"""
        try:
            kb_ids = ['U6EAI0DHJC', 'CTFE3RJR01']
            all_results = []
            
            bedrock_agent = boto3.client(
                'bedrock-agent-runtime',
                region_name=os.environ.get('BEDROCK_REGION', 'us-east-1')
            )
            
            for kb_id in kb_ids:
                try:
                    response = bedrock_agent.retrieve(
                        knowledgeBaseId=kb_id,
                        retrievalQuery={'text': query},
                        retrievalConfiguration={
                            'vectorSearchConfiguration': {
                                'numberOfResults': 3
                            }
                        }
                    )
                    
                    for result in response.get('retrievalResults', []):
                        all_results.append({
                            'content': result.get('content', {}).get('text', ''),
                            'source': result.get('location', {}).get('s3Location', {}).get('uri', 'unknown'),
                            'score': result.get('score', 0.0)
                        })
                except Exception as kb_error:
                    print(f"Failed to query KB {kb_id}: {kb_error}")
            
            # Sort by score and return top 5
            all_results.sort(key=lambda x: x['score'], reverse=True)
            return all_results[:5]
        except Exception as e:
            print(f"Knowledge base search error: {e}")
            return []
    
    def _build_rag_context(self, search_results: list) -> str:
        """Build context from search results"""
        if not search_results:
            return "No relevant information found in knowledge base."
        
        context_parts = []
        for i, result in enumerate(search_results, 1):
            context_parts.append(f"[Document {i}]")
            context_parts.append(result.get('content', ''))
            context_parts.append("")
        
        return "\n".join(context_parts)
    
    def get_workflow_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get status of active workflow for a session"""
        return self.active_workflows.get(session_id)
    
    def cancel_workflow(self, session_id: str) -> bool:
        """Cancel an active workflow"""
        if session_id in self.active_workflows:
            del self.active_workflows[session_id]
            return True
        return False


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
        
        # Initialize agent
        agent = MBPPAgent()
        
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
