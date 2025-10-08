# 🚀 Run Tests Now - Simple Guide

## Option 1: Automated (Recommended - 2 minutes)

```bash
# Install dependency
pip install websockets

# Run all tests
python test_all_workflows.py
```

**Done!** You'll see:
```
✅ WORKFLOW 1 PASSED - Ticket: 20123/2025/01/03
✅ WORKFLOW 2 PASSED - Ticket: 20124/2025/01/03
✅ WORKFLOW 3 PASSED - Ticket: 20125/2025/01/03
🎉 ALL TESTS PASSED!
```

---

## Option 2: Manual Web Interface (8 minutes)

### Step 1: Start Web App
```bash
cd aeon-usersidechatbot/aeon.web.chat
npm run dev
```

### Step 2: Open Browser
Go to: **http://localhost:5173**

### Step 3: Test Each Workflow

#### Test A: Complaint (2 min)
1. Type: `MBPP website is down`
2. Type: `Not an incident`
3. Type: `Error 500`
4. Type: `Yes, internet works`
5. ✅ Get ticket number

#### Test B: Text Incident (3 min)
1. Type: `Report fallen tree`
2. Type: `Yes, report incident`
3. Type: `Jalan Tun Razak`
4. Type: `Yes, blocking road`
5. ✅ Get ticket number

#### Test C: Image Incident (3 min)
1. Click 📷 icon
2. Select any image
3. Type: `Report fallen tree`
4. Type: `Yes, report incident`
5. Type: `Tree blocking Jalan Sultan`
6. Type: `Yes, blocking completely`
7. ✅ Get ticket number

---

## Verify (Optional)

```bash
# Check reports created
aws dynamodb scan --table-name mbpp-reports --select COUNT --profile test --region ap-southeast-1

# Check image uploaded
aws s3 ls s3://mbpp-incident-images-{ACCOUNT}/incidents/ --recursive --profile test
```

---

## That's It! 🎉

**All 3 workflows tested?** → **Deployment successful!**

---

## Need Help?

**Connection issues?**
```bash
./verify_deployment.sh test
```

**See errors?**
```bash
aws logs tail /aws/lambda/ChatbotMainStack-WebSocketHandler --follow --profile test --region ap-southeast-1
```

**Still stuck?**
- Check `WORKFLOW_TEST_GUIDE.md` for detailed steps
- Check `QUICK_TEST_CHECKLIST.md` for troubleshooting
