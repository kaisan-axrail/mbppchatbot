# MBPP Workflow System Architecture

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          USER INTERFACE                             │
│                    (Web/Mobile/WhatsApp)                            │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             │ HTTP/WebSocket
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      API GATEWAY                                    │
│  ┌──────────────────┐  ┌──────────────────┐  ┌─────────────────┐  │
│  │  WebSocket API   │  │   HTTP API       │  │   REST API      │  │
│  │  (Real-time)     │  │  (Workflows)     │  │  (Documents)    │  │
│  └──────────────────┘  └──────────────────┘  └─────────────────┘  │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    MBPP AGENT (Lambda)                              │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                  Intent Detector                             │  │
│  │  • Analyzes user message                                     │  │
│  │  • Detects workflow type or RAG query                        │  │
│  │  • Routes to appropriate handler                             │  │
│  └────────────────┬─────────────────────────────────────────────┘  │
│                   │                                                 │
│       ┌───────────┴───────────┐                                    │
│       ▼                       ▼                                    │
│  ┌─────────────────┐    ┌─────────────────┐                       │
│  │ Workflow Agent  │    │   RAG Agent     │                       │
│  │                 │    │                 │                       │
│  │ • Complaint     │    │ • Vector Search │                       │
│  │ • Text Incident │    │ • Context Build │                       │
│  │ • Image Incident│    │ • Answer Gen    │                       │
│  └─────────────────┘    └─────────────────┘                       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      EXTERNAL SERVICES                              │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │
│  │   Bedrock    │  │  OpenSearch  │  │  DynamoDB    │            │
│  │              │  │              │  │              │            │
│  │ • Claude 3.5 │  │ • Vectors    │  │ • Sessions   │            │
│  │ • Sonnet     │  │ • Documents  │  │ • Tickets    │            │
│  │ • Streaming  │  │ • Search     │  │ • Analytics  │            │
│  └──────────────┘  └──────────────┘  └──────────────┘            │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Workflow Processing Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                      USER MESSAGE                                   │
│              "MBPP website is down"                                 │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
                    ┌────────────────┐
                    │ Intent Detector│
                    └────────┬───────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
        ┌──────────┐   ┌──────────┐   ┌──────────┐
        │Complaint │   │  Text    │   │  Image   │
        │ Workflow │   │ Incident │   │ Incident │
        └────┬─────┘   └────┬─────┘   └────┬─────┘
             │              │              │
             ▼              ▼              ▼
        ┌──────────────────────────────────────┐
        │      MCP Workflow Tool               │
        │  • State Management                  │
        │  • Step Coordination                 │
        │  • Ticket Generation                 │
        └────────────────┬─────────────────────┘
                         │
                         ▼
                ┌────────────────┐
                │ Ticket Created │
                │  20239/09/25   │
                └────────────────┘
```

## RAG Query Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                      USER MESSAGE                                   │
│           "What are MBPP's operating hours?"                        │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
                    ┌────────────────┐
                    │ Intent Detector│
                    │  (RAG Query)   │
                    └────────┬───────┘
                             │
                             ▼
                    ┌────────────────┐
                    │  RAG Agent     │
                    └────────┬───────┘
                             │
                             ▼
                    ┌────────────────┐
                    │ Vector Search  │
                    │  (OpenSearch)  │
                    └────────┬───────┘
                             │
                             ▼
                    ┌────────────────┐
                    │ Build Context  │
                    │ from Results   │
                    └────────┬───────┘
                             │
                             ▼
                    ┌────────────────┐
                    │ Bedrock Claude │
                    │ Generate Answer│
                    └────────┬───────┘
                             │
                             ▼
                    ┌────────────────┐
                    │ Return Answer  │
                    │ to User        │
                    └────────────────┘
```

## Workflow State Machine

### Complaint Workflow (6 Steps)

```
┌─────────┐
│ START   │
└────┬────┘
     │
     ▼
┌─────────────────────┐
│ Step 1: Triage      │ "Would you like to report an incident?"
└────┬────────────────┘
     │ User: "Service Complaint"
     ▼
┌─────────────────────┐
│ Step 2: Describe    │ "Please describe the issue"
└────┬────────────────┘
     │ User: "Website down"
     ▼
┌─────────────────────┐
│ Step 3: Verify      │ "Is your internet working?"
└────┬────────────────┘
     │ User: "Yes"
     ▼
┌─────────────────────┐
│ Step 4: Log Ticket  │ "Logging the ticket..."
└────┬────────────────┘
     │
     ▼
┌─────────────────────┐
│ Step 5: Confirm     │ Show ticket details
└────┬────────────────┘
     │ User: "Yes"
     ▼
┌─────────────────────┐
│ Step 6: Complete    │ "Ticket logged: 20239/09/25"
└─────────────────────┘
```

### Text Incident Workflow (7 Steps)

```
┌─────────┐
│ START   │
└────┬────┘
     │
     ▼
┌─────────────────────┐
│ Step 1: Initiate    │ "Share image, location, description"
└────┬────────────────┘
     │ User: "Fallen tree at location X"
     ▼
┌─────────────────────┐
│ Step 2: Submit Info │ Receive description + optional image
└────┬────────────────┘
     │
     ▼
┌─────────────────────┐
│ Step 3: Confirm     │ "Confirm incident report?"
└────┬────────────────┘
     │ User: "Yes"
     ▼
┌─────────────────────┐
│ Step 4: Location    │ "Where is this?"
└────┬────────────────┘
     │ User: [GPS/Address]
     ▼
┌─────────────────────┐
│ Step 5: Hazard      │ "Is it blocking the road?"
└────┬────────────────┘
     │ User: "Yes"
     ▼
┌─────────────────────┐
│ Step 6: Process     │ "Logging the ticket..."
└────┬────────────────┘
     │
     ▼
┌─────────────────────┐
│ Step 7: Complete    │ "Ticket logged: 20368/09/25"
└─────────────────────┘
```

### Image Incident Workflow (6 Steps)

```
┌─────────┐
│ START   │ User uploads image
└────┬────┘
     │
     ▼
┌─────────────────────┐
│ Step 1: Detect      │ "Image detected. Confirm incident?"
└────┬────────────────┘
     │ User: "Yes"
     ▼
┌─────────────────────┐
│ Step 2: Describe    │ "Describe what happened + location"
└────┬────────────────┘
     │ User: "Fallen tree at X"
     ▼
┌─────────────────────┐
│ Step 3: Details     │ Receive description + location
└────┬────────────────┘
     │
     ▼
┌─────────────────────┐
│ Step 4: Hazard      │ "Is it blocking the road?"
└────┬────────────────┘
     │ User: "Yes"
     ▼
┌─────────────────────┐
│ Step 5: Process     │ "Logging the ticket..."
└────┬────────────────┘
     │
     ▼
┌─────────────────────┐
│ Step 6: Complete    │ "Ticket logged: 20368/09/25"
└─────────────────────┘
```

## Session Management

```
┌─────────────────────────────────────────────────────────────┐
│                    Session Store                            │
│                                                             │
│  session-123: {                                             │
│    workflow_id: "uuid-abc",                                 │
│    workflow_type: "complaint",                              │
│    current_step: 3,                                         │
│    data: {                                                  │
│      description: "Website down",                           │
│      verification: "Yes"                                    │
│    }                                                        │
│  }                                                          │
│                                                             │
│  session-456: {                                             │
│    workflow_id: "uuid-def",                                 │
│    workflow_type: "text_incident",                          │
│    current_step: 5,                                         │
│    data: {                                                  │
│      description: "Fallen tree",                            │
│      location: "Jalan Terapung",                            │
│      hazard: "Yes"                                          │
│    }                                                        │
│  }                                                          │
└─────────────────────────────────────────────────────────────┘
```

## Data Flow

```
User Input
    │
    ▼
┌─────────────────┐
│ API Gateway     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Lambda Handler  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ MBPP Agent      │
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌────────┐ ┌────────┐
│Workflow│ │  RAG   │
│ Agent  │ │ Agent  │
└────┬───┘ └───┬────┘
     │         │
     ▼         ▼
┌────────┐ ┌────────┐
│ MCP    │ │OpenSrch│
│ Tool   │ │ Vector │
└────┬───┘ └───┬────┘
     │         │
     ▼         ▼
┌────────┐ ┌────────┐
│Bedrock │ │Bedrock │
│Claude  │ │Claude  │
└────┬───┘ └───┬────┘
     │         │
     └────┬────┘
          │
          ▼
    ┌──────────┐
    │ Response │
    └──────────┘
```

## Component Interaction

```
┌──────────────────────────────────────────────────────────────┐
│                    MBPP Agent                                │
│                                                              │
│  ┌────────────────────────────────────────────────────┐     │
│  │  Intent Detection                                  │     │
│  │  • Keyword matching                                │     │
│  │  • Image detection                                 │     │
│  │  • Context analysis                                │     │
│  └────────────────┬───────────────────────────────────┘     │
│                   │                                          │
│       ┌───────────┴───────────┐                             │
│       ▼                       ▼                             │
│  ┌─────────────┐         ┌─────────────┐                   │
│  │  Workflow   │         │  RAG Agent  │                   │
│  │   Agent     │         │             │                   │
│  │             │         │             │                   │
│  │  Tools:     │         │  Tools:     │                   │
│  │  • workflow │         │  • search   │                   │
│  │             │         │  • retrieve │                   │
│  └──────┬──────┘         └──────┬──────┘                   │
│         │                       │                           │
│         ▼                       ▼                           │
│  ┌─────────────┐         ┌─────────────┐                   │
│  │ MCP Tool    │         │ Vector DB   │                   │
│  │ (Workflow)  │         │ (OpenSearch)│                   │
│  └─────────────┘         └─────────────┘                   │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

## Deployment Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      AWS Cloud                              │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  VPC                                                  │  │
│  │                                                       │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │  │
│  │  │   Lambda    │  │   Lambda    │  │   Lambda    │ │  │
│  │  │  Workflow   │  │     RAG     │  │   WebSocket │ │  │
│  │  │   Agent     │  │    Agent    │  │   Handler   │ │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘ │  │
│  │                                                       │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Data Layer                                           │  │
│  │                                                       │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │  │
│  │  │  DynamoDB   │  │ OpenSearch  │  │     S3      │ │  │
│  │  │  (Tickets)  │  │  (Vectors)  │  │ (Documents) │ │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘ │  │
│  │                                                       │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  AI Services                                          │  │
│  │                                                       │  │
│  │  ┌─────────────────────────────────────────────────┐ │  │
│  │  │  Amazon Bedrock                                  │ │  │
│  │  │  • Claude 3.5 Sonnet                            │ │  │
│  │  │  • Streaming responses                          │ │  │
│  │  └─────────────────────────────────────────────────┘ │  │
│  │                                                       │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

**Legend:**
- `┌─┐` = Component boundary
- `│` = Connection/Flow
- `▼` = Data flow direction
- `┬` = Branch point
