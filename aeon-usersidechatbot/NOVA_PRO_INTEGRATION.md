# Nova Pro Integration Guide

Your Aeon chatbot has been successfully updated to connect to the Nova Pro WebSocket API!

## 🚀 What's Changed

### WebSocket Endpoint
- **Old:** `wss://k1wj10zxv9.execute-api.us-east-1.amazonaws.com/dev`
- **New:** `wss://ynw017q5lc.execute-api.ap-southeast-1.amazonaws.com/prod` (Nova Pro)

### Message Format
The chatbot now uses Nova Pro's message format:

**Sending:**
```json
{
  "message": "User message text",
  "sessionId": "unique-session-id",
  "timestamp": "2025-01-03T10:30:00.000Z"
}
```

**Receiving:**
```json
{
  "type": "assistant_message",
  "content": "Nova Pro response",
  "sessionId": "session-id",
  "provider": "nova-pro"
}
```

## 🤖 Nova Pro Features

Your chatbot now supports:

- **🧠 AI Responses** - Powered by Amazon Nova Pro via Bedrock
- **📚 RAG Search** - Document search and retrieval
- **🔧 MCP Tools** - Database operations (create, read, update, delete)
- **🌍 Multilingual** - Supports multiple languages including Bahasa Malaysia
- **💾 Session Management** - Automatic conversation memory

## 🛠️ How to Run

1. **Install dependencies:**
   ```bash
   cd aeon-usersidechatbot/aeon.web.chat
   npm install
   ```

2. **Start the development server:**
   ```bash
   npm run dev
   ```

3. **Open your browser:**
   Navigate to `http://localhost:5173` (or the URL shown in terminal)

## 💬 Testing the Integration

### Test Messages to Try:

1. **General Chat:**
   - "Hello Nova!"
   - "What can you do?"
   - "How are you?"

2. **RAG (Document Search):**
   - "Search for documents about AWS Bedrock"
   - "Find information about machine learning"

3. **MCP Tools (Database Operations):**
   - "Create a new record with name 'test' and value 'nova'"
   - "Update user data"
   - "Delete record ID 123"

## 🔧 Configuration

### Environment Variables
The WebSocket endpoint is configured in:
`src/constants/apiEndpoints.tsx`

### Message Types
The chatbot handles these Nova Pro response types:
- `connection_established` - Connection confirmation
- `assistant_message` - AI responses
- `error` - Error messages

### Session Management
- Sessions are automatically created with UUID
- Session cleanup is handled on page unload
- Inactivity timeout: 3 minutes

## 🐛 Troubleshooting

### Connection Issues
1. **Check WebSocket URL:** Ensure Nova Pro API is deployed
2. **Network:** Verify internet connection
3. **CORS:** WebSocket connections should work cross-origin
4. **AWS Status:** Check if AWS services are operational

### Common Errors
- **Connection refused:** Nova Pro WebSocket API might be down
- **Invalid response:** Check message format compatibility
- **Timeout:** Network or server issues

### Debug Mode
Open browser developer tools (F12) and check the Console tab for:
- Connection status logs
- Message sending/receiving logs
- Error messages

## 📊 Response Types

### Successful Response
```json
{
  "type": "assistant_message",
  "content": "Hello! I'm Nova Pro, powered by Amazon Bedrock...",
  "sessionId": "session-123",
  "provider": "nova-pro"
}
```

### RAG Response (with sources)
```json
{
  "type": "assistant_message", 
  "content": "Based on the documents, AWS Bedrock is...",
  "sources": ["document1.pdf", "document2.pdf"],
  "provider": "nova-pro"
}
```

### MCP Tool Response
```json
{
  "type": "assistant_message",
  "content": "Successfully created record: test = nova",
  "toolsUsed": ["create_record"],
  "provider": "nova-pro"
}
```

### Error Response
```json
{
  "type": "error",
  "content": "I apologize, but I encountered an error...",
  "timestamp": "2025-01-03T10:30:01.000Z"
}
```

## 🎯 Next Steps

1. **Test the connection** by running the chatbot
2. **Try different message types** to test RAG and MCP tools
3. **Monitor the browser console** for any connection issues
4. **Customize the UI** if needed for Nova Pro branding

## 📞 Support

If you encounter issues:
1. Check the browser console for error messages
2. Verify the Nova Pro WebSocket API is deployed and accessible
3. Test with simple messages first before complex queries
4. Check AWS CloudWatch logs for server-side issues

---

**Your Aeon chatbot is now powered by Nova Pro! 🚀**