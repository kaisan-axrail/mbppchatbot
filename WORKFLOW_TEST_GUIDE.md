# MBPP Chatbot Workflow Testing Guide

## Quick Start

```bash
# Install dependency
pip install websockets

# Run all 3 workflow tests
python test_all_workflows.py
```

## The 3 Workflows

### 1️⃣ Service/System Complaint Workflow

**Trigger**: Keywords like "complaint", "website down", "service error"

**Flow**:
```
User: "MBPP website is down"
Bot:  "Would you like to report an incident?"
User: "Not an incident (Service Complaint)"
Bot:  "Please describe the issue"
User: "Website shows error 500"
Bot:  "Can you confirm internet is working?"
User: "Yes, internet is fine"
Bot:  "Logging ticket... Ticket: 20123/2025/01/03"
```

**Expected Output**:
- ✅ Complaint ticket created
- ✅ Saved to DynamoDB (mbpp-reports)
- ✅ Category: "Service/ System Error"

### 2️⃣ Text-Driven Incident Report Workflow

**Trigger**: Keywords like "incident", "report", "fallen tree", "pothole" (NO image)

**Flow**:
```
User: "Report fallen tree blocking road"
Bot:  "Please share image, location and describe what happened"
User: "Yes, report an incident"
Bot:  "Where is this? Share location"
User: "Jalan Tun Razak, near traffic light"
Bot:  "Is it blocking the road and causing hazard?"
User: "Yes, blocking the road"
Bot:  "Logging ticket... Ticket: 20124/2025/01/03"
```

**Expected Output**:
- ✅ Incident ticket created
- ✅ Saved to DynamoDB (mbpp-reports)
- ✅ Category: "Bencana Alam"
- ✅ Location recorded

### 3️⃣ Image-Driven Incident Report Workflow

**Trigger**: Image uploaded + incident keywords

**Flow**:
```
User: [Uploads image] "Report incident - fallen tree"
Bot:  "Image detected. Confirm you want to report incident?"
User: "Yes, report an incident"
Bot:  "Please describe what happened and location"
User: "Large tree fell across Jalan Sultan"
Bot:  "Is it blocking the road and causing hazard?"
User: "Yes, blocking completely"
Bot:  "Logging ticket... Ticket: 20125/2025/01/03"
```

**Expected Output**:
- ✅ Incident ticket created
- ✅ Image uploaded to S3
- ✅ Saved to DynamoDB with image_url
- ✅ Category: "Bencana Alam"

## Manual Testing

### Test 1: Complaint Workflow

```bash
# Start web app
cd aeon-usersidechatbot/aeon.web.chat
npm run dev

# In browser (http://localhost:5173):
1. Type: "MBPP website is down"
2. Select: "Not an incident (Service Complaint)"
3. Type: "Website shows error 500 when logging in"
4. Type: "Yes, my internet is working"
5. ✅ Should get ticket number
```

### Test 2: Text Incident Workflow

```bash
# In browser:
1. Type: "I want to report a fallen tree"
2. Type: "Yes, report an incident"
3. Type: "Jalan Tun Razak, near the traffic light"
4. Type: "Yes, it's blocking the road"
5. ✅ Should get ticket number
```

### Test 3: Image Incident Workflow

```bash
# In browser:
1. Click 📷 icon
2. Select any image
3. Type: "Report fallen tree blocking road"
4. Type: "Yes, report an incident"
5. Type: "Jalan Sultan, blocking both lanes"
6. Type: "Yes, blocking completely"
7. ✅ Should get ticket number
```

## Automated Testing

### Run All Tests
```bash
python test_all_workflows.py
```

### Expected Output
```
🧪 TEST 1: SERVICE/SYSTEM COMPLAINT WORKFLOW
✅ Connected
📍 Step 1: Report service error
📍 Step 2: Describe the issue
📍 Step 3: Confirm internet connection
✅ WORKFLOW 1 PASSED - Ticket: 20123/2025/01/03

🧪 TEST 2: TEXT-DRIVEN INCIDENT REPORT WORKFLOW
✅ Connected
📍 Step 1: Report incident
📍 Step 2: Confirm it's an incident
📍 Step 3: Provide location
📍 Step 4: Confirm road blockage
✅ WORKFLOW 2 PASSED - Ticket: 20124/2025/01/03

🧪 TEST 3: IMAGE-DRIVEN INCIDENT REPORT WORKFLOW
✅ Connected
📍 Step 1: Send image with incident report
📍 Step 2: Confirm it's an incident
📍 Step 3: Provide description and location
📍 Step 4: Confirm road blockage
✅ WORKFLOW 3 PASSED - Ticket: 20125/2025/01/03

📊 TEST SUMMARY
Workflow                       Status              
--------------------------------------------------
1. Service/System Complaint    ✅ PASSED           
2. Text-Driven Incident        ✅ PASSED           
3. Image-Driven Incident       ✅ PASSED           
--------------------------------------------------
TOTAL                          3/3 PASSED

🎉 ALL TESTS PASSED!
```

## Verification

### Check DynamoDB Reports
```bash
aws dynamodb scan \
  --table-name mbpp-reports \
  --profile test \
  --region ap-southeast-1 \
  --output json | jq '.Items[] | {ticket: .ticket_number.S, category: .category.S, image: .image_url.S}'
```

### Check S3 Images
```bash
aws s3 ls s3://mbpp-incident-images-{ACCOUNT}/incidents/ \
  --recursive \
  --profile test
```

### Check Events
```bash
aws dynamodb scan \
  --table-name mbpp-events \
  --profile test \
  --region ap-southeast-1 \
  --output json | jq '.Items[] | {event: .event_type.S, ticket: .ticket_number.S}'
```

### Check CloudWatch Logs
```bash
aws logs tail /aws/lambda/ChatbotMainStack-WebSocketHandler \
  --follow \
  --profile test \
  --region ap-southeast-1
```

## Troubleshooting

### Workflow not triggering
- Check keywords in message
- Verify MBPPAgent is loaded
- Check CloudWatch logs for errors

### No ticket generated
- Check DynamoDB tables exist
- Verify Lambda has DynamoDB permissions
- Check workflow completion in logs

### Image not uploading
- Check S3 bucket exists
- Verify Lambda has S3 permissions
- Check image size (<128KB for WebSocket)

### WebSocket connection fails
- Verify endpoint URL is correct
- Check API Gateway is deployed
- Test with simple message first

## Success Criteria

✅ All 3 workflows complete successfully
✅ Ticket numbers generated for each
✅ Reports saved to DynamoDB
✅ Images uploaded to S3 (workflow 3)
✅ Events logged in events table
✅ No errors in CloudWatch logs

## Test Data

### Complaint Keywords
- "complaint", "feedback", "service error"
- "system down", "website", "not working"

### Incident Keywords
- "incident", "report", "emergency"
- "fallen tree", "pothole", "flood"
- "hazard", "blocking", "accident"

### Test Locations
- "Jalan Tun Razak"
- "Jalan Sultan"
- "Near traffic light"
- "GPS: 3.1390, 101.6869"

## Next Steps

After successful testing:
1. ✅ Deploy to production
2. ✅ Monitor CloudWatch metrics
3. ✅ Set up alerts for failures
4. ✅ Train users on workflows
5. ✅ Document ticket resolution process
