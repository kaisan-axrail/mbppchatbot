# API Documentation

## Overview

The AEON User-Side Chatbot communicates with backend services through two main channels:
1. **WebSocket API** - Real-time messaging
2. **REST API** - Session management

## WebSocket API

### Connection

**Endpoint:** `wss://k1wj10zxv9.execute-api.us-east-1.amazonaws.com/dev`

**Connection URL:**
```
wss://k1wj10zxv9.execute-api.us-east-1.amazonaws.com/dev/?userId={userId}
```

**Parameters:**
- `userId` (string, required): Unique identifier for the user session

### Message Format

#### Outgoing Messages (Client → Server)

```json
{
  "message": "Hello, how can you help me?",
  "message_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "550e8400-e29b-41d4-a716-446655440001"
}
```

**Fields:**
- `message` (string, required): The user's message content
- `message_id` (string, required): Unique UUID for the message
- `user_id` (string, required): User session identifier

#### Incoming Messages (Server → Client)

```json
{
  "status_code": 200,
  "answer": "I can help you with various questions and tasks.",
  "message_id": "550e8400-e29b-41d4-a716-446655440000",
  "message_stop": true,
  "replace": false,
  "reasoning_contents": "User is asking for general assistance."
}
```

**Fields:**
- `status_code` (number, required): HTTP-like status code
- `answer` (string, required): AI response content (may be partial)
- `message_id` (string, required): UUID matching the request message
- `message_stop` (boolean, optional): Indicates if message is complete
- `replace` (boolean, optional): Whether to replace existing content
- `reasoning_contents` (string, optional): AI reasoning information

### Connection States

The WebSocket connection can be in one of the following states:

- `CONNECTING` - Establishing connection
- `OPEN` - Connected and ready
- `CLOSING` - Connection closing
- `CLOSED` - Connection closed
- `UNINSTANTIATED` - Not initialized

### Error Handling

#### Connection Errors

When WebSocket connection fails, the client will:
1. Log the error to console
2. Trigger session cleanup
3. Display connection status to user
4. Not attempt automatic reconnection

#### Message Errors

Invalid message formats or server errors are handled gracefully:
- Display error toast to user
- Log error details to console
- Maintain UI responsiveness

## REST API

### Session Close Endpoint

**Endpoint:** `https://2mrh1juc0e.execute-api.us-east-1.amazonaws.com/prod/conversation-update`

**Method:** `POST`

**Headers:**
```
Content-Type: application/json
```

**Request Body:**
```json
{
  "sessionId": "550e8400-e29b-41d4-a716-446655440001",
  "agent": "ai"
}
```

**Fields:**
- `sessionId` (string, required): User session identifier
- `agent` (string, required): Always "ai" for this application

**Response:**
- Status: 200 OK (success)
- Body: Empty or confirmation message

**Usage:**
This endpoint is called to properly close user sessions in the following scenarios:
- User inactivity timeout (3 minutes)
- Page visibility change (tab hidden)
- Page unload (browser close/navigation)
- WebSocket connection loss

## Authentication

### Session-Based Authentication

The application uses session-based authentication with UUID identifiers:

1. **Session Creation**: Generate UUID on page load
2. **Session Identification**: Include userId in all requests
3. **Session Cleanup**: Explicit session termination

### Security Considerations

- **No Persistent Auth**: Sessions are temporary and browser-bound
- **UUID Generation**: Cryptographically secure random UUIDs
- **Session Isolation**: Each tab/window gets unique session
- **Automatic Cleanup**: Sessions cleaned up on inactivity/close

## Rate Limiting

### Client-Side Limits

- **Message Length**: Maximum 500 characters
- **Send Rate**: No explicit rate limiting (handled by UI state)
- **Connection Limit**: One WebSocket per session

### Server-Side Limits

Server-side rate limiting is handled by AWS API Gateway:
- Connection limits per IP
- Message rate limits per connection
- Payload size limits

## Error Codes

### WebSocket Status Codes

- `200` - Success
- `400` - Bad Request (invalid message format)
- `401` - Unauthorized (invalid session)
- `429` - Too Many Requests (rate limited)
- `500` - Internal Server Error

### Connection Close Codes

- `1000` - Normal closure
- `1001` - Going away (page unload)
- `1006` - Abnormal closure (network error)
- `1011` - Server error

## Message Flow Examples

### Successful Conversation

1. **User sends message:**
```json
{
  "message": "What is React?",
  "message_id": "msg-001",
  "user_id": "user-001"
}
```

2. **Server streams response:**
```json
{
  "status_code": 200,
  "answer": "React is a JavaScript library",
  "message_id": "msg-001",
  "message_stop": false,
  "replace": false
}
```

3. **Server continues streaming:**
```json
{
  "status_code": 200,
  "answer": " for building user interfaces.",
  "message_id": "msg-001",
  "message_stop": true,
  "replace": false
}
```

### Message Replacement

When `replace: true`, the client replaces the entire message content:

```json
{
  "status_code": 200,
  "answer": "Let me provide a better answer: React is...",
  "message_id": "msg-001",
  "message_stop": false,
  "replace": true
}
```

## Integration Examples

### JavaScript/TypeScript

```typescript
// WebSocket connection
const ws = new WebSocket(`${WEBSOCKET_ENDPOINT}/?userId=${userId}`);

// Send message
ws.send(JSON.stringify({
  message: "Hello",
  message_id: uuid(),
  user_id: userId
}));

// Handle response
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Received:', data);
};

// Session cleanup
fetch(SESSION_CLOSE_ENDPOINT, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ sessionId: userId, agent: 'ai' })
});
```

### React Hook Usage

```typescript
import { useChat } from './useChat';

function ChatComponent() {
  const { messages, handleSubmitForm, form, connectionStatus } = useChat();
  
  return (
    <div>
      <div>Status: {connectionStatus}</div>
      {messages.map(msg => (
        <div key={msg.messageId}>{msg.contents}</div>
      ))}
      <form onSubmit={form.handleSubmit(handleSubmitForm)}>
        <input {...form.register('message')} />
        <button type="submit">Send</button>
      </form>
    </div>
  );
}
```

## Testing

### WebSocket Testing

Use tools like:
- **wscat**: Command-line WebSocket client
- **Postman**: WebSocket testing interface
- **Browser DevTools**: Network tab WebSocket inspection

### REST API Testing

```bash
# Test session close endpoint
curl -X POST https://2mrh1juc0e.execute-api.us-east-1.amazonaws.com/prod/conversation-update \
  -H "Content-Type: application/json" \
  -d '{"sessionId": "test-session", "agent": "ai"}'
```

## Troubleshooting

### Common Issues

1. **WebSocket Connection Failed**
   - Check network connectivity
   - Verify endpoint URL
   - Check browser WebSocket support

2. **Messages Not Received**
   - Verify WebSocket is open
   - Check message format
   - Monitor network tab for errors

3. **Session Cleanup Failed**
   - Check REST endpoint availability
   - Verify request format
   - Monitor CORS issues

### Debug Tools

- **Browser DevTools**: Network tab for WebSocket inspection
- **Console Logs**: Client-side debugging information
- **Network Monitor**: Track API calls and responses