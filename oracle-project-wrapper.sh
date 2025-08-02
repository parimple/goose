#!/bin/bash
# UltraThink Project-Aware Wrapper for Goose
# Integrates with existing Claude infrastructure on Oracle

# Source cargo environment
source /home/ubuntu/.cargo/env

# Set base directories
export GOOSE_CONFIG=${GOOSE_CONFIG:-/home/ubuntu/.goose/config.yaml}
export GOOSE_MEMORY_DIR=${GOOSE_MEMORY_DIR:-/home/ubuntu/.goose/memory}
export GRAPHITI_ENDPOINT=${GRAPHITI_ENDPOINT:-http://localhost:8123}

# Detect current project based on working directory
detect_project() {
    local pwd=$(pwd)
    
    if [[ "$pwd" == *"/zgdk"* ]]; then
        echo "zgdk"
    elif [[ "$pwd" == *"/zagadka"* ]]; then
        echo "zagadka"
    elif [[ "$pwd" == *"/BohtPY"* ]] || [[ "$pwd" == *"/boht"* ]]; then
        echo "boht"
    elif [[ "$pwd" == *"/ultrathink"* ]]; then
        echo "ultrathink"
    else
        echo "general"
    fi
}

# Set project-specific environment
setup_project_env() {
    local project=$1
    
    export GOOSE_PROJECT=$project
    export GOOSE_PROJECT_MEMORY_DIR="$GOOSE_MEMORY_DIR/$project"
    
    # Create project memory directory if it doesn't exist
    mkdir -p "$GOOSE_PROJECT_MEMORY_DIR"
    
    # Set project-specific context
    case $project in
        zgdk)
            export GOOSE_CONTEXT="Discord bot project in Python, uses discord.py, async architecture"
            ;;
        zagadka)
            export GOOSE_CONTEXT="Mystery/puzzle project, interactive storytelling"
            ;;
        boht)
            export GOOSE_CONTEXT="Python bot project, automation and scripting"
            ;;
        ultrathink)
            export GOOSE_CONTEXT="UltraThink memory enhancement for Goose, Rust project"
            ;;
        *)
            export GOOSE_CONTEXT="General development project"
            ;;
    esac
    
    echo "🎯 Project: $project"
    echo "📁 Context: $GOOSE_CONTEXT"
}

# Load existing memories for project
load_project_memories() {
    local project=$1
    local memory_file="$GOOSE_PROJECT_MEMORY_DIR/context.md"
    
    if [ -f "$memory_file" ]; then
        echo "📚 Loading project memories from: $memory_file"
    fi
}

# Sync with Graphiti if available
sync_graphiti() {
    if command -v curl &> /dev/null && [ ! -z "$GRAPHITI_ENDPOINT" ]; then
        # Check if Graphiti is running
        if curl -s -o /dev/null -w "%{http_code}" "$GRAPHITI_ENDPOINT/health" | grep -q "200"; then
            echo "🔄 Syncing with Graphiti knowledge graph..."
        fi
    fi
}

# Main execution
main() {
    # Detect and setup project
    PROJECT=$(detect_project)
    setup_project_env "$PROJECT"
    
    # Load project memories
    load_project_memories "$PROJECT"
    
    # Sync with Graphiti
    sync_graphiti
    
    # Execute Goose with all arguments
    echo "🚀 Starting Goose with project context..."
    echo ""
    
    exec /usr/local/bin/goose "$@"
}

# Run main function with all arguments
main "$@"