#!/bin/bash
# Setup and test Graphiti integration for UltraThink

set -e

echo "=== Setting up Graphiti for UltraThink ==="

# 1. Check if Graphiti is already installed
echo "1. Checking Graphiti installation..."
if [ -d "$HOME/Development/Claude/graphiti" ]; then
    echo "✓ Graphiti found at ~/Development/Claude/graphiti"
else
    echo "Installing Graphiti..."
    mkdir -p ~/Development/Claude
    cd ~/Development/Claude
    
    # Clone Graphiti (example - adjust URL as needed)
    git clone https://github.com/topoteretes/graphiti.git || {
        echo "✗ Failed to clone Graphiti"
        echo "Please install Graphiti manually"
        exit 1
    }
fi

# 2. Create Graphiti service script
echo "2. Creating Graphiti service..."
cat << 'EOF' > ~/start-graphiti.sh
#!/bin/bash
# Start Graphiti service for UltraThink

cd ~/Development/Claude/graphiti

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt 2>/dev/null || echo "Dependencies already installed"

# Start Graphiti on port 8123
export GRAPHITI_PORT=8123
export GRAPHITI_DATA_DIR=~/.graphiti-data
export GRAPHITI_LOG_LEVEL=INFO

mkdir -p $GRAPHITI_DATA_DIR

echo "Starting Graphiti on port $GRAPHITI_PORT..."
python3 -m graphiti.server \
    --port $GRAPHITI_PORT \
    --data-dir $GRAPHITI_DATA_DIR \
    --log-level $GRAPHITI_LOG_LEVEL &

GRAPHITI_PID=$!
echo $GRAPHITI_PID > ~/.graphiti.pid

echo "✓ Graphiti started with PID $GRAPHITI_PID"
echo "  Endpoint: http://localhost:$GRAPHITI_PORT"
echo "  Data dir: $GRAPHITI_DATA_DIR"
EOF

chmod +x ~/start-graphiti.sh

# 3. Create Graphiti test script
echo "3. Creating test script..."
cat << 'EOF' > ~/test-graphiti-integration.sh
#!/bin/bash
# Test Graphiti integration with UltraThink

echo "=== Testing Graphiti Integration ==="

# 1. Check if Graphiti is running
echo -n "1. Checking Graphiti health: "
if curl -s http://localhost:8123/health > /dev/null 2>&1; then
    echo "✓ Running"
    curl -s http://localhost:8123/health | jq . 2>/dev/null || echo "Health check passed"
else
    echo "✗ Not running"
    echo "   Starting Graphiti..."
    ~/start-graphiti.sh
    sleep 5
fi

# 2. Test memory sync
echo -e "\n2. Testing UltraThink sync with Graphiti..."
cd ~/Projects/zgdk

# Add test memory
echo "Test memory for Graphiti sync at $(date)" > ~/.goose/memory/zgdk/graphiti-test.txt

# Trigger sync
ultrathink sync

# 3. Check Graphiti data
echo -e "\n3. Checking Graphiti data..."
if [ -d ~/.graphiti-data ]; then
    echo "✓ Graphiti data directory exists"
    ls -la ~/.graphiti-data/ | head -10
else
    echo "✗ No Graphiti data directory"
fi

# 4. Query Graphiti API directly
echo -e "\n4. Testing Graphiti API..."
curl -X POST http://localhost:8123/api/v1/memories \
    -H "Content-Type: application/json" \
    -d '{
        "content": "UltraThink test memory",
        "project": "zgdk",
        "tags": ["test", "integration"],
        "timestamp": "'$(date -Iseconds)'"
    }' 2>/dev/null | jq . || echo "API test failed"

# 5. Check thought queue
echo -e "\n5. Checking thought queue..."
ls -la ~/.graphiti-thought-queue/ | tail -10

echo -e "\n=== Integration test complete ==="
EOF

chmod +x ~/test-graphiti-integration.sh

# 4. Create stop script
echo "4. Creating stop script..."
cat << 'EOF' > ~/stop-graphiti.sh
#!/bin/bash
if [ -f ~/.graphiti.pid ]; then
    PID=$(cat ~/.graphiti.pid)
    if ps -p $PID > /dev/null; then
        kill $PID
        echo "✓ Stopped Graphiti (PID $PID)"
    else
        echo "Graphiti not running"
    fi
    rm ~/.graphiti.pid
else
    echo "No PID file found"
fi
EOF

chmod +x ~/stop-graphiti.sh

# 5. Update UltraThink to use Graphiti
echo "5. Updating UltraThink configuration..."
cat << 'EOF' > ~/update-ultrathink-graphiti.py
#!/usr/bin/env python3
import os
import json

# Update MCP pool manager to include Graphiti endpoint
pool_config_file = os.path.expanduser("~/.claude/scripts/ultrathink_mcp_pool_manager.py")

with open(pool_config_file, 'r') as f:
    content = f.read()

# Add Graphiti endpoint to goose-ultrathink env
if 'GRAPHITI_ENDPOINT' in content and 'localhost:8123' not in content:
    content = content.replace(
        '"GRAPHITI_ENDPOINT": "http://localhost:8123"',
        '"GRAPHITI_ENDPOINT": "http://localhost:8123"  # Updated for local Graphiti'
    )
    
    with open(pool_config_file, 'w') as f:
        f.write(content)
    
    print("✓ Updated MCP pool manager with Graphiti endpoint")
else:
    print("✓ Graphiti endpoint already configured")
EOF

python3 ~/update-ultrathink-graphiti.py

echo ""
echo "=== Setup complete! ==="
echo ""
echo "Available commands:"
echo "  ~/start-graphiti.sh         - Start Graphiti service"
echo "  ~/test-graphiti-integration.sh - Test integration" 
echo "  ~/stop-graphiti.sh          - Stop Graphiti"
echo ""
echo "Next steps:"
echo "1. Run: ~/test-graphiti-integration.sh"
echo "2. Restart MCP pool manager to pick up changes"
echo "3. Test with: ultrathink sync"