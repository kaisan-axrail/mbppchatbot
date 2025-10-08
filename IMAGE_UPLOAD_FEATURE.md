# Image Upload Feature - Implementation Summary

## Overview
Added image upload capability to the chatbot interface, allowing users to send images along with text messages for incident reporting workflows.

## Changes Made

### 1. Frontend - Type Definitions
**File**: `aeon-usersidechatbot/aeon.web.chat/src/views/chat/types.ts`
- Added `imageUrl?: string` field to Message type for displaying uploaded images

### 2. Frontend - Chat UI
**File**: `aeon-usersidechatbot/aeon.web.chat/src/views/chat/ChatPage.tsx`
- Added image upload button with `ImagePlus` icon
- Added image preview with remove button (`X` icon)
- Display images in message bubbles
- Hidden file input for image selection

### 3. Frontend - Chat Logic
**File**: `aeon-usersidechatbot/aeon.web.chat/src/views/chat/useChat.tsx`
- Added state management for selected image and image file
- `handleImageSelect()` - Converts selected file to base64 preview
- `clearImage()` - Removes selected image
- Updated `handleSubmitForm()` to include image data in WebSocket message
- Image data sent as base64 string with `hasImage` flag

### 4. Backend - WebSocket Handler
**File**: `lambda/websocket_handler/handler_working.py`
- Updated `handle_message()` to extract `hasImage` and `imageData` from message
- Updated `process_with_nova_pro()` to accept and pass image parameters to MBPPAgent

## How It Works

1. **User selects image**: Click image button → file picker opens → image selected
2. **Preview shown**: Image displayed above input field with remove button
3. **Send message**: Image converted to base64 and sent with message
4. **Backend processing**: MBPPAgent receives image data and triggers appropriate workflow
5. **Display**: User's message shows with image thumbnail

## Image Flow

```
User clicks ImagePlus button
    ↓
File picker opens (accept="image/*")
    ↓
Image selected → converted to base64
    ↓
Preview shown with X button to remove
    ↓
User types message and sends
    ↓
WebSocket message: { message, hasImage: true, imageData: "base64..." }
    ↓
Backend: handler_working.py receives image data
    ↓
MBPPAgent processes with image-driven workflow
    ↓
Response sent back to user
```

## Supported Workflows

The image upload integrates with existing MBPP workflows:
- **Image-Driven Incident Report**: User uploads image of incident (fallen tree, pothole, etc.)
- **Text-Driven Incident Report**: User describes incident (can optionally include image)
- **Complaint/Service Error**: General complaints (image optional)

## Technical Details

- **Image Format**: Base64 encoded string
- **Accepted Types**: All image formats (`image/*`)
- **Size Limit**: Handled by browser and WebSocket message size limits
- **Storage**: Images processed by MBPPAgent and stored in S3 bucket (mbpp-incident-images)

## UI Components Used

- `ImagePlus` icon from lucide-react (upload button)
- `X` icon from lucide-react (remove button)
- `Button` component with `ghost` variant (image upload button)
- Hidden file input for native file picker

## Testing

To test the feature:
1. Open the chat interface
2. Click the image icon (📷) next to the message input
3. Select an image file
4. See preview appear above input
5. Type a message (e.g., "Report fallen tree blocking road")
6. Click send
7. Backend should trigger image-driven incident workflow

## Future Enhancements

- Image compression before sending
- Multiple image support
- Image size validation
- Progress indicator for large images
- Camera capture on mobile devices
- Image editing/cropping before send
