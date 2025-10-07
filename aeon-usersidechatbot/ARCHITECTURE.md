# Architecture Documentation

## System Overview

The AEON User-Side Chatbot is a client-side React application that provides real-time chat functionality through WebSocket connections to an AI backend service.

## High-Level Architecture

```
┌─────────────────┐    WebSocket    ┌─────────────────┐
│   React Client  │ ←──────────────→ │  AWS API Gateway│
│                 │                 │   WebSocket     │
└─────────────────┘                 └─────────────────┘
         │                                   │
         │ HTTP                              │
         ▼                                   ▼
┌─────────────────┐                 ┌─────────────────┐
│ Session Close   │                 │   AI Backend    │
│   Endpoint      │                 │    Service      │
└─────────────────┘                 └─────────────────┘
```

## Component Architecture

### Core Components Hierarchy

```
App
├── QueryClientProvider
├── SiteContainer
│   └── ChatPage
│       └── ChatProvider
│           └── Screen
│               ├── Message List
│               └── Input Form
└── Toaster
```

### Data Flow

1. **User Input** → Form submission via React Hook Form
2. **Message Processing** → useChat hook handles state updates
3. **WebSocket Send** → Message sent to backend via WebSocket
4. **Response Streaming** → AI responses received in chunks
5. **UI Updates** → Messages rendered with animations

## State Management

### Chat State (useChat Hook)

```typescript
interface ChatState {
  messages: Message[];
  userId: string;
  connectionStatus: ConnectionStatus;
  form: UseFormReturn;
}
```

### Message State Flow

```
User Input → Form Validation → State Update → WebSocket Send
     ↑                                              ↓
UI Update ← Message Rendering ← State Update ← WebSocket Response
```

## WebSocket Communication

### Connection Lifecycle

1. **Initialization**: Generate unique userId
2. **Connection**: Establish WebSocket connection
3. **Authentication**: Include userId in connection URL
4. **Message Exchange**: Bidirectional communication
5. **Cleanup**: Close connection on page unload/inactivity

### Message Protocol

**Client → Server:**
```json
{
  "message": "string",
  "message_id": "uuid",
  "user_id": "uuid"
}
```

**Server → Client:**
```json
{
  "status_code": "number",
  "answer": "string",
  "message_id": "uuid",
  "message_stop": "boolean",
  "replace": "boolean",
  "reasoning_contents": "string?"
}
```

## Session Management

### Session Lifecycle

```
Page Load → Generate UUID → Connect WebSocket → Active Session
    ↓
Inactivity Timer (3min) → Session Close Event → Cleanup
    ↓
Page Unload → Beacon API → Final Cleanup
```

### Cleanup Triggers

- **Inactivity**: 3-minute timeout
- **Page Visibility**: Tab hidden/minimized
- **Page Unload**: Browser close/navigation
- **WebSocket Close**: Connection lost

## Security Architecture

### Client-Side Security

- **Input Validation**: Zod schema validation
- **XSS Prevention**: Markdown sanitization
- **Session Isolation**: Unique UUIDs per session
- **Automatic Cleanup**: Prevent session leaks

### Communication Security

- **WSS Protocol**: Encrypted WebSocket connections
- **HTTPS Endpoints**: Secure HTTP for session management
- **No Credentials**: Stateless authentication via session IDs

## Performance Considerations

### Optimization Strategies

- **Code Splitting**: Vite automatic chunking
- **Lazy Loading**: Dynamic imports for components
- **Memoization**: React.memo for expensive renders
- **Debouncing**: Input debouncing for API calls
- **Virtual Scrolling**: For large message lists (future)

### Memory Management

- **Message Cleanup**: Automatic cleanup on session end
- **Event Listeners**: Proper cleanup in useEffect
- **Timer Management**: Clear timeouts on unmount
- **WebSocket Cleanup**: Close connections properly

## Error Handling

### Error Boundaries

```
App Level → Global error handling
Component Level → Local error recovery
Hook Level → State error management
```

### Error Types

- **Network Errors**: WebSocket connection failures
- **Validation Errors**: Form input validation
- **Session Errors**: Timeout/cleanup failures
- **Rendering Errors**: Component render failures

## Scalability Considerations

### Current Limitations

- **Single Session**: One conversation per browser tab
- **Memory Growth**: Messages accumulate in memory
- **No Persistence**: Messages lost on page refresh

### Future Enhancements

- **Message Persistence**: Local storage/IndexedDB
- **Multiple Sessions**: Tab-based session management
- **Message Pagination**: Virtual scrolling for performance
- **Offline Support**: Service worker integration

## Development Architecture

### Build System

- **Vite**: Fast development and building
- **TypeScript**: Type safety and developer experience
- **ESLint**: Code quality and consistency
- **Tailwind**: Utility-first CSS framework

### Component Structure

```
components/
├── generic/          # Layout components
│   └── layouts/      # Page layouts
├── ui/              # Base UI components
└── LoadingDots.tsx  # Specific components
```

### Hook Architecture

```
hooks/
├── useChat.tsx      # Main chat functionality
├── useDebounce.tsx  # Input debouncing
└── useClientPagination.tsx  # Pagination logic
```

## Deployment Architecture

### Static Hosting

- **Build Output**: Static files in `dist/`
- **CDN Distribution**: CloudFront/similar
- **Environment Config**: Build-time configuration

### Infrastructure Requirements

- **WebSocket Endpoint**: AWS API Gateway WebSocket
- **Session API**: REST endpoint for cleanup
- **Static Hosting**: S3/Vercel/Netlify
- **CDN**: Global content distribution

## Monitoring and Observability

### Client-Side Logging

- **Console Logs**: Development debugging
- **Error Tracking**: Global error handlers
- **Performance Metrics**: Core Web Vitals
- **User Analytics**: Session tracking

### Health Checks

- **WebSocket Status**: Connection state monitoring
- **API Availability**: Endpoint health checks
- **Performance Monitoring**: Load time tracking
- **Error Rate Tracking**: Client-side error rates