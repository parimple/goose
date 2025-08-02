#!/usr/bin/env python3
"""
MCP Protocol Debugger
Helps diagnose MCP communication issues
"""

import json
import subprocess
import asyncio
import sys

async def debug_mcp_communication():
    """Debug MCP communication step by step"""
    print("=== MCP Protocol Debugger ===\n")
    
    # Start MCP server
    print("1. Starting goose mcp ultrathink...")
    process = await asyncio.create_subprocess_exec(
        'goose', 'mcp', 'ultrathink',
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    # Function to send and receive
    async def send_and_receive(request, description):
        print(f"\n{description}")
        print(f"Sending: {json.dumps(request)}")
        
        # Send
        process.stdin.write((json.dumps(request) + '\n').encode())
        await process.stdin.drain()
        
        # Read with timeout
        try:
            response_data = await asyncio.wait_for(
                process.stdout.readline(),
                timeout=2.0
            )
            response = json.loads(response_data.decode())
            print(f"Received: {json.dumps(response, indent=2)}")
            return response
        except asyncio.TimeoutError:
            print("TIMEOUT - No response received")
            return None
        except json.JSONDecodeError as e:
            print(f"JSON Error: {e}")
            print(f"Raw data: {response_data.decode()}")
            return None
    
    # Test 1: Initialize
    init_response = await send_and_receive({
        "jsonrpc": "2.0",
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "debugger",
                "version": "1.0"
            }
        },
        "id": 1
    }, "Test 1: Initialize")
    
    if not init_response:
        print("\n✗ Initialize failed")
        process.terminate()
        return
    
    print("\n✓ Initialize successful")
    
    # Small delay
    await asyncio.sleep(0.1)
    
    # Test 2: List tools
    tools_response = await send_and_receive({
        "jsonrpc": "2.0",
        "method": "tools/list",
        "id": 2
    }, "Test 2: List tools")
    
    if tools_response and "result" in tools_response:
        print(f"\n✓ Tools list successful: {len(tools_response['result'].get('tools', []))} tools")
    else:
        print("\n✗ Tools list failed")
        
        # Try alternative format
        print("\nTrying alternative format...")
        alt_response = await send_and_receive({
            "jsonrpc": "2.0",
            "method": "tools/list",
            "params": {},
            "id": 3
        }, "Test 2b: List tools with empty params")
    
    # Test 3: Check for any extra output
    print("\nChecking for additional output...")
    try:
        extra = await asyncio.wait_for(process.stdout.read(100), timeout=0.5)
        if extra:
            print(f"Extra data found: {extra.decode()}")
    except asyncio.TimeoutError:
        print("No extra data (good)")
    
    # Clean up
    process.terminate()
    await process.wait()
    print("\n=== Debug complete ===")


async def test_other_mcp_servers():
    """Test if other MCP servers have the same issue"""
    print("\n=== Testing other MCP servers ===\n")
    
    servers = ["memory", "developer", "tutorial"]
    
    for server in servers:
        print(f"\nTesting {server}...")
        
        try:
            process = await asyncio.create_subprocess_exec(
                'goose', 'mcp', server,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Send initialize
            init_req = {
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0"}
                },
                "id": 1
            }
            
            process.stdin.write((json.dumps(init_req) + '\n').encode())
            await process.stdin.drain()
            
            # Read response
            response = await asyncio.wait_for(process.stdout.readline(), timeout=2.0)
            init_result = json.loads(response.decode())
            
            if "result" in init_result:
                print(f"  ✓ Initialize OK")
                
                # Try tools/list
                tools_req = {
                    "jsonrpc": "2.0",
                    "method": "tools/list",
                    "id": 2
                }
                
                process.stdin.write((json.dumps(tools_req) + '\n').encode())
                await process.stdin.drain()
                
                response = await asyncio.wait_for(process.stdout.readline(), timeout=2.0)
                tools_result = json.loads(response.decode())
                
                if "result" in tools_result:
                    print(f"  ✓ Tools/list OK - {len(tools_result['result'].get('tools', []))} tools")
                else:
                    print(f"  ✗ Tools/list failed: {tools_result}")
            else:
                print(f"  ✗ Initialize failed")
                
            process.terminate()
            await process.wait()
            
        except Exception as e:
            print(f"  ✗ Error: {e}")


if __name__ == "__main__":
    print("Choose test:")
    print("1. Debug UltraThink MCP communication")
    print("2. Test other MCP servers")
    print("3. Run both tests")
    
    choice = input("\nEnter choice (1-3): ").strip()
    
    if choice == "1":
        asyncio.run(debug_mcp_communication())
    elif choice == "2":
        asyncio.run(test_other_mcp_servers())
    elif choice == "3":
        asyncio.run(debug_mcp_communication())
        asyncio.run(test_other_mcp_servers())
    else:
        print("Invalid choice")