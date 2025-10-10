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
    
    def classify_incident(self, description: str, image_data: Optional[str] = None) -> Dict[str, str]:
        """Classify incident from description and/or image into feedback, category, and sub_category using AI."""
        print(f"[CLASSIFY] Starting classification - has_image: {bool(image_data)}")
        try:
            bedrock = boto3.client('bedrock-runtime', region_name=os.environ.get('BEDROCK_REGION', 'us-east-1'))
            
            content = []
            # Skip image if too large to avoid timeout
            if image_data:
                print(f"[CLASSIFY] Image data length: {len(image_data)}")
                if image_data.startswith('data:image'):
                    image_data = image_data.split(',')[1]
                # Only include image if reasonable size (< 1MB base64)
                if len(image_data) < 1000000:
                    content.append({
                        "type": "image",
                        "source": {"type": "base64", "media_type": "image/jpeg", "data": image_data}
                    })
                    print(f"[CLASSIFY] Image included in classification")
                else:
                    print(f"[CLASSIFY] Image too large, skipping vision analysis")
            
            prompt = f"""Analyze this incident and classify it into:
1. Feedback type: Aduan, Cadangan, Penghargaan, or Pertanyaan
2. Category: ALAM SEKITAR, BANGUNAN, BENCANA ALAM, BINATANG, CUKAI PINTU, DISPLIN, GANGGUAN, HALANGAN, JALAN, KEBERSIHAN, KEMUDAHAN AWAM, LETAK KERETA, PENYELENGGARAAN HARTA, PERNIAGAAN, POKOK, PORTAL E-PERJAWATAN, or PUSAT HIBURAN
3. Subcategory based on the category

Description: "{description}"

Respond in JSON format only:
{{"feedback": "...", "category": "...", "sub_category": "..."}}"""
            content.append({"type": "text", "text": prompt})
            
            print(f"[CLASSIFY] Calling Bedrock API...")
            response = bedrock.invoke_model(
                modelId='anthropic.claude-3-5-sonnet-20240620-v1:0',
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 100,
                    "messages": [{"role": "user", "content": content}]
                })
            )
            
            result = json.loads(response['body'].read())
            text = result['content'][0]['text'].strip()
            print(f"[CLASSIFY] API response: {text}")
            
            # Parse JSON response
            import re
            json_match = re.search(r'\{[^}]+\}', text)
            if json_match:
                classification = json.loads(json_match.group())
                result = {
                    "feedback": classification.get("feedback", "Aduan"),
                    "category": classification.get("category", "JALAN"),
                    "sub_category": classification.get("sub_category", "--")
                }
                print(f"[CLASSIFY] Success: {result}")
                return result
        except Exception as e:
            print(f"[CLASSIFY] ERROR: {e}")
            import traceback
            traceback.print_exc()
        
        print(f"[CLASSIFY] Returning default classification")
        return {"feedback": "Aduan", "category": "JALAN", "sub_category": "--"}
    
    def _classify_feedback_old(self, description: str, image_data: Optional[str] = None) -> str:
        """Use AI to classify feedback type: Aduan, Cadangan, Penghargaan, or Pertanyaan"""
        try:
            bedrock = boto3.client('bedrock-runtime', region_name=os.environ.get('BEDROCK_REGION', 'us-east-1'))
            
            content = []
            if image_data:
                if image_data.startswith('data:image'):
                    image_data = image_data.split(',')[1]
                content.append({
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/jpeg", "data": image_data}
                })
            
            prompt = f"""Classify this incident into ONE of these feedback types:
- Aduan (Complaint about problems/issues)
- Cadangan (Suggestion for improvement)
- Penghargaan (Appreciation/praise)
- Pertanyaan (Question/inquiry)

Description: "{description}"

Respond with ONLY ONE WORD: Aduan, Cadangan, Penghargaan, or Pertanyaan."""
            content.append({"type": "text", "text": prompt})
            
            response = bedrock.invoke_model(
                modelId='anthropic.claude-3-5-sonnet-20240620-v1:0',
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 10,
                    "messages": [{"role": "user", "content": content}]
                })
            )
            
            result = json.loads(response['body'].read())
            feedback = result['content'][0]['text'].strip()
            
            valid_feedbacks = ['Aduan', 'Cadangan', 'Penghargaan', 'Pertanyaan']
            if feedback in valid_feedbacks:
                return feedback
            return 'Aduan'
        except Exception as e:
            print(f"Feedback classification error: {e}")
            return 'Aduan'
    
    def _classify_category_old(self, description: str, image_data: Optional[str] = None) -> str:
        """Use AI to classify category from the MBPP category list"""
        try:
            bedrock = boto3.client('bedrock-runtime', region_name=os.environ.get('BEDROCK_REGION', 'us-east-1'))
            
            content = []
            if image_data:
                if image_data.startswith('data:image'):
                    image_data = image_data.split(',')[1]
                content.append({
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/jpeg", "data": image_data}
                })
            
            prompt = f"""Classify this incident into ONE of these categories:
- ALAM SEKITAR (Environment)
- BANGUNAN (Building)
- BENCANA ALAM (Natural Disaster)
- BINATANG (Animals)
- CUKAI PINTU (Property Tax)
- DISPLIN (Discipline)
- GANGGUAN (Disturbance)
- HALANGAN (Obstruction)
- JALAN (Road)
- KEBERSIHAN (Cleanliness)
- KEMUDAHAN AWAM (Public Facilities)
- LETAK KERETA (Parking)
- PENYELENGGARAAN HARTA (Property Maintenance)
- PERNIAGAAN (Business)
- POKOK (Trees)
- PORTAL E-PERJAWATAN (E-Portal)
- PUSAT HIBURAN (Entertainment Center)

Description: "{description}"

Respond with ONLY the category name (e.g., JALAN, BENCANA ALAM, etc.)."""
            content.append({"type": "text", "text": prompt})
            
            response = bedrock.invoke_model(
                modelId='anthropic.claude-3-5-sonnet-20240620-v1:0',
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 20,
                    "messages": [{"role": "user", "content": content}]
                })
            )
            
            result = json.loads(response['body'].read())
            category = result['content'][0]['text'].strip().upper()
            
            valid_categories = [
                'ALAM SEKITAR', 'BANGUNAN', 'BENCANA ALAM', 'BINATANG',
                'CUKAI PINTU', 'DISPLIN', 'GANGGUAN', 'HALANGAN', 'JALAN',
                'KEBERSIHAN', 'KEMUDAHAN AWAM', 'LETAK KERETA',
                'PENYELENGGARAAN HARTA', 'PERNIAGAAN', 'POKOK',
                'PORTAL E-PERJAWATAN', 'PUSAT HIBURAN'
            ]
            
            if category in valid_categories:
                return category
            return 'JALAN'
        except Exception as e:
            print(f"Category classification error: {e}")
            return 'JALAN'
    
    def _classify_subcategory_old(self, description: str, category: str, image_data: Optional[str] = None) -> str:
        """Use AI to classify subcategory based on the main category"""
        # Subcategory mapping
        subcategories = {
            'ALAM SEKITAR': ['KERJA TANAH'],
            'BANGUNAN': [
                'TUKARGUNA BANGUNAN/PREMIS', 'HOME STAY', 'PINDAAN/TAMBAHAN',
                'MASALAH PROJEK PEMAJUAN', 'BENGKEL/SETOR TANPA IZIN',
                'BANGUNAN/PREMIS TANPA IZIN', 'BANGUNAN USANG/TERBIAR/RUNTUH',
                'BANGUNAN IBADAT TANPA IZIN', 'MENARA TELEKOMUNIKASI',
                'TEMBOK PENGHADANG', 'GERAI TANPA IZIN',
                'PERAKUAN KELAYAKAN MENDUDUKI/OC', 'PERMOHONAN MERANCANG SISTEM 3.0 PLUS'
            ],
            'BENCANA ALAM': ['BANJIR', 'TANAH RUNTUH', 'POKOK TUMBANG'],
            'BINATANG': [
                'ANJING LIAR / TIDAK BERLESEN', 'BURUNG MERPATI/GAGAK', 'NYAMUK',
                'KUCING LIAR', 'KACAU GANGGU SERANGGA', 'LEMBU/KAMBING/KERBAU/KUDA/UNTA',
                'TIKUS', 'KACAU GANGGU LAIN-LAIN BINATANG', 'BURUNG WALIT'
            ],
            'CADANGAN': ['PELBAGAI'],
            'CUKAI PINTU': [
                'BIL CUKAI TAKSIRAN', 'BIL CUKAI TERTUNGGAK', 'BIL CUKAI BANTAHAN',
                'BIL CUKAI TIDAK DITERIMA', 'TUKAR NAMA PEMILIK', 'BIL CUKAI PEMBETULAN MAKLUMAT',
                'MASALAH CUKAI TAKSIRAN', 'TUKAR ALAMAT', 'TUKAR NAMA'
            ],
            'DISIPLIN': ['MASALAH KAKITANGAN MAJLIS'],
            'GANGGUAN': ['KACAUGANGGU BISING', 'KACAUGANGGU KESIHATAN AWAM'],
            'HALANGAN': [
                'PERLETAKAN KENDERAAN TEPI JALAN', 'KENDERAAN LAMA', 'HALANGAN DI TEPI JALAN',
                'HALANGAN DALAM PETAK LETAK KERETA', 'MELETAK KERETA DILUAR PETAK',
                'KENDERAAN BERAT (BAS/LORI)', 'KAKI LIMA', 'KERUSI MEJA',
                'PROSES TUNDA', 'PROSES KAPIT'
            ],
            'JALAN': [
                'JALAN ROSAK/BERLUBANG', 'BAHU JALAN ROSAK/BERLUBANG', 'MASALAH LALULINTAS',
                'LUBANG / MANHOLE ROSAK/HILANG', 'PAPAN TANDA TRAFIK ROSAK/HILANG',
                'KOREKAN JALAN', 'PAPAN TANDA NAMA JALAN ROSAK/HILANG',
                'GEGILI JALAN ROSAK/PECAH', 'BAHU JALAN RUMPUT PANJANG', 'BONGGOL JALAN'
            ],
            'KEBERSIHAN': [
                'SAMPAH DOMESTIK TAK KUTIP', 'PARIT TERSUMBAT', 'KEKOTORAN JALAN',
                'SAMPAH KEBUN TAK KUTIP', 'LONGGOKAN SAMPAH TANPA IZIN',
                'KUTIPAN SAMPAH TIDAK MENGIKUT JADUAL', 'SAMPAH PUKAL TAK KUTIP',
                'PEMOTONGAN RUMPUT TEPI JALAN', 'RUMAH KOSONG SEMAK SAMUN',
                'TANAH KOSONG SEMAK SAMUN', 'LONGGOKAN SISA BINAAN', 'TIADA TONG SAMPAH',
                'KEKOTORAN PREMIS MAKANAN', 'PENEMPATAN TONG SAMPAH TIDAK SESUAI',
                'MASALAH KOMPLEK/PASAR/TPS', 'TANDAS AWAM KOTOR', 'KERACUNAN MAKANAN',
                'SCHOOL', 'KAMPUNG', 'PENGKALAN'
            ],
            'PENGHARGAAN': ['PELBAGAI'],
            'PERTANYAAN': ['PELBAGAI'],
            'PORTAL E-PERJAWATAN': ['PERTANYAAN/ ADUAN JAWATAN KOSONG'],
            'KEMUDAHAN AWAM': [
                'LAMPU JALAN TIDAK MENYALA', 'PARIT ROSAK/RUNTUH', 'LAMPU ISYARAT ROSAK',
                'PADANG PERMAINAN ADA SAMPAH', 'PADANG PERMAINAN RUMPUT PANJANG',
                'PERALATAN PERMAINAN ROSAK', 'PERHENTIAN BAS ROSAK',
                'PERMOHONAN PENGHADANG JALAN', 'TIMER LAMPU JALAN ROSAK',
                'PERMOHONAN CERMIN FISH EYE', 'PERALATAN TANDAS AWAM ROSAK', 'CCTV',
                'MEROSAKAN HARTA AWAM', 'SALAHGUNA KAWASAN LAPANG',
                'PERKHIDMATAN BAS SHUTTLE', 'PENYELENGGARAAN FREE TRADE ZONE',
                'KEROSAKAN LAMPU TAMAN MBPP', 'PENUTUP PARIT ROSAK', 'PENUTUP PARIT HILANG'
            ],
            'LETAK KERETA': [
                'KOMPAUN', 'BAYARAN KOMPAUN', 'PSP', 'KEKURANGAN PETAK LETAK KERETA',
                'PETAK LETAK KERETA KURANG JELAS', 'KOMPAUN TRAFIK'
            ],
            'PENYELENGGARAAN HARTA': [
                'MASALAH COB', 'GERAI MAJLIS', 'BANGUNAN MAJLIS', 'PERUMAHAN AWAM',
                'KEGUNAAN TANAH MAJLIS', 'PENCEROBOHAN TANAH MAJLIS'
            ],
            'PERNIAGAAN': [
                'TIDAK MEMATUHI SYARAT PERLESENAN', 'KACAU GANGGU PENJAJA',
                'PERNIAGAAN TANPA LESEN', 'PENJAJA TANPA LESEN', 'PENGIKLANAN TANPA LESEN'
            ],
            'POKOK': ['PEMANGKASAN POKOK', 'PENEBANGAN POKOK', 'PENYELENGGARAAN LANDSKAP'],
            'PUSAT HIBURAN': [
                'BEROPERASI LEBIH MASA', 'GEJALA SOSIAL', 'PUSAT HIBURAN TIDAK BERLESEN', 'CYBERCAFE'
            ]
        }
        
        # If category has no subcategories defined, return --
        if category not in subcategories:
            return '--'
        
        try:
            bedrock = boto3.client('bedrock-runtime', region_name=os.environ.get('BEDROCK_REGION', 'us-east-1'))
            
            subs = subcategories[category]
            subs_list = '\n'.join([f"- {s}" for s in subs])
            
            content = []
            if image_data:
                if image_data.startswith('data:image'):
                    image_data = image_data.split(',')[1]
                content.append({
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/jpeg", "data": image_data}
                })
            
            prompt = f"""Classify this incident into ONE of these subcategories for {category}:
{subs_list}

Description: "{description}"

Respond with ONLY the subcategory name."""
            content.append({"type": "text", "text": prompt})
            
            response = bedrock.invoke_model(
                modelId='anthropic.claude-3-5-sonnet-20240620-v1:0',
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 50,
                    "messages": [{"role": "user", "content": content}]
                })
            )
            
            result = json.loads(response['body'].read())
            sub_category = result['content'][0]['text'].strip().upper()
            
            if sub_category in [s.upper() for s in subs]:
                return sub_category
            return subs[0]
        except Exception as e:
            print(f"Subcategory classification error: {e}")
            return subcategories[category][0] if category in subcategories else '--'
    
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
            key = f"incidents/{uuid.uuid4()}.jpg"
            
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
            return {"status": "success", "step": 2, "message": "Can you please confirm if your internet connection is working properly?", "options": ["Yes", "No"], "workflow_id": workflow_id}
        
        elif action == "step3_verify":
            workflow = self.workflows.get(workflow_id)
            workflow["current_step"] = 3
            workflow["data"]["verification"] = data.get("verification")
            
            # Classify complaint
            classification = self.classify_incident(
                workflow["data"]["description"],
                workflow["data"].get("image")
            )
            
            ticket_number = self._generate_ticket_number()
            ticket = {
                "ticket_number": ticket_number,
                "subject": "Service Error",
                "details": workflow["data"]["description"],
                "feedback": classification["feedback"],
                "category": classification["category"],
                "sub_category": classification["sub_category"],
                "created_at": datetime.now().isoformat()
            }
            
            workflow["ticket_number"] = ticket_number
            workflow["ticket_details"] = ticket
            
            preview = (
                "Please confirm these details:\n\n"
                f"**Feedback:** {ticket['feedback']}\n\n"
                f"**Subject:** {ticket['subject']}\n\n"
                f"**Details:** {ticket['details']}\n\n"
                f"**Category:** {ticket['category']} - {ticket['sub_category']}\n\n"
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
            return {"status": "success", "step": 1, "message": "Please share an image of the incident, the location and describe what happened. You may also share your location to make it easier.\n\n(e.g. I would like to complain about a pothole at Jalan Penang, 10000, Georgetown)", "workflow_id": workflow_id}
        
        elif action == "step2_submit_info":
            workflow = self.workflows.get(workflow_id)
            workflow["current_step"] = 2
            workflow["data"]["description"] = data.get("description")
            workflow["data"]["location"] = data.get("location")
            workflow["data"]["image"] = data.get("image")
            
            # If image is provided, switch to image_incident workflow
            if workflow["data"].get("image"):
                return {"status": "switch_workflow", "new_workflow_type": "image_incident", "message": "Image detected. Switching to image incident workflow.", "workflow_id": workflow_id}
            
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
            classification = self.classify_incident(
                workflow["data"]["description"],
                workflow["data"].get("image")
            )
            
            ticket_number = self._generate_ticket_number()
            ticket = {
                "ticket_number": ticket_number,
                "subject": "Incident Report",
                "details": workflow["data"]["description"],
                "location": workflow["data"]["location"],
                "feedback": classification["feedback"],
                "category": classification["category"],
                "sub_category": classification["sub_category"],
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
Feedback: {ticket['feedback']}
Category: {ticket['category']} - {ticket['sub_category']}

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
            
            # Classify incident from description and image
            classification = self.classify_incident(
                workflow["data"]["description"],
                workflow["data"].get("image")
            )
            
            ticket_number = self._generate_ticket_number()
            ticket = {
                "ticket_number": ticket_number,
                "subject": data.get("subject", "Incident Report"),
                "details": workflow["data"]["description"],
                "location": workflow["data"]["location"],
                "feedback": classification["feedback"],
                "category": classification["category"],
                "sub_category": classification["sub_category"],
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
