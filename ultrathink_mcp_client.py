#!/usr/bin/env python3
"""
UltraThink MCP Client
Allows non-MCP AI systems (Gemini, OpenAI) to access UltraThink via MCP protocol
"""

import subprocess
import json
import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)

class UltraThinkMCPClient:
    """MCP Client for UltraThink - enables Gemini/OpenAI to use shared memory"""
    
    def __init__(self, project: str = "general"):
        self.process = None
        self.project = project
        self.request_id = 0
        self._reader = None
        self._writer = None
        
    async def connect(self):
        """Start goose mcp ultrathink process and establish communication"""
        logger.info(f"Starting UltraThink MCP connection for project: {self.project}")
        
        # Set environment for project context
        env = {
            "GOOSE_PROJECT": self.project,
            "MEMORY_DIR": f"/home/ubuntu/.goose/memory/{self.project}"
        }
        
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
        response = await self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "ultrathink-mcp-client",
                "version": "1.0.0"
            }
        })
        
        if "error" in response:
            raise Exception(f"Failed to initialize MCP connection: {response['error']}")
            
        logger.info("MCP connection initialized successfully")
        return response
        
    async def disconnect(self):
        """Close MCP connection"""
        if self.process:
            self.process.terminate()
            await self.process.wait()
            logger.info("MCP connection closed")
            
    async def _send_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send JSON-RPC request and wait for response"""
        self.request_id += 1
        
        request = {
            "jsonrpc": "2.0",
            "method": method,
            "id": self.request_id
        }
        
        if params:
            request["params"] = params
            
        # Send request
        request_str = json.dumps(request) + '\n'
        self._writer.write(request_str.encode())
        await self._writer.drain()
        
        # Read response
        response_data = await self._reader.readline()
        if not response_data:
            raise Exception("No response from MCP server")
            
        response = json.loads(response_data.decode())
        
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


# Example integrations

class GeminiUltraThink:
    """Gemini integration with UltraThink memory"""
    
    def __init__(self, gemini_api_key: str, project: str = "general"):
        import google.generativeai as genai
        genai.configure(api_key=gemini_api_key)
        self.model = genai.GenerativeModel('gemini-pro')
        self.mcp_client = UltraThinkMCPClient(project)
        self.project = project
        
    async def __aenter__(self):
        await self.mcp_client.connect()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.mcp_client.disconnect()
        
    async def chat(self, message: str, remember_response: bool = True) -> str:
        """Chat with Gemini using UltraThink memory context"""
        # Retrieve relevant memories
        memories = await self.mcp_client.retrieve(message, limit=5)
        
        # Build context prompt
        context_parts = [f"Project: {self.project}"]
        
        if memories:
            context_parts.append("\nRelevant memories:")
            for mem in memories:
                context_parts.append(f"- {mem['content']}")
                
        context = "\n".join(context_parts)
        
        # Generate response with context
        full_prompt = f"{context}\n\nUser: {message}\n\nAssistant:"
        response = self.model.generate_content(full_prompt)
        
        # Store important information
        if remember_response and any(keyword in message.lower() 
                                    for keyword in ["remember", "note", "important"]):
            await self.mcp_client.remember(
                f"User asked: {message}\nResponse: {response.text}",
                priority="high"
            )
            
        return response.text


class OpenAIUltraThink:
    """OpenAI integration with UltraThink memory"""
    
    def __init__(self, openai_api_key: str, project: str = "general", 
                 model: str = "gpt-4"):
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(api_key=openai_api_key)
        self.model = model
        self.mcp_client = UltraThinkMCPClient(project)
        self.project = project
        
    async def __aenter__(self):
        await self.mcp_client.connect()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.mcp_client.disconnect()
        
    async def chat(self, message: str, remember_response: bool = True) -> str:
        """Chat with OpenAI using UltraThink memory context"""
        # Retrieve relevant memories
        memories = await self.mcp_client.retrieve(message, limit=5)
        
        # Build messages array
        messages = [
            {
                "role": "system",
                "content": f"You have access to project '{self.project}' memories via UltraThink."
            }
        ]
        
        # Add memories as system context
        if memories:
            memory_content = "Relevant memories:\n"
            for mem in memories:
                memory_content += f"- {mem['content']}\n"
            messages.append({"role": "system", "content": memory_content})
            
        messages.append({"role": "user", "content": message})
        
        # Get response
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages
        )
        
        response_text = response.choices[0].message.content
        
        # Store important information
        if remember_response and any(keyword in message.lower() 
                                    for keyword in ["remember", "note", "important"]):
            await self.mcp_client.remember(
                f"User asked: {message}\nResponse: {response_text}",
                priority="high"
            )
            
        return response_text


# Test script
async def test_ultrathink_mcp():
    """Test UltraThink MCP client"""
    print("Testing UltraThink MCP Client...")
    
    client = UltraThinkMCPClient(project="test")
    
    try:
        # Connect
        await client.connect()
        print("✓ Connected to UltraThink MCP")
        
        # List tools
        tools = await client.list_tools()
        print(f"✓ Available tools: {len(tools)}")
        for tool in tools:
            print(f"  - {tool['name']}: {tool['description']}")
            
        # Store a memory
        result = await client.remember("Test memory from MCP client", priority="high")
        print(f"✓ Stored memory: {result}")
        
        # Retrieve memories
        memories = await client.retrieve("test")
        print(f"✓ Retrieved {len(memories)} memories")
        
        # Sequential thought
        thought = await client.sequence("Testing sequential thinking via MCP")
        print(f"✓ Added sequential thought: {thought}")
        
    finally:
        await client.disconnect()
        print("✓ Disconnected")


if __name__ == "__main__":
    # Run test
    asyncio.run(test_ultrathink_mcp())
    
    # Example usage with Gemini
    print("\nExample: Using with Gemini")
    print("""
    async with GeminiUltraThink("your-api-key", project="zgdk") as gemini:
        response = await gemini.chat("What do you know about Discord bots?")
        print(response)
    """)
    
    # Example usage with OpenAI
    print("\nExample: Using with OpenAI")
    print("""
    async with OpenAIUltraThink("your-api-key", project="zgdk") as openai:
        response = await openai.chat("Help me with a Discord bot feature")
        print(response)
    """)