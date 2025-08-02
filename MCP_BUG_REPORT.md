# MCP Protocol Bug in Goose

## Issue Summary
All MCP servers in Goose (memory, ultrathink, etc.) return error responses with ID 0 instead of the original request ID, breaking JSON-RPC protocol compliance.

## Bug Details

### Expected Behavior (JSON-RPC 2.0 spec):
```json
Request:  {"jsonrpc": "2.0", "method": "tools/list", "id": 2}
Response: {"jsonrpc": "2.0", "error": {...}, "id": 2}  // Same ID
```

### Actual Behavior in Goose:
```json
Request:  {"jsonrpc": "2.0", "method": "tools/list", "id": 2}
Response: {"jsonrpc": "2.0", "error": {...}, "id": 0}  // Always ID 0
```

## Affected Components
- All MCP servers: memory, ultrathink, developer, tutorial
- Error: "JSON serialization error: data did not match any variant of untagged enum JsonRpcMessage"
- The initialize method works, but tools/list and other methods fail

## Root Cause
The error handling in Goose MCP implementation doesn't preserve the request ID when returning errors.

## Workaround
The `ultrathink_mcp_client_v2.py` implements a workaround:
1. Track pending requests by ID
2. When receiving ID 0 error, assume it's for the most recent request
3. Manually fix the ID in the response

## Impact
- Standard MCP clients cannot properly match error responses to requests
- Makes it difficult to implement robust async communication
- Breaks compatibility with MCP protocol specification

## Recommended Fix
In Goose MCP server implementation, ensure error responses preserve the original request ID instead of defaulting to 0.

## Test Case
```bash
# This demonstrates the bug:
(echo '{"jsonrpc":"2.0","method":"initialize","params":{...},"id":1}' && \
 echo '{"jsonrpc":"2.0","method":"tools/list","id":2}') | goose mcp memory

# Returns error with ID 0 instead of ID 2
```