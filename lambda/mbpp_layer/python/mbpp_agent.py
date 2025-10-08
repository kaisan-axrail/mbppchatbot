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
        """Start a new workflow"""
        import uuid
        workflow_id = str(uuid.uuid4())
        
        # Store workflow context
        self.active_workflows[session_id] = {
            "workflow_id": workflow_id,
            "workflow_type": workflow_type,
            "current_step": 1,
            "data": {
                "initial_message": message,
                "has_image": has_image,
                "image_data": image_data
            }
        }
        
        # Call workflow manager directly
        result = mbpp_workflow(
            action="start",
            workflow_type=workflow_type,
            workflow_id=workflow_id,
            data={"image": image_data} if has_image else {},
            message=message,
            has_image=has_image
        )
        
        response_text = result.get('message', 'Workflow started')
        
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
        """Continue an existing workflow"""
        workflow_context = self.active_workflows[session_id]
        workflow_id = workflow_context["workflow_id"]
        workflow_type = workflow_context["workflow_type"]
        current_step = workflow_context["current_step"]
        
        # Determine next action based on workflow type and step
        action = self._get_workflow_action(workflow_type, current_step, message)
        data = self._extract_workflow_data(workflow_type, current_step, message, workflow_context)
        
        # Call workflow manager directly
        result = mbpp_workflow(
            action=action,
            workflow_type=workflow_type,
            workflow_id=workflow_id,
            data=data
        )
        
        response_text = result.get('message', '')
        
        # Update workflow context
        workflow_context["current_step"] += 1
        workflow_context["data"]["last_message"] = message
        
        # Check if workflow is completed
        if result.get('status') == 'success' and 'ticket_number' in result:
            del self.active_workflows[session_id]
            return {
                "type": "workflow_complete",
                "workflow_type": workflow_type,
                "workflow_id": workflow_id,
                "response": response_text,
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
