# UltraThink Architecture Documentation

## Overview

UltraThink is an enhanced memory and knowledge management system that extends Goose with:
- Project-aware todo management across multiple AI agents (Claude, Gemini, OpenAI)
- Shared knowledge graph via Cognee MCP
- Integration with existing Oracle MCP pool manager
- Terminal-only access for iPad SSH compatibility

## Current Infrastructure

### Oracle Server
- **MCP Pool Manager**: Manages shared MCP servers on ports 8010-8016
- **Existing MCP Servers**:
  - Memory (8010): Standard memory management
  - Sequential-thinking (8011): Reasoning capabilities
  - Exa-search (8012): Web search
  - GitHub (8013): GitHub integration
  - Filesystem (8014): File operations
  - Firecrawl (8015): Web scraping
  - Playwright (8016): Browser automation

### Projects
- **zgdk**: Discord bot project
- **zagadka**: Mystery/puzzle project
- **BohtPY**: Python bot project

## UltraThink Components

### 1. UltraThinkRouter (Goose Extension)
Located in `crates/goose-mcp/src/ultrathink/mod.rs`

**Tools**:
- `ultrathink_remember`: Enhanced memory with priorities and context
- `ultrathink_retrieve`: Context-aware memory retrieval
- `ultrathink_sequence`: Sequential thinking integration
- `ultrathink_graphiti_sync`: Knowledge graph synchronization

### 2. Graphiti Client
Located in `crates/goose-mcp/src/ultrathink/graphiti_client.rs`

Provides integration with Graphiti knowledge graph for persistent memory storage.

### 3. MCP Pool Integration
- Goose runs as MCP server on port 8017
- Cognee runs on port 8018
- Managed by existing ultrathink_mcp_pool_manager.py

## Installation Steps

### Phase 1: Install Goose on Oracle
```bash
# Install Rust (if not installed)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y

# Install dependencies
sudo apt-get update
sudo apt-get install -y build-essential pkg-config libssl-dev

# Install newer protobuf (required for build)
cd /tmp
wget https://github.com/protocolbuffers/protobuf/releases/download/v21.12/protoc-21.12-linux-aarch_64.zip
sudo unzip -o protoc-21.12-linux-aarch_64.zip -d /usr/local

# Clone and build
cd ~/Projects
git clone https://github.com/parimple/goose.git ultrathink-goose
cd ultrathink-goose
cargo build --release

# Install binary
sudo cp target/release/goose /usr/local/bin/
```

### Phase 2: Configure Integration
```bash
# Run integration script
./integrate-goose-oracle.sh

# Update MCP pool manager
sudo systemctl restart ultrathink-mcp-pool-manager

# Test integration
./test-goose-integration.sh
```

## Configuration

### Goose Config (`~/.goose/config.yaml`)
```yaml
providers:
  - name: openai
    type: openai
    api_key: ${OPENAI_API_KEY}

extensions:
  - name: ultrathink
    type: mcp
    transport: stdio
    command: goose
    args: ["mcp", "ultrathink"]
    
  - name: cognee
    type: mcp
    transport: stdio
    command: uv
    args: ["--directory", "/path/to/cognee-mcp", "run", "python", "src/server.py"]
```

### Environment Variables
```bash
export OPENAI_API_KEY="your-key"
export GRAPHITI_ENDPOINT="http://localhost:8123"
export GOOSE_CONFIG="$HOME/.goose/config.yaml"
```

## Usage

### Terminal Commands
```bash
# Start Goose with project context
cd ~/Projects/zgdk
goose chat

# Direct MCP server usage
goose mcp ultrathink

# Query knowledge graph
goose query "show todos for zgdk project"
```

### Multi-Agent Access
All AI agents can access the shared knowledge graph via:
- Direct MCP connection to port 8017 (Goose)
- REST API endpoint (future implementation)
- Shared Cognee graph on port 8018

## Project Detection

The system automatically detects the current project based on:
1. Current working directory
2. SSH session environment
3. Manual override via `GOOSE_PROJECT` env var

## iPad Access

Everything works through terminal SSH:
```bash
# From iPad
ssh oracle
tmux attach -t main
goose chat
```

## Troubleshooting

### Build Issues
- Ensure protobuf >= 3.21 is installed
- Check Rust version: `rustc --version` (should be >= 1.70)
- For ARM64: use correct protobuf binary

### MCP Connection Issues
- Check pool manager: `ps aux | grep ultrathink_mcp`
- Verify ports: `netstat -tlnp | grep -E '801[0-9]'`
- Check logs: `tail -f ~/.claude/logs/mcp_pool_manager.log`

### Memory/Graph Issues
- Graphiti logs: `~/.graphiti-thought-queue/`
- Goose logs: `~/.goose/logs/goose.log`
- Memory files: `~/.goose/memory/`

## Next Steps

1. Complete Goose build on Oracle
2. Install Cognee MCP server
3. Configure Graphiti endpoint
4. Test multi-agent access
5. Create CLI tools for graph management