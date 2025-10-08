# ✅ Quick Test Checklist

## Before Testing

```bash
# 1. Verify deployment
./verify_deployment.sh test

# 2. Install test dependencies
pip install websockets
```

## Automated Test (Fastest)

```bash
# Run all 3 workflows automatically
python test_all_workflows.py
```

**Expected**: All 3 tests pass with ticket numbers

---

## Manual Test (Web Interface)

### Start Web App
```bash
cd aeon-usersidechatbot/aeon.web.chat
npm run dev
# Open: http://localhost:5173
```

### ✅ Test 1: Complaint Workflow (2 min)

| Step | Action | Expected Response |
|------|--------|-------------------|
| 1 | Type: `MBPP website is down` | "Would you like to report an incident?" |
| 2 | Type: `Not an incident` | "Please describe the issue" |
| 3 | Type: `Error 500 when logging in` | "Can you confirm internet is working?" |
| 4 | Type: `Yes, internet is fine` | "Ticket has been logged: 20XXX/2025/01/03" |

**✅ PASS**: Ticket number received

---

### ✅ Test 2: Text Incident Workflow (3 min)

| Step | Action | Expected Response |
|------|--------|-------------------|
| 1 | Type: `Report fallen tree` | "Please share image, location..." |
| 2 | Type: `Yes, report an incident` | "Where is this?" |
| 3 | Type: `Jalan Tun Razak` | "Is it blocking the road?" |
| 4 | Type: `Yes, blocking the road` | "Ticket has been logged: 20XXX/2025/01/03" |

**✅ PASS**: Ticket number received

---

### ✅ Test 3: Image Incident Workflow (3 min)

| Step | Action | Expected Response |
|------|--------|-------------------|
| 1 | Click 📷 icon, select image | Preview shows |
| 2 | Type: `Report fallen tree` | "Image detected. Confirm incident?" |
| 3 | Type: `Yes, report an incident` | "Please describe what happened..." |
| 4 | Type: `Tree blocking Jalan Sultan` | "Is it blocking the road?" |
| 5 | Type: `Yes, blocking completely` | "Ticket has been logged: 20XXX/2025/01/03" |

**✅ PASS**: Ticket number received + image uploaded

---

## Verify Results

### Check DynamoDB
```bash
# Count reports
aws dynamodb scan --table-name mbpp-reports --select COUNT --profile test --region ap-southeast-1

# View latest reports
aws dynamodb scan --table-name mbpp-reports --profile test --region ap-southeast-1 | jq '.Items[-3:]'
```

**✅ PASS**: 3 new reports created

### Check S3 (for Test 3)
```bash
# List images
aws s3 ls s3://mbpp-incident-images-{ACCOUNT}/incidents/ --recursive --profile test

# Count images
aws s3 ls s3://mbpp-incident-images-{ACCOUNT}/incidents/ --recursive --profile test | wc -l
```

**✅ PASS**: At least 1 image uploaded

### Check CloudWatch Logs
```bash
# View recent logs
aws logs tail /aws/lambda/ChatbotMainStack-WebSocketHandler --profile test --region ap-southeast-1 --since 5m
```

**✅ PASS**: No errors, workflow completions logged

---

## Quick Troubleshooting

| Issue | Solution |
|-------|----------|
| WebSocket won't connect | Check endpoint URL, verify deployment |
| No bot response | Check CloudWatch logs, verify Lambda is running |
| Workflow doesn't start | Use exact keywords: "complaint", "incident", "report" |
| No ticket generated | Check DynamoDB tables exist, verify permissions |
| Image not uploading | Check S3 bucket exists, verify image size <1MB |

---

## Success Criteria

- [ ] Automated test: 3/3 workflows pass
- [ ] Manual test: All 3 workflows complete
- [ ] DynamoDB: 3 new reports created
- [ ] S3: Image uploaded (Test 3)
- [ ] CloudWatch: No errors
- [ ] Ticket numbers: All received

**All checked?** 🎉 **DEPLOYMENT SUCCESSFUL!**

---

## Time Estimate

- Automated test: **2 minutes**
- Manual test (all 3): **8 minutes**
- Verification: **2 minutes**
- **Total: ~12 minutes**
