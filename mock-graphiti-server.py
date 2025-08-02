#!/usr/bin/env python3
"""
Mock Graphiti Server for UltraThink
Simple implementation for testing graph memory integration
"""

import json
import os
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
import logging

from aiohttp import web

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MockGraphitiServer:
    def __init__(self, data_dir: str = "~/.graphiti-data"):
        self.data_dir = Path(data_dir).expanduser()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.memories_file = self.data_dir / "memories.json"
        self.nodes_file = self.data_dir / "nodes.json"
        self.edges_file = self.data_dir / "edges.json"
        
        self._load_data()
        
    def _load_data(self):
        """Load existing data from files"""
        self.memories = self._load_json(self.memories_file, [])
        self.nodes = self._load_json(self.nodes_file, [])
        self.edges = self._load_json(self.edges_file, [])
        
    def _load_json(self, file_path: Path, default: Any) -> Any:
        """Load JSON file with default"""
        if file_path.exists():
            try:
                with open(file_path, 'r') as f:
                    return json.load(f)
            except:
                pass
        return default
        
    def _save_data(self):
        """Save data to files"""
        with open(self.memories_file, 'w') as f:
            json.dump(self.memories, f, indent=2)
        with open(self.nodes_file, 'w') as f:
            json.dump(self.nodes, f, indent=2)
        with open(self.edges_file, 'w') as f:
            json.dump(self.edges, f, indent=2)
            
    async def health(self, request):
        """Health check endpoint"""
        return web.json_response({
            "status": "healthy",
            "service": "mock-graphiti",
            "timestamp": datetime.now().isoformat(),
            "stats": {
                "memories": len(self.memories),
                "nodes": len(self.nodes),
                "edges": len(self.edges)
            }
        })
        
    async def create_memory(self, request):
        """Create a new memory"""
        data = await request.json()
        
        memory = {
            "id": f"mem-{len(self.memories)+1}",
            "content": data.get("content"),
            "project": data.get("project", "general"),
            "tags": data.get("tags", []),
            "timestamp": data.get("timestamp", datetime.now().isoformat()),
            "metadata": data.get("metadata", {})
        }
        
        self.memories.append(memory)
        
        # Create node for this memory
        node = {
            "id": memory["id"],
            "type": "memory",
            "project": memory["project"],
            "content": memory["content"],
            "created": memory["timestamp"]
        }
        self.nodes.append(node)
        
        # Create edges for tags
        for tag in memory["tags"]:
            edge = {
                "id": f"edge-{len(self.edges)+1}",
                "from": memory["id"],
                "to": f"tag-{tag}",
                "type": "has_tag"
            }
            self.edges.append(edge)
            
        self._save_data()
        
        logger.info(f"Created memory: {memory['id']} for project {memory['project']}")
        
        return web.json_response(memory)
        
    async def get_memories(self, request):
        """Get memories with optional filtering"""
        project = request.query.get('project')
        tag = request.query.get('tag')
        limit = int(request.query.get('limit', 100))
        
        filtered = self.memories
        
        if project:
            filtered = [m for m in filtered if m['project'] == project]
        if tag:
            filtered = [m for m in filtered if tag in m.get('tags', [])]
            
        return web.json_response({
            "memories": filtered[:limit],
            "total": len(filtered)
        })
        
    async def sync_memories(self, request):
        """Sync memories from UltraThink"""
        data = await request.json()
        
        synced = 0
        for memory_data in data.get("memories", []):
            # Check if memory already exists
            existing = next((m for m in self.memories 
                           if m.get("content") == memory_data.get("content")), None)
            
            if not existing:
                memory = {
                    "id": f"mem-{len(self.memories)+1}",
                    "content": memory_data.get("content"),
                    "project": memory_data.get("project", "general"),
                    "tags": memory_data.get("tags", []),
                    "timestamp": memory_data.get("timestamp", datetime.now().isoformat()),
                    "source": "ultrathink"
                }
                self.memories.append(memory)
                synced += 1
                
        self._save_data()
        
        logger.info(f"Synced {synced} new memories")
        
        return web.json_response({
            "synced": synced,
            "total_memories": len(self.memories)
        })
        
    async def query_graph(self, request):
        """Query the knowledge graph"""
        data = await request.json()
        query = data.get("query", "")
        project = data.get("project")
        
        # Simple keyword search
        results = []
        query_lower = query.lower()
        
        for memory in self.memories:
            if project and memory.get("project") != project:
                continue
                
            if query_lower in memory.get("content", "").lower():
                results.append(memory)
                
        # Find related nodes
        related_nodes = []
        for node in self.nodes:
            if query_lower in str(node.get("content", "")).lower():
                related_nodes.append(node)
                
        return web.json_response({
            "query": query,
            "memories": results[:10],
            "nodes": related_nodes[:10],
            "total_matches": len(results)
        })
        
    async def get_stats(self, request):
        """Get statistics about the graph"""
        stats = {
            "total_memories": len(self.memories),
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "projects": {},
            "tags": {}
        }
        
        # Count by project
        for memory in self.memories:
            project = memory.get("project", "general")
            stats["projects"][project] = stats["projects"].get(project, 0) + 1
            
            # Count tags
            for tag in memory.get("tags", []):
                stats["tags"][tag] = stats["tags"].get(tag, 0) + 1
                
        return web.json_response(stats)

async def create_app():
    """Create the web application"""
    server = MockGraphitiServer()
    
    app = web.Application()
    
    # Routes
    app.router.add_get('/health', server.health)
    app.router.add_post('/api/v1/memories', server.create_memory)
    app.router.add_get('/api/v1/memories', server.get_memories)
    app.router.add_post('/api/v1/sync', server.sync_memories)
    app.router.add_post('/api/v1/query', server.query_graph)
    app.router.add_get('/api/v1/stats', server.get_stats)
    
    # Root endpoint
    async def root(request):
        return web.json_response({
            "service": "Mock Graphiti Server",
            "version": "1.0.0",
            "endpoints": {
                "health": "/health",
                "memories": "/api/v1/memories",
                "sync": "/api/v1/sync",
                "query": "/api/v1/query",
                "stats": "/api/v1/stats"
            }
        })
    
    app.router.add_get('/', root)
    
    return app

if __name__ == "__main__":
    port = int(os.environ.get("GRAPHITI_PORT", "8123"))
    
    print(f"""
╔═══════════════════════════════════════════╗
║     Mock Graphiti Server for UltraThink   ║
╠═══════════════════════════════════════════╣
║  Knowledge Graph Memory Storage           ║
║                                           ║
║  Starting on: http://0.0.0.0:{port:<4}        ║
║  Data dir: ~/.graphiti-data              ║
║                                           ║
║  Endpoints:                               ║
║  - POST /api/v1/memories                  ║
║  - GET  /api/v1/memories                  ║
║  - POST /api/v1/sync                      ║
║  - POST /api/v1/query                     ║
║  - GET  /api/v1/stats                     ║
╚═══════════════════════════════════════════╝
    """)
    
    app = asyncio.get_event_loop().run_until_complete(create_app())
    web.run_app(app, host="0.0.0.0", port=port)