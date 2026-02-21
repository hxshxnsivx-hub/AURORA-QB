# Contributing to AURORA Assess

Thank you for your interest in contributing to AURORA Assess!

## Development Setup

1. Fork the repository
2. Clone your fork
3. Follow the setup instructions in README.md
4. Create a new branch for your feature/fix

## Code Standards

### Python (Backend)

- Follow PEP 8 style guide
- Use type hints for all function signatures
- Format code with Black (line length: 100)
- Lint with flake8
- Write docstrings for all public functions and classes
- Maintain test coverage above 80%

### TypeScript (Frontend)

- Follow the project's ESLint configuration
- Use TypeScript strict mode
- Format code with Prettier
- Use functional components with hooks
- Write meaningful component and function names

## Testing Requirements

### Unit Tests

- Write unit tests for all new functions and classes
- Test edge cases and error conditions
- Use descriptive test names

### Property-Based Tests

- Write property tests for correctness properties
- Use Hypothesis (Python) or fast-check (TypeScript)
- Run tests with minimum 100 iterations
- Tag tests with property numbers

Example:
```python
from hypothesis import given, settings
import hypothesis.strategies as st

@settings(max_examples=100)
@given(user_role=st.sampled_from(['Student', 'Faculty', 'Admin']))
def test_property_1_rbac_enforcement(user_role):
    """Property 1: Role-Based Access Control Enforcement"""
    # Test implementation
    pass
```

## Commit Messages

Use conventional commit format:

```
type(scope): subject

body

footer
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

Example:
```
feat(auth): implement JWT token generation

- Add JWT token creation utility
- Add token expiration handling
- Add refresh token support

Closes #123
```

## Pull Request Process

1. Update documentation for any new features
2. Add tests for new functionality
3. Ensure all tests pass
4. Update CHANGELOG.md
5. Request review from maintainers

## Code Review Guidelines

- Be respectful and constructive
- Focus on code quality and maintainability
- Suggest improvements with examples
- Approve when standards are met

## Questions?

Open an issue or reach out to the maintainers.
