# PRD-106: API Error Handling & Validation Middleware

## Overview
Add structured error handling, validation middleware, and consistent error response formatting to the FastAPI API layer. Currently, the API routes lack global error handlers, return inconsistent error formats, and have minimal input validation beyond Pydantic models.

## Goals
1. **Global Exception Handler** — Catch all unhandled exceptions and return structured JSON error responses with request context
2. **Validation Middleware** — Provide reusable validation decorators for common patterns (symbol format, date ranges, pagination)
3. **Error Taxonomy** — Define a consistent error code system (validation, authentication, authorization, rate limit, server errors)
4. **Error Response Format** — Standardized JSON envelope with error code, message, details, request_id, and timestamp
5. **Request Sanitization** — Input sanitization utilities to prevent injection attacks

## Technical Design

### Error Response Format
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid symbol format",
    "details": [{"field": "symbol", "issue": "Must be 1-5 uppercase letters"}],
    "request_id": "abc-123",
    "timestamp": "2024-01-01T00:00:00Z"
  }
}
```

### Components
- `src/api_errors/__init__.py` — Public API exports
- `src/api_errors/config.py` — Error codes enum, error config dataclass
- `src/api_errors/exceptions.py` — Custom exception hierarchy (AxionAPIError, ValidationError, AuthenticationError, etc.)
- `src/api_errors/handlers.py` — FastAPI exception handlers (global, validation, HTTP, custom)
- `src/api_errors/middleware.py` — Error-catching middleware, request sanitization
- `src/api_errors/validators.py` — Reusable validation decorators and utilities

### Database
- `api_error_logs` table for persistent error tracking

### Dashboard
- Error rates, error distribution by type, recent errors, validation failures

## Success Criteria
- All API errors return consistent JSON format
- No raw 500 errors leak stack traces to clients
- Input validation covers common trading domain patterns
- 40+ tests covering all error paths
