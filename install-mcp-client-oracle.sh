#!/bin/bash
# Install UltraThink MCP Client on Oracle

set -e

echo "=== Installing UltraThink MCP Client on Oracle ==="

# 1. Copy MCP client
echo "1. Installing MCP client..."
sudo cp ultrathink_mcp_client.py /usr/local/bin/ultrathink-mcp-client
sudo chmod +x /usr/local/bin/ultrathink-mcp-client

# 2. Create wrapper for Gemini
echo "2. Creating Gemini wrapper..."
cat << 'EOF' > /usr/local/bin/gemini-ultrathink
#!/usr/bin/env python3
import os
import sys
import asyncio
from ultrathink_mcp_client import GeminiUltraThink

async def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not set")
        sys.exit(1)
        
    project = os.environ.get("GOOSE_PROJECT", "general")
    
    async with GeminiUltraThink(api_key, project) as gemini:
        if len(sys.argv) > 1:
            message = " ".join(sys.argv[1:])
            response = await gemini.chat(message)
            print(response)
        else:
            print("Interactive Gemini with UltraThink memory")
            print(f"Project: {project}")
            print("Type 'exit' to quit")
            
            while True:
                try:
                    message = input("\n> ")
                    if message.lower() == 'exit':
                        break
                    response = await gemini.chat(message)
                    print(f"\n{response}")
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
EOF

sudo chmod +x /usr/local/bin/gemini-ultrathink

# 3. Create wrapper for OpenAI
echo "3. Creating OpenAI wrapper..."
cat << 'EOF' > /usr/local/bin/openai-ultrathink
#!/usr/bin/env python3
import os
import sys
import asyncio
from ultrathink_mcp_client import OpenAIUltraThink

async def main():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY not set")
        sys.exit(1)
        
    project = os.environ.get("GOOSE_PROJECT", "general")
    
    async with OpenAIUltraThink(api_key, project) as openai:
        if len(sys.argv) > 1:
            message = " ".join(sys.argv[1:])
            response = await openai.chat(message)
            print(response)
        else:
            print("Interactive OpenAI with UltraThink memory")
            print(f"Project: {project}")
            print("Type 'exit' to quit")
            
            while True:
                try:
                    message = input("\n> ")
                    if message.lower() == 'exit':
                        break
                    response = await openai.chat(message)
                    print(f"\n{response}")
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
EOF

sudo chmod +x /usr/local/bin/openai-ultrathink

# 4. Create test script
echo "4. Creating test script..."
cat << 'EOF' > ~/test-mcp-clients.sh
#!/bin/bash
echo "=== Testing UltraThink MCP Clients ==="

# Test direct MCP client
echo "1. Testing direct MCP client..."
python3 /usr/local/bin/ultrathink-mcp-client

# Test with environment
export GOOSE_PROJECT=test

echo ""
echo "2. Testing Gemini wrapper (needs GEMINI_API_KEY)..."
if [ ! -z "$GEMINI_API_KEY" ]; then
    gemini-ultrathink "Test message for Gemini"
else
    echo "   Skipped - GEMINI_API_KEY not set"
fi

echo ""
echo "3. Testing OpenAI wrapper (needs OPENAI_API_KEY)..."
if [ ! -z "$OPENAI_API_KEY" ]; then
    openai-ultrathink "Test message for OpenAI"
else
    echo "   Skipped - OPENAI_API_KEY not set"
fi

echo ""
echo "=== Test complete ==="
EOF

chmod +x ~/test-mcp-clients.sh

# 5. Install Python dependencies
echo "5. Installing Python dependencies..."
pip3 install --user google-generativeai openai asyncio

echo ""
echo "=== Installation complete! ==="
echo ""
echo "Usage:"
echo "  # Set API keys"
echo "  export GEMINI_API_KEY='your-key'"
echo "  export OPENAI_API_KEY='your-key'"
echo ""
echo "  # Use in specific project"
echo "  cd ~/Projects/zgdk"
echo "  gemini-ultrathink 'What Discord commands are implemented?'"
echo ""
echo "  # Interactive mode"
echo "  openai-ultrathink"
echo ""
echo "  # Test installation"
echo "  ~/test-mcp-clients.sh"