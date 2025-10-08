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
        
        # Use workflow agent to start the workflow
        prompt = f"""Start a {workflow_type} workflow.
        User message: {message}
        Has image: {has_image}
        
        Use the mbpp_workflow tool to initiate the workflow."""
        
        try:
            response = self.workflow_agent(prompt)
            response_text = str(response.content) if hasattr(response, 'content') else str(response)
        except Exception as e:
            print(f"Workflow agent error: {e}")
            response_text = f"Started {workflow_type} workflow. Please provide the required information."
        
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
        
        # Build context for the agent
        prompt = f"""Continue the {workflow_type} workflow (ID: {workflow_id}).
        Current step: {current_step}
        User response: {message}
        Has image: {has_image}
        Location provided: {location is not None}
        
        Use the mbpp_workflow tool to process this step and move to the next."""
        
        try:
            response = self.workflow_agent(prompt)
            response_text = str(response.content) if hasattr(response, 'content') else str(response)
        except Exception as e:
            print(f"Workflow continuation error: {e}")
            response_text = "Processing your response. Please continue."
            response = response_text
        
        # Update workflow context
        workflow_context["current_step"] += 1
        workflow_context["data"]["last_message"] = message
        
        # Check if workflow is completed
        if "completed" in str(response).lower() or "ticket has been logged" in str(response).lower():
            # Clean up completed workflow
            del self.active_workflows[session_id]
            return {
                "type": "workflow_complete",
                "workflow_type": workflow_type,
                "workflow_id": workflow_id,
                "response": response,
                "session_id": session_id
            }
        
        return {
            "type": "workflow",
            "workflow_type": workflow_type,
            "workflow_id": workflow_id,
            "response": response,
            "session_id": session_id
        }
    
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
        """Search OpenSearch knowledge base"""
        try:
            # Import vector search handler
            from vector_search import search_documents
            
            results = search_documents(
                query=query,
                index_name=os.environ.get('OPENSEARCH_INDEX', 'mbpp-documents'),
                top_k=5
            )
            return results
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
