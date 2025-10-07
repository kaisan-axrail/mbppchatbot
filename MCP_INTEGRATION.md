# MCP Server Integration Guide

Simple guide for connecting any LLM or chatbot to the MCP server.

## Quick Start

**MCP Server Endpoint:** `https://4fsaarjly6.execute-api.ap-southeast-1.amazonaws.com/prod/mcp`

**Method:** POST

**Content-Type:** application/json

## Available Tools

### 1. List Events
```json
{
  "tool_name": "list_events",
  "parameters": {}
}
```

### 2. Create Event
```json
{
  "tool_name": "create_event",
  "parameters": {
    "data": {
      "name": "Tech Conference",
      "location": "KLCC",
      "date": "2025-02-15",
      "category": "Conference",
      "description": "Annual tech event"
    }
  }
}
```

### 3. Read Event
```json
{
  "tool_name": "read_event",
  "parameters": {
    "record_id": "event-id-here"
  }
}
```

### 4. Update Event
```json
{
  "tool_name": "update_event",
  "parameters": {
    "record_id": "event-id-here",
    "data": {
      "name": "Updated Event Name",
      "location": "New Location"
    }
  }
}
```

### 5. Delete Event
```json
{
  "tool_name": "delete_event",
  "parameters": {
    "record_id": "event-id-here"
  }
}
```

### 6. Search Documents
```json
{
  "tool_name": "search_documents",
  "parameters": {
    "query": "What is AWS Lambda?",
    "limit": 5,
    "threshold": 0.7
  }
}
```

## Example: Python

```python
import requests

url = "https://4fsaarjly6.execute-api.ap-southeast-1.amazonaws.com/prod/mcp"

# List all events
response = requests.post(url, json={
    "tool_name": "list_events",
    "parameters": {}
})

print(response.json())
```

## Example: cURL

```bash
curl -X POST https://4fsaarjly6.execute-api.ap-southeast-1.amazonaws.com/prod/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "list_events",
    "parameters": {}
  }'
```

## Example: JavaScript/Node.js

```javascript
const response = await fetch('https://4fsaarjly6.execute-api.ap-southeast-1.amazonaws.com/prod/mcp', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    tool_name: 'list_events',
    parameters: {}
  })
});

const data = await response.json();
console.log(data);
```

## OpenAPI Schema

Full tool definitions available at:
`lambda/mcp_server/mcp_tools_schema.yaml`

## Response Format

All tools return JSON:

```json
{
  "statusCode": 200,
  "success": true,
  "result": {
    // Tool-specific response data
  }
}
```

## Error Handling

Errors return:

```json
{
  "statusCode": 500,
  "error": "ERROR_CODE",
  "message": "Error description"
}
```

## Integration Tips

1. **For LangChain:** Create a custom tool that calls the MCP endpoint
2. **For OpenAI Function Calling:** Use the OpenAPI schema to define functions
3. **For Claude:** Define tools using the schema and call the endpoint
4. **For Custom Chatbots:** Make HTTP POST requests to the endpoint

## Need Help?

- Check `lambda/mcp_server/mcp_tools_schema.yaml` for complete tool definitions
- Test with cURL or Postman first
- All tools use POST method with JSON body
