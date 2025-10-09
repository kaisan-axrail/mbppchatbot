# Complete Workflow Flows

## FLOW 1: Service/System Complaint Workflow (Image Upload)

**Trigger:** User uploads an image

### Step-by-Step Flow:

1. **Image Detection**
   - User: [Uploads image of error screen/service issue]
   - System detects: Image uploaded
   - Bot: "Image detected. Can you confirm you would like to report an incident?"
   - Quick Replies: [Yes, report an incident] [Not an incident (Service Complaint / Feedback)]

2. **Not an Incident Selected**
   - User: "Not an incident (Service Complaint / Feedback)"
   - Bot stores: Image data
   - Bot: "Thank you for your feedback. Could you please describe the issue or service/system error?\n\n(e.g. I want to complain about slow response times on a government website.)"

3. **Issue Description**
   - User: "MBPP website service down without notice"
   - Bot stores: Description

4. **Verification Check**
   - Bot: "Can you please confirm if your internet connection is working properly?"
   - Quick Replies: [✅ Yes] [❌ No]
   - User: "Yes"
   - Bot stores: Verification = Yes

5. **Ticket Preview**
   - Bot shows preview:
     ```
     Please confirm these details:
     
     **Subject:** Service Error
     **Details:** MBPP website service down without notice
     **Category:** Service/ System Error
     **Internet verified:** Yes
     
     Is this correct?
     ```
   - Quick Replies: [✅ Yes, submit] [❌ No, start over]

6. **Final Confirmation**
   - User: "Yes"
   - Bot: Saves image to S3 (s3://mbpp-incident-images-{account}/complaints/{ticket_number}/...)
   - Bot: Saves ticket to DynamoDB with image_url
   - Bot: "Thank you for your submission! Your reference number is 20239/2025/01/09"

---

## FLOW 2: Text-Driven Incident Report Workflow

**Trigger:** User types "I want to report an incident"

### Step-by-Step Flow:

1. **Initial Trigger**
   - User: "I want to report an incident"
   - System detects: Incident keywords
   - Bot: "Please share an image of the incident, the location and describe what happened. You may also share your location to make it easier.

(e.g. I would like to complain about a pothole at Jalan Penang, 10000, Georgetown)"

2. **Image Upload**
   - User: [Uploads image of fallen tree]
   - Bot stores: Image data
   - Bot: "Please describe what happened and tell us the location. You may also share your live location to make it easier.

(e.g. I want to complain about a pothole at Jalan Penang, 10000, Georgetown)"

3. **Description & Location Collection (Combined)**
   - User: "I want to report a fallen tree that is blocking the main road at Jalan Batu Feringghi, 11100"
   - Bot: Uses AI to extract description and location from the message
   - AI extracts:
     - Description: "I want to report a fallen tree that is blocking the main road"
     - Location: "Jalan Batu Feringghi, 11100"
   - Bot stores: Both description and location
   - Bot: Uses AI to analyze description and generate contextual hazard question
   - AI analyzes: "fallen tree that is blocking the main road"
   - Bot: "Is it blocking the main road?" (or similar contextual question)
   - Quick Replies: [Yes] [No]

4. **Hazard Confirmation**
   - User: "Yes"
   - Bot stores: Hazard confirmation = Yes
   - Bot: Uses AI to classify incident based on description
   - AI classifies: Category = "Bencana Alam", Sub-category = "Pokok Tumbang"

5. **Ticket Preview**
   - Bot shows preview:
     ```
     Please confirm these details:
     
     **Subject:** Incident Report
     **Details:** I want to report a fallen tree that is blocking the main road
     **Feedback:** Aduan
     **Category:** Bencana Alam
     **Sub-category:** Pokok Tumbang
     **Blocked road:** Yes
     **Location:** Jalan Batu Feringghi, 11100
     
     Is this correct?
     ```
   - Quick Replies: [✅ Yes, submit] [❌ No, start over]

6. **Final Confirmation**
   - User: "Yes"
   - Bot: Saves image to S3 (s3://mbpp-incident-images-{account}/incidents/{ticket_number}/...)
   - Bot: Saves ticket to DynamoDB with image_url
   - Bot: "Thank you for your submission! Your reference number is 20368/2025/01/09"

---

## FLOW 3: Image-Driven Incident Report Workflow

**Trigger:** User uploads an image

### Step-by-Step Flow:

1. **Image Detection**
   - User: [Uploads image of fallen tree]
   - System detects: Image uploaded
   - Bot: "Image detected. Can you confirm you would like to report an incident?"
   - Quick Replies: [Yes, report an incident] [Not an incident (Service Complaint / Feedback)]

2. **Yes, Report an Incident Selected**
   - User: "Yes, report an incident"
   - Bot stores: Image data
   - Bot: "Please describe what happened and tell us the location. You may also share your live location to make it easier.

(e.g. I want to complain about a pothole at Jalan Penang, 10000, Georgetown)"

3. **Description & Location Collection (Combined)**
   - User: "I want to report a fallen tree that is blocking the main road at Jalan Batu Feringghi, 11100"
   - Bot: Uses AI to extract description and location from the message
   - AI extracts:
     - Description: "I want to report a fallen tree that is blocking the main road"
     - Location: "Jalan Batu Feringghi, 11100"
   - Bot stores: Both description and location
   - Bot: Uses AI to analyze description and generate contextual hazard question
   - AI analyzes: "fallen tree that is blocking the main road"
   - Bot: "Is it blocking the main road?" (or similar contextual question)
   - Quick Replies: [Yes] [No]

4. **Hazard Confirmation**
   - User: "Yes"
   - Bot stores: Hazard confirmation = Yes
   - Bot: Uses AI to classify incident based on description
   - AI classifies: Category = "Bencana Alam", Sub-category = "Pokok Tumbang"

5. **Ticket Preview**
   - Bot shows preview:
     ```
     Please confirm these details:
     
     **Subject:** Incident Report
     **Details:** I want to report a fallen tree that is blocking the main road
     **Feedback:** Aduan
     **Category:** Bencana Alam
     **Sub-category:** Pokok Tumbang
     **Blocked road:** Yes
     **Location:** Jalan Batu Feringghi, 11100
     
     Is this correct?
     ```
   - Quick Replies: [✅ Yes, submit] [❌ No, start over]

6. **Final Confirmation**
   - User: "Yes"
   - Bot: Saves image to S3 (s3://mbpp-incident-images-{account}/incidents/{ticket_number}/...)
   - Bot: Saves ticket to DynamoDB with image_url
   - Bot: "Thank you for your submission! Your reference number is 20368/2025/01/09"

---

## Key Differences Between Flows

| Feature | Complaint (Image) | Text Incident | Image Incident |
|---------|-------------------|---------------|----------------|
| **Trigger** | Image upload | "report incident" TEXT | Image upload |
| **User Choice** | "Not an incident" | N/A | "Yes, report incident" |
| **Image** | Yes (required) | Yes (required) | Yes (required) |
| **Steps** | 6 steps | 6 steps | 6 steps |
| **AI Usage** | None | Extraction + Hazard question + Classification | Extraction + Hazard question + Classification |
| **Category** | Service/System Error | Bencana Alam, etc. | Bencana Alam, etc. |
| **Image Storage** | Always (S3) | Always (S3) | Always (S3) |

---

## AI Analysis Points

### 1. **Description Extraction (Image Incident Only)**
- **Input:** User's combined message with description and location
- **AI Task:** Extract description and location separately
- **Example:**
  - Input: "fallen tree blocking road at Jalan Penang"
  - Output: `{"description": "fallen tree blocking road", "location": "Jalan Penang"}`

### 2. **Hazard Question Generation (Both Incident Flows)**
- **Input:** Description text only (NOT the image)
- **AI Task:** Generate contextual yes/no question about hazard
- **Example:**
  - Input: "fallen tree that is blocking the main road"
  - Output: "Is it blocking the main road?"
  - Input: "pothole on the street"
  - Output: "Is it causing immediate danger?"

### 3. **Incident Classification (Both Incident Flows)**
- **Input:** Description text
- **AI Task:** Classify into Category and Sub-category
- **Example:**
  - Input: "fallen tree"
  - Output: `{"category": "Bencana Alam", "sub_category": "Pokok Tumbang"}`
  - Input: "pothole"
  - Output: `{"category": "Infrastruktur", "sub_category": "Jalan Rosak"}`

---

## Important Notes

1. **Flow 1 & 3 both start with image upload** - The difference is the user's choice after upload
2. **Flow 2 & 3 are identical** - Except Flow 2 starts with text "I want to report an incident" then asks for image
3. **Image is NEVER analyzed by AI** - Only used for storage
4. **Description text is analyzed** - For hazard questions and classification
5. **Location is extracted** - In both incident flows (Flow 2 & 3) from combined message
6. **All workflows can restart** - User can select "No, start over" at preview
7. **User choice determines flow** - "Yes, report incident" → Flow 3, "Not an incident" → Flow 1
