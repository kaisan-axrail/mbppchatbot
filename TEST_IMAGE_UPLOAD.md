# Testing Image Upload Feature

## Quick Test Guide

### Option 1: Using the Web Interface (Easiest)

1. **Start the web app**:
   ```bash
   cd aeon-usersidechatbot/aeon.web.chat
   npm install  # if not already done
   npm run dev
   ```

2. **Open browser**: http://localhost:5173

3. **Test image upload**:
   - Click the 📷 (image) icon next to the message input
   - Select an image (any photo of an incident, pothole, fallen tree, etc.)
   - See the preview appear
   - Type: "Report fallen tree blocking road"
   - Click Send
   - Watch the workflow responses

4. **Verify in AWS**:
   ```bash
   # Check S3 bucket for uploaded image
   aws s3 ls s3://mbpp-incident-images-{YOUR_ACCOUNT_ID}/incidents/ --recursive --profile test
   
   # Check DynamoDB for report
   aws dynamodb scan --table-name mbpp-reports --profile test --region ap-southeast-1
   ```

### Option 2: Using Python Test Script

1. **Install dependencies**:
   ```bash
   pip install websockets
   ```

2. **Prepare a test image**:
   - Save any image as `test_image.jpg` in the project root
   - Or use any image path

3. **Run the test**:
   ```bash
   python test_image_upload.py
   ```

4. **Follow prompts**:
   - Choose option 1 (Test with image)
   - Enter image path: `test_image.jpg`
   - Enter message: `Report fallen tree blocking road`
   - Watch the responses

### Option 3: Manual WebSocket Test (Advanced)

Using `wscat`:

```bash
# Install wscat
npm install -g wscat

# Connect
wscat -c wss://ynw017q5lc.execute-api.ap-southeast-1.amazonaws.com/prod

# Send message with base64 image (replace IMAGE_BASE64 with actual base64)
{"message":"Report incident","sessionId":"test-123","timestamp":"2025-01-03T10:00:00Z","hasImage":true,"imageData":"IMAGE_BASE64"}
```

## What to Expect

### 1. Image-Driven Incident Workflow

**User sends**: Image + "Report fallen tree"

**Bot responses**:
1. "Image detected. Can you confirm you would like to report an incident?"
2. "Please describe what happened and tell us the location..."
3. "Could you confirm if its blocking the road and causing hazard?"
4. "Logging the ticket..."
5. "Thank you for your submission, ticket number: 20123/2025/01/03"

### 2. Image Storage

**S3 Location**:
```
s3://mbpp-incident-images-{account}/incidents/{ticket_number}/{uuid}.jpg
```

**DynamoDB Record** (mbpp-reports table):
```json
{
  "ticket_number": "20123/2025/01/03",
  "subject": "Incident Report",
  "details": "Fallen tree blocking road",
  "location": "Jalan XYZ",
  "image_url": "s3://mbpp-incident-images-123/incidents/20123/2025/01/03/abc.jpg",
  "blocked_road": "true",
  "category": "Bencana Alam",
  "status": "open"
}
```

## Verification Steps

### 1. Check CloudWatch Logs
```bash
# WebSocket handler logs
aws logs tail /aws/lambda/ChatbotMainStack-WebSocketHandler --follow --profile test --region ap-southeast-1

# Look for:
# - "Processing message with Nova Pro: ..., has_image: True"
# - "Detected workflow type: image_incident"
```

### 2. Check S3 Bucket
```bash
# List uploaded images
aws s3 ls s3://mbpp-incident-images-{ACCOUNT}/incidents/ --recursive --profile test

# Download an image to verify
aws s3 cp s3://mbpp-incident-images-{ACCOUNT}/incidents/{ticket}/{uuid}.jpg ./downloaded.jpg --profile test
```

### 3. Check DynamoDB Reports
```bash
# Scan reports table
aws dynamodb scan \
  --table-name mbpp-reports \
  --profile test \
  --region ap-southeast-1 \
  --output json

# Query specific ticket
aws dynamodb get-item \
  --table-name mbpp-reports \
  --key '{"ticket_number":{"S":"20123/2025/01/03"}}' \
  --profile test \
  --region ap-southeast-1
```

### 4. Check Events Table
```bash
# Check incident events
aws dynamodb scan \
  --table-name mbpp-events \
  --filter-expression "event_type = :type" \
  --expression-attribute-values '{":type":{"S":"incident_created"}}' \
  --profile test \
  --region ap-southeast-1
```

## Troubleshooting

### Image not uploading to S3
- Check Lambda has S3 permissions
- Check bucket name matches: `mbpp-incident-images-{account}`
- Check CloudWatch logs for S3 errors

### Workflow not triggering
- Verify message contains incident keywords: "incident", "report", "fallen tree", etc.
- Check `has_image: true` in logs
- Verify MBPPAgent is detecting workflow type

### WebSocket connection fails
- Verify endpoint URL is correct
- Check API Gateway WebSocket API is deployed
- Test with simple text message first

### Image too large
- WebSocket has ~128KB message limit
- Compress images before sending
- Or implement direct S3 upload with presigned URLs

## Test Scenarios

### Scenario 1: Fallen Tree
- **Image**: Photo of fallen tree
- **Message**: "Report fallen tree blocking Jalan ABC"
- **Expected**: Image-driven incident workflow → S3 upload → Ticket created

### Scenario 2: Pothole
- **Image**: Photo of pothole
- **Message**: "Pothole on main road causing hazard"
- **Expected**: Image-driven incident workflow → S3 upload → Ticket created

### Scenario 3: Text Only
- **Image**: None
- **Message**: "What is MBPP?"
- **Expected**: RAG query → No S3 upload → General response

### Scenario 4: Service Complaint
- **Image**: Screenshot of error
- **Message**: "MBPP website is down"
- **Expected**: Complaint workflow → S3 upload → Complaint ticket

## Success Criteria

✅ Image preview shows in chat UI
✅ Image sent via WebSocket (check network tab)
✅ Backend receives `hasImage: true` (check logs)
✅ Workflow detects image incident type
✅ Image uploaded to S3 bucket
✅ DynamoDB report contains `image_url`
✅ Ticket number returned to user
✅ Event logged in events table

## Next Steps After Testing

1. **Add image compression** (reduce payload size)
2. **Add file size validation** (prevent large uploads)
3. **Add image format validation** (only allow jpg, png)
4. **Add loading indicator** (while uploading)
5. **Add error handling** (upload failures)
6. **Add multiple images** (array of images)
7. **Add camera capture** (mobile devices)

---

**Need Help?**
- Check CloudWatch logs first
- Verify S3 bucket exists
- Test with small images (<100KB)
- Try text-only message first to verify WebSocket works
