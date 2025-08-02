# UltraThink MCP Integration Guide

## Understanding MCP Architecture

MCP (Model Context Protocol) uses **stdio** (stdin/stdout) for communication, not TCP/HTTP. Each MCP client needs a direct stdio connection to the MCP server.

## Current Setup on Oracle

The `ultrathink_mcp_pool_manager.py` manages MCP server processes:
- **goose-ultrathink** runs as `goose mcp ultrathink`
- Communicates via stdio (not TCP port 8017)
- Shared memory at `/home/ubuntu/.goose/memory`

## How Different AI Clients Can Connect

### 1. Claude (Already Working)
Claude has native MCP support:
```json
{
  "mcpServers": {
    "ultrathink": {
      "command": "goose",
      "args": ["mcp", "ultrathink"],
      "env": {
        "MEMORY_DIR": "/home/ubuntu/.goose/memory"
      }
    }
  }
}
```

### 2. For Gemini/OpenAI Integration

Since they don't have native MCP support, you need an MCP client library:

#### Option A: Python MCP Client
```python
#!/usr/bin/env python3
"""
MCP Client for Gemini/OpenAI to access UltraThink
"""
import subprocess
import json
import asyncio
from typing import Dict, Any

class UltraThinkMCPClient:
    def __init__(self):
        self.process = None
        
    async def connect(self):
        """Start goose mcp ultrathink process"""
        self.process = await asyncio.create_subprocess_exec(
            'goose', 'mcp', 'ultrathink',
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
    async def send_request(self, method: str, params: Dict[str, Any] = None):
        """Send JSON-RPC request to MCP server"""
        request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": 1
        }
        
        # Send request
        request_str = json.dumps(request) + '\n'
        self.process.stdin.write(request_str.encode())
        await self.process.stdin.drain()
        
        # Read response
        response_line = await self.process.stdout.readline()
        return json.loads(response_line.decode())
        
    async def remember(self, content: str, project: str = "general"):
        """Store memory via UltraThink"""
        return await self.send_request("tools/ultrathink_remember", {
            "content": content,
            "project": project,
            "priority": "medium"
        })
        
    async def retrieve(self, query: str, project: str = None):
        """Retrieve memories"""
        params = {"query": query}
        if project:
            params["project"] = project
        return await self.send_request("tools/ultrathink_retrieve", params)

# Usage in Gemini/OpenAI wrapper
async def main():
    client = UltraThinkMCPClient()
    await client.connect()
    
    # Store memory
    await client.remember("User prefers Python for Discord bots", "zgdk")
    
    # Retrieve memories
    memories = await client.retrieve("Discord", "zgdk")
    print(memories)
```

#### Option B: Node.js MCP Client
```javascript
const { spawn } = require('child_process');
const readline = require('readline');

class UltraThinkMCPClient {
    constructor() {
        this.process = null;
        this.rl = null;
    }
    
    connect() {
        // Spawn goose mcp ultrathink
        this.process = spawn('goose', ['mcp', 'ultrathink']);
        
        // Create readline interface
        this.rl = readline.createInterface({
            input: this.process.stdout,
            output: this.process.stdin
        });
    }
    
    async sendRequest(method, params = {}) {
        const request = {
            jsonrpc: "2.0",
            method: method,
            params: params,
            id: Date.now()
        };
        
        // Send request
        this.process.stdin.write(JSON.stringify(request) + '\n');
        
        // Wait for response
        return new Promise((resolve) => {
            this.rl.once('line', (line) => {
                resolve(JSON.parse(line));
            });
        });
    }
    
    async remember(content, project = 'general') {
        return this.sendRequest('tools/ultrathink_remember', {
            content,
            project,
            priority: 'medium'
        });
    }
}
```

### 3. Using socat for TCP Bridge (Advanced)

If you really need TCP access, create a bridge:

```bash
# Terminal 1: Create TCP to stdio bridge
socat TCP-LISTEN:8017,reuseaddr,fork EXEC:"goose mcp ultrathink"

# Terminal 2: Test with netcat
echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | nc localhost 8017
```

### 4. SSH Tunnel for Remote Access

For iPad or remote access:
```bash
# On iPad/remote machine
ssh -L 8017:localhost:8017 oracle

# Then use local TCP bridge
socat TCP-LISTEN:8017,reuseaddr,fork EXEC:"ssh oracle goose mcp ultrathink"
```

## MCP Protocol Basics

### 1. List Available Tools
```json
{
  "jsonrpc": "2.0",
  "method": "tools/list",
  "id": 1
}
```

### 2. Call UltraThink Tools
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "ultrathink_remember",
    "arguments": {
      "content": "Important fact about zgdk project",
      "project": "zgdk",
      "priority": "high"
    }
  },
  "id": 2
}
```

## Integration Examples

### Gemini Integration
```python
# gemini_ultrathink.py
import google.generativeai as genai
from ultrathink_mcp_client import UltraThinkMCPClient

class GeminiWithMemory:
    def __init__(self, api_key):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-pro')
        self.memory = UltraThinkMCPClient()
        
    async def chat(self, message, project="general"):
        # Retrieve relevant memories
        memories = await self.memory.retrieve(message, project)
        
        # Build context
        context = "Relevant memories:\n"
        for mem in memories.get('memories', []):
            context += f"- {mem['content']}\n"
            
        # Generate response with context
        response = self.model.generate_content(
            f"{context}\n\nUser: {message}"
        )
        
        # Store important parts of conversation
        if "remember" in message.lower():
            await self.memory.remember(response.text, project)
            
        return response.text
```

### OpenAI Integration
```python
# openai_ultrathink.py
import openai
from ultrathink_mcp_client import UltraThinkMCPClient

class OpenAIWithMemory:
    def __init__(self, api_key):
        openai.api_key = api_key
        self.memory = UltraThinkMCPClient()
        
    async def chat(self, message, project="general"):
        # Retrieve relevant memories
        memories = await self.memory.retrieve(message, project)
        
        # Build messages with context
        messages = [
            {"role": "system", "content": "You have access to project memories."},
            {"role": "system", "content": f"Project: {project}"}
        ]
        
        # Add memories as context
        for mem in memories.get('memories', []):
            messages.append({
                "role": "system", 
                "content": f"Memory: {mem['content']}"
            })
            
        messages.append({"role": "user", "content": message})
        
        # Get response
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=messages
        )
        
        return response.choices[0].message.content
```

## Testing MCP Connection

### Direct Test
```bash
# Test UltraThink MCP server
echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | goose mcp ultrathink

# Should return list of tools:
# - ultrathink_remember
# - ultrathink_retrieve  
# - ultrathink_sequence
# - ultrathink_graphiti_sync
```

### Python Test Script
```python
#!/usr/bin/env python3
import asyncio
import json

async def test_ultrathink():
    # Start MCP server
    process = await asyncio.create_subprocess_exec(
        'goose', 'mcp', 'ultrathink',
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE
    )
    
    # List tools
    request = json.dumps({
        "jsonrpc": "2.0",
        "method": "tools/list",
        "id": 1
    }) + '\n'
    
    process.stdin.write(request.encode())
    await process.stdin.drain()
    
    response = await process.stdout.readline()
    print("Available tools:", json.loads(response))
    
    # Terminate
    process.terminate()
    await process.wait()

asyncio.run(test_ultrathink())
```

## Summary

1. **MCP uses stdio**, not HTTP/TCP
2. **Each AI client** needs its own MCP client implementation
3. **UltraThink MCP** provides unified memory/todo access
4. **Shared storage** at `/home/ubuntu/.goose/memory`
5. **Multiple clients** can access same data through separate MCP connections

This approach maintains MCP's design while enabling multi-agent collaboration!