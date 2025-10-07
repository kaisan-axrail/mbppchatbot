# Deployment Guide

## Overview

This guide covers deploying the AEON User-Side Chatbot to various hosting platforms and environments.

## Prerequisites

- Node.js 18+ installed
- npm or yarn package manager
- Git for version control
- Access to hosting platform

## Build Process

### Production Build

```bash
# Install dependencies
npm install

# Run production build
npm run build

# Preview build locally (optional)
npm run preview
```

The build process:
1. TypeScript compilation
2. Vite bundling and optimization
3. Asset optimization and minification
4. Output to `dist/` directory

### Build Configuration

**vite.config.ts:**
```typescript
export default defineConfig({
  define: { global: "window" },
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});
```

## Deployment Options

### 1. Vercel (Recommended)

**Automatic Deployment:**

1. Connect GitHub repository to Vercel
2. Configure build settings:
   - Build Command: `npm run build`
   - Output Directory: `dist`
   - Install Command: `npm install`

**Manual Deployment:**

```bash
# Install Vercel CLI
npm i -g vercel

# Deploy
vercel --prod
```

**vercel.json configuration:**
```json
{
  "buildCommand": "npm run build",
  "outputDirectory": "dist",
  "framework": "vite"
}
```

### 2. Netlify

**Automatic Deployment:**

1. Connect repository to Netlify
2. Build settings:
   - Build command: `npm run build`
   - Publish directory: `dist`

**Manual Deployment:**

```bash
# Install Netlify CLI
npm install -g netlify-cli

# Build and deploy
npm run build
netlify deploy --prod --dir=dist
```

**netlify.toml configuration:**
```toml
[build]
  command = "npm run build"
  publish = "dist"

[[redirects]]
  from = "/*"
  to = "/index.html"
  status = 200
```

### 3. AWS S3 + CloudFront

**S3 Bucket Setup:**

```bash
# Create S3 bucket
aws s3 mb s3://aeon-chatbot-frontend

# Configure for static website hosting
aws s3 website s3://aeon-chatbot-frontend \
  --index-document index.html \
  --error-document index.html
```

**Deploy to S3:**

```bash
# Build application
npm run build

# Sync to S3
aws s3 sync dist/ s3://aeon-chatbot-frontend --delete
```

**CloudFront Distribution:**

```json
{
  "Origins": [{
    "DomainName": "aeon-chatbot-frontend.s3-website-us-east-1.amazonaws.com",
    "Id": "S3-aeon-chatbot-frontend",
    "CustomOriginConfig": {
      "HTTPPort": 80,
      "OriginProtocolPolicy": "http-only"
    }
  }],
  "DefaultCacheBehavior": {
    "TargetOriginId": "S3-aeon-chatbot-frontend",
    "ViewerProtocolPolicy": "redirect-to-https"
  }
}
```

### 4. Docker Deployment

**Dockerfile:**

```dockerfile
# Build stage
FROM node:18-alpine as build
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .
RUN npm run build

# Production stage
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

**nginx.conf:**

```nginx
server {
    listen 80;
    server_name localhost;
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /static/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

**Build and run:**

```bash
# Build Docker image
docker build -t aeon-chatbot .

# Run container
docker run -p 80:80 aeon-chatbot
```

## Environment Configuration

### Environment Variables

Create environment-specific configuration:

**Development (.env.development):**
```env
VITE_WEBSOCKET_ENDPOINT=wss://dev-api.example.com/ws
VITE_SESSION_ENDPOINT=https://dev-api.example.com/session
```

**Production (.env.production):**
```env
VITE_WEBSOCKET_ENDPOINT=wss://api.example.com/ws
VITE_SESSION_ENDPOINT=https://api.example.com/session
```

### Configuration Management

Update `src/constants/apiEndpoints.tsx`:

```typescript
const WEBSOCKET_ENDPOINT = import.meta.env.VITE_WEBSOCKET_ENDPOINT || 
  "wss://k1wj10zxv9.execute-api.us-east-1.amazonaws.com/dev";

const SESSION_CLOSE_ENDPOINT = import.meta.env.VITE_SESSION_ENDPOINT || 
  "https://2mrh1juc0e.execute-api.us-east-1.amazonaws.com/prod/conversation-update";
```

## Performance Optimization

### Build Optimizations

**vite.config.ts optimizations:**

```typescript
export default defineConfig({
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom'],
          ui: ['@radix-ui/react-dropdown-menu', 'lucide-react'],
        },
      },
    },
    chunkSizeWarningLimit: 1000,
  },
});
```

### CDN Configuration

**CloudFront Cache Behaviors:**

```json
{
  "CacheBehaviors": [
    {
      "PathPattern": "/static/*",
      "CachePolicyId": "4135ea2d-6df8-44a3-9df3-4b5a84be39ad",
      "TTL": 31536000
    },
    {
      "PathPattern": "*.js",
      "CachePolicyId": "4135ea2d-6df8-44a3-9df3-4b5a84be39ad",
      "TTL": 86400
    }
  ]
}
```

## Security Configuration

### Content Security Policy

Add CSP headers for security:

```html
<meta http-equiv="Content-Security-Policy" 
      content="default-src 'self'; 
               connect-src 'self' wss://k1wj10zxv9.execute-api.us-east-1.amazonaws.com https://2mrh1juc0e.execute-api.us-east-1.amazonaws.com; 
               style-src 'self' 'unsafe-inline';">
```

### HTTPS Configuration

Ensure all deployments use HTTPS:
- Vercel/Netlify: Automatic HTTPS
- AWS: Use CloudFront with SSL certificate
- Docker: Configure reverse proxy with SSL

## Monitoring and Analytics

### Error Tracking

Integrate error tracking service:

```typescript
// src/main.tsx
import * as Sentry from "@sentry/react";

Sentry.init({
  dsn: "YOUR_SENTRY_DSN",
  environment: import.meta.env.MODE,
});
```

### Performance Monitoring

Add performance monitoring:

```typescript
// Web Vitals tracking
import { getCLS, getFID, getFCP, getLCP, getTTFB } from 'web-vitals';

getCLS(console.log);
getFID(console.log);
getFCP(console.log);
getLCP(console.log);
getTTFB(console.log);
```

## CI/CD Pipeline

### GitHub Actions

**.github/workflows/deploy.yml:**

```yaml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'
          cache: 'npm'
      
      - name: Install dependencies
        run: npm ci
      
      - name: Run tests
        run: npm test
      
      - name: Build application
        run: npm run build
      
      - name: Deploy to Vercel
        uses: amondnet/vercel-action@v20
        with:
          vercel-token: ${{ secrets.VERCEL_TOKEN }}
          vercel-org-id: ${{ secrets.ORG_ID }}
          vercel-project-id: ${{ secrets.PROJECT_ID }}
          vercel-args: '--prod'
```

## Health Checks

### Application Health

Implement health check endpoint:

```typescript
// src/utils/healthCheck.ts
export const checkHealth = async () => {
  try {
    const wsTest = new WebSocket(WEBSOCKET_ENDPOINT);
    wsTest.close();
    return { status: 'healthy', timestamp: new Date().toISOString() };
  } catch (error) {
    return { status: 'unhealthy', error: error.message };
  }
};
```

### Monitoring Dashboard

Set up monitoring for:
- WebSocket connection success rate
- Page load times
- Error rates
- User session duration

## Rollback Strategy

### Version Management

Tag releases for easy rollback:

```bash
# Tag current release
git tag -a v1.0.0 -m "Release version 1.0.0"
git push origin v1.0.0

# Rollback to previous version
git checkout v0.9.0
npm run build
# Deploy previous version
```

### Blue-Green Deployment

For zero-downtime deployments:

1. Deploy new version to staging environment
2. Test thoroughly
3. Switch traffic to new version
4. Keep old version as backup
5. Remove old version after verification

## Troubleshooting

### Common Deployment Issues

1. **Build Failures**
   - Check Node.js version compatibility
   - Verify all dependencies are installed
   - Check for TypeScript errors

2. **Runtime Errors**
   - Verify environment variables
   - Check API endpoint accessibility
   - Monitor browser console for errors

3. **Performance Issues**
   - Analyze bundle size
   - Check CDN configuration
   - Monitor Core Web Vitals

### Debug Commands

```bash
# Analyze bundle size
npm run build -- --analyze

# Check for outdated dependencies
npm outdated

# Audit for security vulnerabilities
npm audit
```