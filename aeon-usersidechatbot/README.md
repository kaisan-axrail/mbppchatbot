# AEON User-Side Chatbot

A modern, real-time chat application built with React, TypeScript, and WebSocket technology for seamless AI-powered conversations.

## 🚀 Features

- **Real-time messaging** via WebSocket connections
- **AI-powered responses** with streaming support
- **Session management** with automatic cleanup
- **Responsive design** with Tailwind CSS
- **Markdown support** for rich text formatting
- **Inactivity timeout** handling
- **Modern UI components** with Radix UI

## 🛠️ Tech Stack

- **Frontend**: React 18, TypeScript, Vite
- **Styling**: Tailwind CSS, SCSS
- **State Management**: React Query, React Hook Form
- **WebSocket**: react-use-websocket
- **UI Components**: Radix UI, Lucide React
- **Markdown**: react-markdown with remark-gfm
- **Animations**: Framer Motion
- **Form Validation**: Zod

## 📁 Project Structure

```
aeon.web.chat/
├── public/                 # Static assets
├── src/
│   ├── assets/            # Images and static files
│   ├── components/        # Reusable UI components
│   │   ├── generic/       # Layout components
│   │   └── ui/           # Base UI components
│   ├── constants/         # API endpoints and constants
│   ├── fonts/            # Custom font files
│   ├── hooks/            # Custom React hooks
│   ├── lib/              # Utility libraries
│   ├── utils/            # Helper functions
│   └── views/            # Page components
│       └── chat/         # Chat-specific components
├── package.json
├── vite.config.ts
├── tailwind.config.js
└── tsconfig.json
```

## 🚦 Getting Started

### Prerequisites

- Node.js (v18 or higher)
- npm or yarn

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd aeon-usersidechatbot/aeon.web.chat
```

2. Install dependencies:
```bash
npm install
```

3. Start the development server:
```bash
npm run dev
```

4. Open your browser and navigate to `http://localhost:5173`

## 📜 Available Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run preview` - Preview production build
- `npm run lint` - Run ESLint
- `npm run codegen` - Generate GraphQL code (AWS AppSync)

## 🔧 Configuration

### Environment Variables

The application uses hardcoded endpoints in `src/constants/apiEndpoints.tsx`:
- WebSocket endpoint for real-time messaging
- Session close endpoint for cleanup

### WebSocket Connection

The chat functionality connects to AWS API Gateway WebSocket endpoint:
```typescript
const WEBSOCKET_ENDPOINT = "wss://k1wj10zxv9.execute-api.us-east-1.amazonaws.com/dev";
```

## 🏗️ Architecture

### Core Components

#### ChatPage
Main chat interface component that renders the conversation UI and message input form.

#### useChat Hook
Custom hook managing:
- WebSocket connection state
- Message state management
- Form handling
- Session lifecycle
- Inactivity timeout (3 minutes)

#### Message Flow
1. User types message and submits
2. Message sent via WebSocket to backend
3. AI response streamed back in real-time
4. Messages rendered with markdown support

### Session Management

- **Unique User ID**: Generated using UUID for each session
- **Inactivity Timeout**: 3-minute timeout with automatic session cleanup
- **Page Visibility**: Handles tab switching and window focus
- **Graceful Cleanup**: Sends session close events on page unload

### Message Types

```typescript
type Message = {
  messageId: string;
  contents: string;
  sender: "user" | "assistant";
  messageStop?: boolean;
  reasoningContents?: string;
};
```

## 🎨 UI/UX Features

- **Smooth Animations**: Framer Motion for message transitions
- **Auto-scroll**: Automatic scrolling to latest messages
- **Loading States**: Visual feedback during message processing
- **Responsive Design**: Mobile-first approach
- **Markdown Rendering**: Support for rich text formatting
- **Link Handling**: External links open in new tabs

## 🔒 Security Features

- **Session Isolation**: Each user gets unique session ID
- **Automatic Cleanup**: Sessions closed on inactivity/page leave
- **Input Validation**: Zod schema validation for forms
- **XSS Protection**: Markdown sanitization

## 🚀 Deployment

### Build for Production

```bash
npm run build
```

The build artifacts will be stored in the `dist/` directory.

### Deployment Options

- **Static Hosting**: Deploy to Vercel, Netlify, or AWS S3
- **CDN**: Use CloudFront for global distribution
- **Container**: Docker deployment with nginx

## 🧪 Development

### Code Style

- **ESLint**: Configured with TypeScript rules
- **Prettier**: Code formatting (if configured)
- **TypeScript**: Strict type checking enabled

### Custom Hooks

- `useChat`: Main chat functionality
- `useClientPagination`: Client-side pagination
- `useDebounce`: Input debouncing

### Utility Functions

- `jsonHelpers.ts`: JSON manipulation utilities
- `utilityFunctions.ts`: General helper functions
- `utils.ts`: Class name utilities (clsx)

## 🔍 API Integration

### WebSocket Events

**Outgoing Messages:**
```json
{
  "message": "User message text",
  "message_id": "unique-message-id",
  "user_id": "unique-user-id"
}
```

**Incoming Messages:**
```json
{
  "status_code": 200,
  "answer": "AI response text",
  "message_id": "message-id",
  "message_stop": true,
  "replace": false,
  "reasoning_contents": "optional reasoning"
}
```

### Session Management API

**Session Close:**
```json
POST /conversation-update
{
  "sessionId": "user-session-id",
  "agent": "ai"
}
```

## 🐛 Troubleshooting

### Common Issues

1. **WebSocket Connection Failed**
   - Check network connectivity
   - Verify endpoint URLs
   - Check browser console for errors

2. **Messages Not Displaying**
   - Verify WebSocket connection status
   - Check message format in network tab
   - Ensure proper state updates

3. **Session Timeout Issues**
   - Check inactivity timer configuration
   - Verify session close endpoint
   - Monitor browser console logs

## 📈 Performance Optimization

- **Code Splitting**: Vite handles automatic code splitting
- **Lazy Loading**: Components loaded on demand
- **Memoization**: React.memo for expensive components
- **Debounced Input**: Prevents excessive API calls

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is proprietary software. All rights reserved.

## 🆘 Support

For technical support or questions:
- Check the troubleshooting section
- Review browser console logs
- Contact the development team

---

**Built with ❤️ by the AEON Development Team**