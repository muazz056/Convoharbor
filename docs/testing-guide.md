# Testing Guide

This guide explains the testing setup, how to run tests, and how to add new tests to the ConvoPilot application.

## Testing Stack

- **pytest**: Main testing framework
- **pytest-cov**: Coverage reporting
- **pytest-mock**: Mocking functionality
- **pytest-xdist**: Parallel test execution
- **requests-mock**: Mock HTTP requests

## Test Structure

```
backend/
├── tests/
│   ├── conftest.py           # Shared fixtures
│   ├── requirements-test.txt # Test dependencies
│   ├── test_auth_service.py  # Authentication tests
│   ├── test_chat_service.py  # Chat service tests
│   ├── test_vector_service.py # Vector search tests
│   └── test_embedding_service.py # Embedding tests
```

## Running Tests

1. Install test dependencies:
   ```bash
   pip install -r backend/tests/requirements-test.txt
   ```

2. Run all tests:
   ```bash
   pytest backend/tests/
   ```

3. Run with coverage:
   ```bash
   pytest backend/tests/ --cov=app --cov-report=html
   ```

4. Run specific test file:
   ```bash
   pytest backend/tests/test_auth_service.py
   ```

5. Run tests in parallel:
   ```bash
   pytest -n auto backend/tests/
   ```

## Test Categories

### Unit Tests
- Test individual components in isolation
- Mock external dependencies
- Fast execution
- Example:
  ```python
  def test_authenticate_user(auth_service):
      result = auth_service.authenticate_user("test@example.com", "password")
      assert result is not None
  ```

### Integration Tests
- Test component interactions
- Use test databases
- Example:
  ```python
  def test_chat_with_vector_search(chat_service, vector_service):
      result = chat_service.get_response_with_context(...)
      assert result.contains_relevant_info
  ```

### API Tests
- Test HTTP endpoints
- Use test client
- Example:
  ```python
  def test_login_endpoint(client):
      response = client.post("/api/v1/auth/login", json={...})
      assert response.status_code == 200
  ```

## Test Configuration

### pytest.ini
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
```

### Coverage Configuration
```ini
[coverage:run]
source = app
omit = 
    */migrations/*
    */tests/*
```

## Fixtures

### Database Fixtures
```python
@pytest.fixture
def app():
    app = create_app({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:'
    })
    return app
```

### Authentication Fixtures
```python
@pytest.fixture
def auth_headers():
    return {
        'Authorization': 'Bearer test-token',
        'Content-Type': 'application/json'
    }
```

### Mock Response Fixtures
```python
@pytest.fixture
def mock_openai_response():
    return {
        "choices": [{
            "message": {
                "content": "Test response"
            }
        }]
    }
```

## Writing New Tests

1. Create test file:
   ```python
   """
   Tests for XYZ functionality.
   """
   import pytest
   from app.services.xyz import XYZService
   
   def test_xyz_feature(xyz_service):
       result = xyz_service.do_something()
       assert result is not None
   ```

2. Add fixtures if needed:
   ```python
   @pytest.fixture
   def xyz_service(app):
       return XYZService()
   ```

3. Add to conftest.py if fixture is shared:
   ```python
   @pytest.fixture(scope="session")
   def shared_fixture():
       return SharedResource()
   ```

## Best Practices

1. **Test Isolation**
   - Each test should be independent
   - Clean up after tests
   - Use fresh fixtures

2. **Meaningful Names**
   ```python
   def test_user_creation_with_valid_data():
   def test_user_creation_fails_with_invalid_email():
   ```

3. **Arrange-Act-Assert**
   ```python
   def test_something():
       # Arrange
       service = Service()
       data = {"key": "value"}
       
       # Act
       result = service.process(data)
       
       # Assert
       assert result.is_valid
   ```

4. **Mock External Services**
   ```python
   @patch('app.services.openai.ChatCompletion')
   def test_chat(mock_openai):
       mock_openai.create.return_value = mock_response
   ```

5. **Test Edge Cases**
   ```python
   def test_division():
       assert service.divide(4, 2) == 2
       with pytest.raises(ValueError):
           service.divide(4, 0)
   ```

## Continuous Integration

Tests run automatically on:
- Every push to main/develop
- Pull requests
- Nightly builds

See GitHub Actions workflow:
```yaml
- name: Run tests
  run: |
    pytest tests/ --cov=app --cov-report=xml
```

## Coverage Goals

- Minimum coverage: 80%
- Target coverage: 90%
- Critical paths: 100%

Monitor coverage in PRs and CI/CD pipeline.

## Debugging Tests

1. Show print output:
   ```bash
   pytest -s
   ```

2. Verbose output:
   ```bash
   pytest -v
   ```

3. Debug on error:
   ```bash
   pytest --pdb
   ```

4. List all tests:
   ```bash
   pytest --collect-only
   ```
