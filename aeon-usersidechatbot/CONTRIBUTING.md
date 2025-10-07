# Contributing Guide

## Welcome

Thank you for your interest in contributing to the AEON User-Side Chatbot project! This guide will help you get started with contributing to the codebase.

## Getting Started

### Prerequisites

- Node.js 18 or higher
- npm or yarn
- Git
- Code editor (VS Code recommended)

### Development Setup

1. **Clone the repository:**
```bash
git clone <repository-url>
cd aeon-usersidechatbot/aeon.web.chat
```

2. **Install dependencies:**
```bash
npm install
```

3. **Start development server:**
```bash
npm run dev
```

4. **Open browser:**
Navigate to `http://localhost:5173`

## Development Workflow

### Branch Strategy

- `main` - Production-ready code
- `develop` - Integration branch for features
- `feature/*` - Feature development branches
- `bugfix/*` - Bug fix branches
- `hotfix/*` - Critical production fixes

### Creating a Feature Branch

```bash
# Create and switch to feature branch
git checkout -b feature/your-feature-name

# Make your changes
# ...

# Commit changes
git add .
git commit -m "feat: add your feature description"

# Push branch
git push origin feature/your-feature-name
```

## Code Standards

### TypeScript Guidelines

- Use strict TypeScript configuration
- Define proper types for all props and state
- Avoid `any` type - use proper typing
- Use interfaces for object shapes
- Export types from dedicated files

**Example:**
```typescript
// Good
interface ChatMessage {
  id: string;
  content: string;
  sender: 'user' | 'assistant';
  timestamp: Date;
}

// Avoid
const message: any = { ... };
```

### React Best Practices

- Use functional components with hooks
- Implement proper error boundaries
- Use React.memo for performance optimization
- Follow hooks rules (no conditional hooks)
- Use custom hooks for reusable logic

**Example:**
```typescript
// Good
const ChatMessage = React.memo(({ message }: { message: Message }) => {
  return <div>{message.contents}</div>;
});

// Custom hook
const useChat = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  // ... hook logic
  return { messages, setMessages };
};
```

### Styling Guidelines

- Use Tailwind CSS utility classes
- Follow mobile-first responsive design
- Use CSS custom properties for theming
- Avoid inline styles
- Use semantic class names for custom CSS

**Example:**
```tsx
// Good
<div className="flex flex-col space-y-4 p-4 bg-white rounded-lg shadow-md">
  <h2 className="text-lg font-semibold text-gray-800">Title</h2>
</div>

// Avoid
<div style={{ display: 'flex', padding: '16px' }}>
```

## Component Guidelines

### Component Structure

```typescript
// Component file structure
import React from 'react';
import { ComponentProps } from './types';
import './Component.scss'; // if needed

interface Props {
  // Define props interface
}

export const Component: React.FC<Props> = ({ prop1, prop2 }) => {
  // Hooks at the top
  const [state, setState] = useState();
  
  // Event handlers
  const handleClick = () => {
    // handler logic
  };
  
  // Render
  return (
    <div>
      {/* JSX */}
    </div>
  );
};
```

### File Naming Conventions

- Components: `PascalCase.tsx`
- Hooks: `useCamelCase.tsx`
- Utilities: `camelCase.ts`
- Types: `types.ts`
- Constants: `UPPER_SNAKE_CASE`

### Directory Structure

```
src/
├── components/
│   ├── ui/              # Base UI components
│   └── generic/         # Layout components
├── hooks/               # Custom hooks
├── utils/               # Utility functions
├── types/               # Type definitions
├── constants/           # Application constants
└── views/               # Page components
```

## Testing Guidelines

### Writing Tests

- Write unit tests for utilities and hooks
- Write integration tests for components
- Use React Testing Library for component tests
- Mock external dependencies
- Aim for meaningful test coverage

**Example:**
```typescript
// Component test
import { render, screen } from '@testing-library/react';
import { ChatMessage } from './ChatMessage';

describe('ChatMessage', () => {
  it('renders message content', () => {
    const message = {
      id: '1',
      contents: 'Hello world',
      sender: 'user' as const
    };
    
    render(<ChatMessage message={message} />);
    expect(screen.getByText('Hello world')).toBeInTheDocument();
  });
});
```

### Running Tests

```bash
# Run all tests
npm test

# Run tests in watch mode
npm test -- --watch

# Run tests with coverage
npm test -- --coverage
```

## Commit Guidelines

### Commit Message Format

Use conventional commits format:

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types:**
- `feat` - New feature
- `fix` - Bug fix
- `docs` - Documentation changes
- `style` - Code style changes
- `refactor` - Code refactoring
- `test` - Adding tests
- `chore` - Maintenance tasks

**Examples:**
```bash
feat(chat): add message streaming support
fix(websocket): handle connection timeout properly
docs(api): update WebSocket documentation
style(ui): improve button hover states
refactor(hooks): extract message logic to custom hook
test(chat): add unit tests for useChat hook
chore(deps): update React to v18.2.0
```

## Pull Request Process

### Before Submitting

1. **Run quality checks:**
```bash
npm run lint
npm test
npm run build
```

2. **Update documentation if needed**
3. **Add tests for new features**
4. **Ensure all tests pass**

### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing completed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] Tests pass locally
```

### Review Process

1. **Automated checks** must pass
2. **Code review** by team member
3. **Testing** in staging environment
4. **Approval** from maintainer
5. **Merge** to main branch

## Code Review Guidelines

### As a Reviewer

- Be constructive and respectful
- Focus on code quality and maintainability
- Check for security issues
- Verify tests are adequate
- Ensure documentation is updated

### Review Checklist

- [ ] Code follows project standards
- [ ] Logic is clear and efficient
- [ ] Error handling is appropriate
- [ ] Tests cover new functionality
- [ ] Documentation is updated
- [ ] No security vulnerabilities
- [ ] Performance considerations addressed

## Issue Reporting

### Bug Reports

Use the bug report template:

```markdown
**Bug Description**
Clear description of the bug

**Steps to Reproduce**
1. Go to '...'
2. Click on '...'
3. See error

**Expected Behavior**
What should happen

**Actual Behavior**
What actually happens

**Environment**
- Browser: [e.g. Chrome 91]
- OS: [e.g. macOS 12.0]
- Version: [e.g. 1.0.0]

**Screenshots**
If applicable, add screenshots
```

### Feature Requests

Use the feature request template:

```markdown
**Feature Description**
Clear description of the feature

**Use Case**
Why is this feature needed?

**Proposed Solution**
How should this be implemented?

**Alternatives Considered**
Other solutions you've considered

**Additional Context**
Any other relevant information
```

## Development Tools

### Recommended VS Code Extensions

- TypeScript and JavaScript Language Features
- ES7+ React/Redux/React-Native snippets
- Tailwind CSS IntelliSense
- ESLint
- Prettier
- Auto Rename Tag
- Bracket Pair Colorizer

### VS Code Settings

```json
{
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.fixAll.eslint": true
  },
  "typescript.preferences.importModuleSpecifier": "relative"
}
```

## Performance Guidelines

### Optimization Best Practices

- Use React.memo for expensive components
- Implement proper key props for lists
- Avoid unnecessary re-renders
- Use useCallback and useMemo appropriately
- Lazy load components when possible

### Bundle Size Management

- Analyze bundle size regularly
- Use dynamic imports for code splitting
- Remove unused dependencies
- Optimize images and assets

## Security Guidelines

### Security Best Practices

- Validate all user inputs
- Sanitize data before rendering
- Use HTTPS for all communications
- Implement proper error handling
- Avoid exposing sensitive information

### Common Security Issues

- XSS vulnerabilities in markdown rendering
- WebSocket connection security
- Session management
- Input validation

## Getting Help

### Resources

- **Documentation**: Check existing docs first
- **Issues**: Search existing issues
- **Discussions**: Use GitHub discussions for questions
- **Code Review**: Ask for help in PR comments

### Contact

- **Team Lead**: [contact information]
- **Technical Questions**: Create GitHub issue
- **General Questions**: Use discussions

## Recognition

Contributors will be recognized in:
- CONTRIBUTORS.md file
- Release notes
- Project documentation

Thank you for contributing to the AEON User-Side Chatbot project!