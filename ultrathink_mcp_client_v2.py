#!/usr/bin/env python3
"""
UltraThink MCP Client v2 - Workaround for Goose MCP ID bug
Works around the issue where error responses always have ID 0
"""

import subprocess
import json
import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

class UltraThinkMCPClientV2:
    """MCP Client with workaround for ID 0 error responses"""
    
    def __init__(self, project: str = "general"):
        self.process = None
        self.project = project
        self.request_id = 0
        self._reader = None
        self._writer = None
        self._pending_requests = {}  # Track pending requests by ID
        self._initialized = False
        
    async def connect(self):
        """Start goose mcp ultrathink process and establish communication"""
        logger.info(f"Starting UltraThink MCP connection for project: {self.project}")
        
        # Set environment for project context
        import os
        env = os.environ.copy()
        env["GOOSE_PROJECT"] = self.project
        env["MEMORY_DIR"] = f"/home/ubuntu/.goose/memory/{self.project}"
        
        # Start the MCP server process
        self.process = await asyncio.create_subprocess_exec(
            'goose', 'mcp', 'ultrathink',
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env
        )
        
        self._reader = self.process.stdout
        self._writer = self.process.stdin
        
        # Initialize connection
        await self._initialize_connection()
        
    async def _initialize_connection(self):
        """Send initialize request to establish MCP session"""
        self.request_id += 1
        
        request = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "ultrathink-mcp-client-v2",
                    "version": "2.0.0"
                }
            },
            "id": self.request_id
        }
        
        # Send and wait for response
        response = await self._send_and_receive(request)
        
        if "error" in response:
            raise Exception(f"Failed to initialize MCP connection: {response['error']}")
            
        self._initialized = True
        logger.info(f"MCP connection initialized")
        return response
        
    async def _send_and_receive(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Send request and receive response, handling ID 0 errors"""
        # Track this request
        request_id = request.get("id")
        method = request.get("method")
        self._pending_requests[request_id] = method
        
        # Send request
        request_str = json.dumps(request) + '\n'
        logger.debug(f"Sending: {request}")
        self._writer.write(request_str.encode())
        await self._writer.drain()
        
        # Read response
        response_line = await self._reader.readline()
        if not response_line:
            raise Exception("No response from MCP server")
            
        response = json.loads(response_line.decode())
        logger.debug(f"Received: {response}")
        
        # Handle ID 0 error responses
        if response.get("id") == 0 and "error" in response:
            # This is likely an error for our most recent request
            if request_id in self._pending_requests:
                logger.warning(f"Received ID 0 error, assuming it's for request {request_id}")
                response["id"] = request_id
                del self._pending_requests[request_id]
        
        return response
        
    async def disconnect(self):
        """Close MCP connection"""
        if self.process:
            self.process.terminate()
            await self.process.wait()
            logger.info("MCP connection closed")
            
    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available UltraThink tools"""
        if not self._initialized:
            raise Exception("MCP connection not initialized")
            
        self.request_id += 1
        
        request = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "id": self.request_id
        }
        
        response = await self._send_and_receive(request)
        
        if "error" in response:
            # For tools/list errors, return empty list
            logger.error(f"Tools list error: {response['error']}")
            return []
            
        return response.get("result", {}).get("tools", [])
        
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a specific UltraThink tool"""
        if not self._initialized:
            raise Exception("MCP connection not initialized")
            
        self.request_id += 1
        
        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            },
            "id": self.request_id
        }
        
        response = await self._send_and_receive(request)
        
        if "error" in response:
            raise Exception(f"Tool call failed: {response['error']}")
            
        return response.get("result", {})
    
    # High-level convenience methods
    
    async def remember(self, content: str, priority: str = "medium", 
                      tags: Optional[List[str]] = None) -> Dict[str, Any]:
        """Store a memory in UltraThink"""
        return await self.call_tool("ultrathink_remember", {
            "content": content,
            "project": self.project,
            "priority": priority,
            "tags": tags or []
        })
        
    async def retrieve(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieve memories matching query"""
        result = await self.call_tool("ultrathink_retrieve", {
            "query": query,
            "project": self.project,
            "limit": limit
        })
        return result.get("memories", [])


# Alternative: Use goose chat directly
class GooseChatWrapper:
    """Simple wrapper that uses goose chat command instead of MCP"""
    
    def __init__(self, project: str = "general"):
        self.project = project
        
    async def chat(self, message: str) -> str:
        """Send message to goose chat and get response"""
        import os
        env = os.environ.copy()
        env["GOOSE_PROJECT"] = self.project
        
        # Run goose chat with message
        cmd = ['goose', 'chat', '--project', self.project]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env
        )
        
        # Send message and get response
        stdout, stderr = await process.communicate(
            input=f"{message}\nexit\n".encode()
        )
        
        # Parse response
        response = stdout.decode()
        
        # Extract the actual response (skip prompts and commands)
        lines = response.split('\n')
        response_lines = []
        in_response = False
        
        for line in lines:
            if line.strip() == message:
                in_response = True
                continue
            if in_response and line.strip() != 'exit':
                response_lines.append(line)
                
        return '\n'.join(response_lines).strip()


# Test the v2 client
async def test_v2_client():
    """Test the v2 MCP client with workarounds"""
    print("Testing UltraThink MCP Client v2...")
    
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    client = UltraThinkMCPClientV2(project="test")
    
    try:
        # Connect
        await client.connect()
        print("✓ Connected to UltraThink MCP")
        
        # List tools (may fail due to MCP bug, but we handle it)
        print("\nListing tools...")
        tools = await client.list_tools()
        if tools:
            print(f"✓ Available tools: {len(tools)}")
            for tool in tools:
                print(f"  - {tool['name']}: {tool.get('description', 'No description')}")
        else:
            print("⚠ Tools list not available (known MCP issue)")
            print("  But we can still call tools directly!")
            
        # The tools we know exist:
        print("\nKnown UltraThink tools:")
        print("  - ultrathink_remember")
        print("  - ultrathink_retrieve")
        print("  - ultrathink_sequence")
        print("  - ultrathink_graphiti_sync")
            
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()
        print("\n✓ Disconnected")


# Test the chat wrapper
async def test_chat_wrapper():
    """Test the simple goose chat wrapper"""
    print("\nTesting Goose Chat Wrapper...")
    
    wrapper = GooseChatWrapper(project="zgdk")
    
    try:
        response = await wrapper.chat("What project am I working on?")
        print(f"Response: {response}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    # Run tests
    asyncio.run(test_v2_client())
    # asyncio.run(test_chat_wrapper())