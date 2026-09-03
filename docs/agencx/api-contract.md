# Agencx API contract

## Errors

JSON errors use RFC 9457 Problem Details with media type
`application/problem+json`:

```json
{
  "type": "about:blank",
  "title": "Validation failed",
  "status": 422,
  "detail": "One or more fields are invalid.",
  "instance": "urn:agencx:request:<request_id>",
  "code": "validation_failed",
  "request_id": "<request_id>",
  "errors": [{"pointer": "/field", "code": "required", "detail": "Field is required."}]
}
```

Malformed JSON is `400 malformed_request`. Semantic validation is `422
validation_failed`. Authentication is `401 unauthenticated` with
`WWW-Authenticate: Bearer`; authorization, missing resources, conflicts, rate
limits, upstream failures, and operational failures use stable local codes and
safe details. Rate limits include `Retry-After`.

Successful responses remain resource-oriented: reads and updates use 200,
creation uses 201, and successful commands or deletions use 204 with no body.
SSE failures after a stream starts use an `error` event containing `code`, safe
`detail`, and `request_id`.

The generated frontend OpenAPI types are refreshed with `npm run gen:types` and
checked without writing with `npm run gen:types -- --check`.
