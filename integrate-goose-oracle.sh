#!/bin/bash
# Script to integrate Goose with existing Oracle MCP infrastructure

set -e

echo "=== Integrating Goose with Oracle MCP Pool Manager ==="

# 1. Update MCP Pool Manager to include Goose
echo "1. Updating MCP Pool Manager configuration..."
cat << 'EOF' > update_mcp_pool.py
#!/usr/bin/env python3
import json
import sys
sys.path.append('/home/ubuntu/.claude/scripts')

# Read existing pool manager
with open('/home/ubuntu/.claude/scripts/ultrathink_mcp_pool_manager.py', 'r') as f:
    content = f.read()

# Add Goose server definition
goose_server = '''
            "goose-ultrathink": {
                "command": ["goose", "mcp", "ultrathink"],
                "port": 8017,
                "type": "goose",
                "description": "UltraThink enhanced memory with Graphiti",
                "args": [],
                "env": {
                    "GRAPHITI_ENDPOINT": "http://localhost:8123",
                    "MEMORY_DIR": "/home/ubuntu/.goose/memory"
                }
            },
            "cognee": {
                "command": ["uv", "--directory", "/home/ubuntu/Development/MCP-Servers/cognee-mcp", "run", "python", "src/server.py"],
                "port": 8018,
                "type": "python",
                "description": "Cognee knowledge graph",
                "args": [],
                "env": {
                    "LLM_API_KEY": os.environ.get("OPENAI_API_KEY", ""),
                    "EMBEDDING_API_KEY": os.environ.get("OPENAI_API_KEY", "")
                }
            }'''

# Insert before closing brace of mcp_servers
if '"playwright"' in content and goose_server not in content:
    content = content.replace(
        '            }\n        }',
        '            },\n' + goose_server + '\n        }'
    )

# Write updated file
with open('/home/ubuntu/.claude/scripts/ultrathink_mcp_pool_manager_updated.py', 'w') as f:
    f.write(content)

print("Updated MCP pool manager configuration")
EOF

python3 update_mcp_pool.py

# 2. Create Goose wrapper script
echo "2. Creating Goose wrapper script..."
cat << 'EOF' > /home/ubuntu/Development/Tools/bin/goose-wrapper.sh
#!/bin/bash
# Goose wrapper for MCP integration

source /home/ubuntu/.cargo/env
export GOOSE_CONFIG=/home/ubuntu/.goose/config.yaml

# Set project context based on current directory
CURRENT_DIR=$(pwd)
if [[ "$CURRENT_DIR" == *"/zgdk"* ]]; then
    export GOOSE_PROJECT="zgdk"
elif [[ "$CURRENT_DIR" == *"/zagadka"* ]]; then
    export GOOSE_PROJECT="zagadka"
elif [[ "$CURRENT_DIR" == *"/BohtPY"* ]] || [[ "$CURRENT_DIR" == *"/boht"* ]]; then
    export GOOSE_PROJECT="boht"
fi

exec /usr/local/bin/goose "$@"
EOF

chmod +x /home/ubuntu/Development/Tools/bin/goose-wrapper.sh

# 3. Create Goose config directory and copy configuration
echo "3. Setting up Goose configuration..."
mkdir -p /home/ubuntu/.goose/logs
cp oracle-goose-config.yaml /home/ubuntu/.goose/config.yaml

# 4. Create systemd service for Goose (optional)
echo "4. Creating systemd service..."
cat << 'EOF' > /home/ubuntu/.config/systemd/user/goose-ultrathink.service
[Unit]
Description=Goose UltraThink Service
After=network.target

[Service]
Type=simple
ExecStart=/home/ubuntu/Development/Tools/bin/goose-wrapper.sh serve
Restart=on-failure
Environment="HOME=/home/ubuntu"
Environment="PATH=/home/ubuntu/.cargo/bin:/usr/local/bin:/usr/bin:/bin"

[Install]
WantedBy=default.target
EOF

# 5. Create integration test script
echo "5. Creating integration test script..."
cat << 'EOF' > /home/ubuntu/test-goose-integration.sh
#!/bin/bash
echo "Testing Goose integration..."

# Test 1: Check if Goose is installed
if command -v goose &> /dev/null; then
    echo "✓ Goose is installed"
    goose --version
else
    echo "✗ Goose is not installed"
    exit 1
fi

# Test 2: Check MCP pool manager
if pgrep -f "ultrathink_mcp_pool_manager.py" > /dev/null; then
    echo "✓ MCP pool manager is running"
else
    echo "✗ MCP pool manager is not running"
fi

# Test 3: Test Goose MCP server
echo "Testing UltraThink MCP server..."
timeout 5 goose mcp ultrathink &
GOOSE_PID=$!
sleep 2
if ps -p $GOOSE_PID > /dev/null; then
    echo "✓ Goose MCP server started successfully"
    kill $GOOSE_PID
else
    echo "✗ Failed to start Goose MCP server"
fi

echo "Integration test complete!"
EOF

chmod +x /home/ubuntu/test-goose-integration.sh

echo "=== Integration setup complete! ==="
echo "Next steps:"
echo "1. Wait for Goose build to complete"
echo "2. Copy this script to Oracle and run it"
echo "3. Restart MCP pool manager to include Goose"
echo "4. Test with: /home/ubuntu/test-goose-integration.sh"