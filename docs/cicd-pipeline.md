# CI/CD Pipeline Documentation

This document describes the Continuous Integration and Continuous Deployment (CI/CD) pipeline for the ConvoPilot application.

## Overview

The CI/CD pipeline consists of three main workflows:
1. Testing (`test.yml`)
2. Docker Image Building (`docker.yml`)
3. Deployment (`deploy.yml`)

## Workflow Triggers

### Test Workflow
- Triggers on:
  - Push to main/develop
  - Pull requests to main/develop
  ```yaml
  on:
    push:
      branches: [ main, develop ]
    pull_request:
      branches: [ main, develop ]
  ```

### Docker Build Workflow
- Triggers on:
  - Push to main
  - Version tags
  ```yaml
  on:
    push:
      branches: [ main ]
      tags: [ 'v*.*.*' ]
  ```

### Deploy Workflow
- Triggers on:
  - Successful Docker build
  ```yaml
  on:
    workflow_run:
      workflows: ["Build and Push Docker Images"]
      types:
        - completed
  ```

## Test Pipeline

### Services
- PostgreSQL 15
  ```yaml
  postgres:
    image: postgres:15-alpine
    env:
      POSTGRES_DB: convopilot_test
  ```
- Redis 7
  ```yaml
  redis:
    image: redis:7-alpine
  ```

### Steps
1. **Setup**
   - Python 3.10
   - Node.js 18
   - Dependencies installation

2. **Backend Tests**
   ```yaml
   - name: Run backend tests
     run: pytest tests/ --cov=app
   ```

3. **Frontend Tests**
   ```yaml
   - name: Run frontend tests
     run: npm test -- --coverage
   ```

4. **Coverage Report**
   ```yaml
   - uses: codecov/codecov-action@v3
   ```

## Docker Build Pipeline

### Authentication
```yaml
- uses: docker/login-action@v2
  with:
    registry: ghcr.io
```

### Build Steps
1. **Extract Metadata**
   ```yaml
   - uses: docker/metadata-action@v4
   ```

2. **Build Backend**
   ```yaml
   - uses: docker/build-push-action@v4
     with:
       context: ./backend
   ```

3. **Build Frontend**
   ```yaml
   - uses: docker/build-push-action@v4
     with:
       context: ./frontend
   ```

### Tags
- Semantic versions: `v1.2.3`
- Branch builds: `main`, `develop`
- SHA builds: `sha-abc123`

## Deployment Pipeline

### Prerequisites
- SSH access to production server
- Environment variables
- Slack webhook for notifications

### Deployment Steps
1. **Connect to Server**
   ```yaml
   - uses: appleboy/ssh-action@v1.0.0
   ```

2. **Update Application**
   ```bash
   docker compose pull
   docker compose up -d
   ```

3. **Health Checks**
   ```bash
   docker compose ps
   docker compose logs
   ```

4. **Notifications**
   ```yaml
   - uses: slackapi/slack-github-action@v1.24.0
   ```

## Environment Variables

### Required Secrets
```yaml
# GitHub Secrets
DEPLOY_HOST: "production.example.com"
DEPLOY_USER: "deploy"
DEPLOY_KEY: "ssh-private-key"
SLACK_BOT_TOKEN: "xoxb-..."

# Repository Secrets
OPENAI_API_KEY: "sk-..."
GOOGLE_API_KEY: "AIza..."
PINECONE_API_KEY: "..."
```

## Security Measures

1. **Secret Scanning**
   ```yaml
   - uses: actions/secret-scanning@v1
   ```

2. **SBOM Generation**
   ```yaml
   - uses: anchore/sbom-action@v0
   ```

3. **Container Scanning**
   ```yaml
   - uses: aquasecurity/trivy-action@v1
   ```

## Monitoring

### Metrics
- Build duration
- Test coverage
- Deployment success rate
- Container health

### Alerts
- Pipeline failures
- Coverage drops
- Security issues
- Deployment issues

## Rollback Procedure

1. **Automatic Rollback**
   ```bash
   docker compose rollback
   ```

2. **Manual Rollback**
   ```bash
   # Get previous version
   docker images --format "{{.Tag}}" | head -n 2
   
   # Rollback
   docker compose down
   docker tag $IMAGE:$PREVIOUS_TAG $IMAGE:latest
   docker compose up -d
   ```

## Best Practices

1. **Version Control**
   - Protected branches
   - Required reviews
   - Signed commits

2. **Testing**
   - Run tests in parallel
   - Cache dependencies
   - Fail fast on errors

3. **Docker**
   - Multi-stage builds
   - Layer caching
   - Security scanning

4. **Deployment**
   - Zero-downtime updates
   - Health checks
   - Automated rollbacks

## Troubleshooting

### Common Issues

1. **Test Failures**
   ```bash
   # View test logs
   gh run view --log
   ```

2. **Build Failures**
   ```bash
   # Check build cache
   docker buildx prune
   ```

3. **Deployment Failures**
   ```bash
   # Check container logs
   docker compose logs --tail=100
   ```

### Recovery Steps

1. **Pipeline Failure**
   - Check logs
   - Fix issues
   - Re-run workflow

2. **Deployment Failure**
   - Roll back to last version
   - Check logs
   - Fix and redeploy

## Future Improvements

1. **Pipeline Optimization**
   - Parallel testing
   - Build caching
   - Test splitting

2. **Security**
   - SAST/DAST scanning
   - Dependency scanning
   - Image signing

3. **Monitoring**
   - APM integration
   - Log aggregation
   - Metrics dashboard
