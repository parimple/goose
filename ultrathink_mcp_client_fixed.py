#!/usr/bin/env python3
"""
UltraThink MCP Client (Fixed Version)
Improved protocol handling for MCP communication
"""

import subprocess
import json
import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid

# Enhanced logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class UltraThinkMCPClient:
    """Fixed MCP Client with better protocol handling"""
    
    def __init__(self, project: str = "general"):
        self.process = None
        self.project = project
        self.request_id = 0
        self._reader = None
        self._writer = None
        self._response_buffer = []
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
        
        # Start background reader
        asyncio.create_task(self._background_reader())
        
        # Initialize connection
        await self._initialize_connection()
        
    async def _background_reader(self):
        """Continuously read from stdout and buffer responses"""
        try:
            while True:
                line = await self._reader.readline()
                if not line:
                    break
                    
                try:
                    data = json.loads(line.decode().strip())
                    logger.debug(f"Received: {data}")
                    self._response_buffer.append(data)
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse JSON: {line.decode().strip()}")
                except Exception as e:
                    logger.error(f"Reader error: {e}")
        except Exception as e:
            logger.error(f"Background reader crashed: {e}")
    
    async def _wait_for_response(self, expected_id: int, timeout: float = 5.0) -> Dict[str, Any]:
        """Wait for a response with specific ID"""
        start_time = asyncio.get_event_loop().time()
        
        while True:
            # Check timeout
            if asyncio.get_event_loop().time() - start_time > timeout:
                raise TimeoutError(f"Timeout waiting for response with ID {expected_id}")
            
            # Check buffer for our response
            for i, response in enumerate(self._response_buffer):
                if response.get("id") == expected_id:
                    # Found it, remove from buffer and return
                    self._response_buffer.pop(i)
                    return response
            
            # Wait a bit before checking again
            await asyncio.sleep(0.01)
            
    async def _initialize_connection(self):
        """Send initialize request to establish MCP session"""
        self.request_id += 1
        init_id = self.request_id
        
        request = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "ultrathink-mcp-client",
                    "version": "1.0.1"
                }
            },
            "id": init_id
        }
        
        # Send request
        await self._send_raw(request)
        
        # Wait for response
        response = await self._wait_for_response(init_id)
        
        if "error" in response:
            raise Exception(f"Failed to initialize MCP connection: {response['error']}")
            
        self._initialized = True
        logger.info(f"MCP connection initialized: {response.get('result', {}).get('serverInfo', {})}")
        return response
        
    async def _send_raw(self, request: Dict[str, Any]):
        """Send raw JSON-RPC request"""
        request_str = json.dumps(request) + '\n'
        logger.debug(f"Sending: {request}")
        self._writer.write(request_str.encode())
        await self._writer.drain()
        
    async def disconnect(self):
        """Close MCP connection"""
        if self.process:
            self.process.terminate()
            await self.process.wait()
            logger.info("MCP connection closed")
            
    async def _send_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send JSON-RPC request and wait for response"""
        if not self._initialized and method != "initialize":
            raise Exception("MCP connection not initialized")
            
        self.request_id += 1
        current_id = self.request_id
        
        request = {
            "jsonrpc": "2.0",
            "method": method,
            "id": current_id
        }
        
        if params:
            request["params"] = params
            
        # Send request
        await self._send_raw(request)
        
        # Wait for response
        response = await self._wait_for_response(current_id)
        
        # Check for errors
        if "error" in response:
            logger.error(f"MCP error: {response['error']}")
            
        return response
        
    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available UltraThink tools"""
        response = await self._send_request("tools/list")
        return response.get("result", {}).get("tools", [])
        
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a specific UltraThink tool"""
        response = await self._send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments
        })
        
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
        
    async def sequence(self, thought: str, context: Optional[str] = None) -> Dict[str, Any]:
        """Add a sequential thought"""
        return await self.call_tool("ultrathink_sequence", {
            "thought": thought,
            "context": context,
            "project": self.project
        })
        
    async def sync_graphiti(self) -> Dict[str, Any]:
        """Sync with Graphiti knowledge graph"""
        return await self.call_tool("ultrathink_graphiti_sync", {
            "project": self.project
        })


# Test function with detailed debugging
async def test_ultrathink_mcp_fixed():
    """Test the fixed UltraThink MCP client"""
    print("Testing Fixed UltraThink MCP Client...")
    
    client = UltraThinkMCPClient(project="test")
    
    try:
        # Connect
        await client.connect()
        print("✓ Connected to UltraThink MCP")
        
        # Small delay to ensure initialization completes
        await asyncio.sleep(0.5)
        
        # List tools
        print("\nListing tools...")
        tools = await client.list_tools()
        print(f"✓ Available tools: {len(tools)}")
        for tool in tools:
            print(f"  - {tool['name']}: {tool.get('description', 'No description')}")
            
        # Test memory storage
        print("\nTesting memory storage...")
        try:
            result = await client.remember("Test memory from fixed MCP client", priority="high")
            print(f"✓ Stored memory: {result}")
        except Exception as e:
            print(f"✗ Memory storage failed: {e}")
            
        # Test memory retrieval
        print("\nTesting memory retrieval...")
        try:
            memories = await client.retrieve("test")
            print(f"✓ Retrieved {len(memories)} memories")
        except Exception as e:
            print(f"✗ Memory retrieval failed: {e}")
            
    except Exception as e:
        print(f"✗ Error during test: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()
        print("\n✓ Disconnected")


# Alternative simple wrapper using goose chat
class SimpleGeminiWrapper:
    """Simple wrapper that uses goose chat instead of MCP protocol"""
    
    def __init__(self, gemini_api_key: str, project: str = "general"):
        self.project = project
        # In real implementation, this would use Gemini API
        # For now, it's a placeholder showing the concept
        
    async def chat(self, message: str) -> str:
        """Chat using goose as intermediary"""
        # This would run: goose chat --project zgdk "message"
        # And parse the response
        process = await asyncio.create_subprocess_exec(
            'goose', 'chat', '--project', self.project,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Send message
        process.stdin.write(f"{message}\n".encode())
        await process.stdin.drain()
        
        # Read response (simplified - real implementation would be more robust)
        response = await process.stdout.read(1024)
        
        process.terminate()
        await process.wait()
        
        return response.decode()


if __name__ == "__main__":
    # Run the fixed test
    asyncio.run(test_ultrathink_mcp_fixed())