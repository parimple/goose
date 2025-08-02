#!/usr/bin/env python3
"""
UltraThink CLI - Manage todos and knowledge across AI agents
Integrates with Goose, Claude, and other AI systems
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

class UltraThinkCLI:
    def __init__(self):
        self.base_dir = Path.home() / ".goose"
        self.memory_dir = self.base_dir / "memory"
        self.todos_file = self.base_dir / "todos.json"
        self.projects = ["zgdk", "zagadka", "boht", "general"]
        
    def list_todos(self, project: Optional[str] = None, status: Optional[str] = None):
        """List todos, optionally filtered by project or status"""
        todos = self._load_todos()
        
        # Filter by project
        if project:
            todos = [t for t in todos if t.get("project") == project]
            
        # Filter by status
        if status:
            todos = [t for t in todos if t.get("status") == status]
            
        # Display todos
        if not todos:
            print("No todos found matching criteria")
            return
            
        print(f"\n{'ID':<10} {'Project':<12} {'Status':<12} {'Priority':<10} {'Content'}")
        print("-" * 80)
        
        for todo in todos:
            print(f"{todo['id']:<10} {todo.get('project', 'general'):<12} "
                  f"{todo['status']:<12} {todo['priority']:<10} {todo['content'][:40]}...")
                  
    def add_todo(self, content: str, project: str = "general", priority: str = "medium"):
        """Add a new todo"""
        todos = self._load_todos()
        
        new_todo = {
            "id": f"todo-{len(todos)+1}",
            "content": content,
            "project": project,
            "status": "pending",
            "priority": priority,
            "created": datetime.now().isoformat(),
            "agent": "ultrathink-cli"
        }
        
        todos.append(new_todo)
        self._save_todos(todos)
        
        print(f"✅ Added todo: {new_todo['id']}")
        
    def update_todo(self, todo_id: str, status: Optional[str] = None, 
                   priority: Optional[str] = None):
        """Update todo status or priority"""
        todos = self._load_todos()
        
        for todo in todos:
            if todo["id"] == todo_id:
                if status:
                    todo["status"] = status
                if priority:
                    todo["priority"] = priority
                todo["updated"] = datetime.now().isoformat()
                
                self._save_todos(todos)
                print(f"✅ Updated todo: {todo_id}")
                return
                
        print(f"❌ Todo not found: {todo_id}")
        
    def list_memories(self, project: Optional[str] = None):
        """List memories for a project"""
        if project:
            memory_path = self.memory_dir / project
        else:
            memory_path = self.memory_dir
            
        if not memory_path.exists():
            print(f"No memories found for project: {project or 'all'}")
            return
            
        print(f"\n📚 Memories for: {project or 'all projects'}")
        print("-" * 50)
        
        for file in memory_path.rglob("*.txt"):
            rel_path = file.relative_to(self.memory_dir)
            print(f"\n📄 {rel_path}")
            with open(file, 'r') as f:
                content = f.read()
                if len(content) > 200:
                    content = content[:200] + "..."
                print(f"   {content}")
                
    def sync_graphiti(self):
        """Sync with Graphiti knowledge graph"""
        graphiti_endpoint = os.environ.get("GRAPHITI_ENDPOINT", "http://localhost:8123")
        
        print(f"🔄 Syncing with Graphiti at {graphiti_endpoint}")
        
        # TODO: Implement actual Graphiti sync
        # For now, just show what would be synced
        todos = self._load_todos()
        print(f"  - {len(todos)} todos to sync")
        
        memory_files = list(self.memory_dir.rglob("*.txt"))
        print(f"  - {len(memory_files)} memory files to sync")
        
    def project_stats(self):
        """Show statistics for all projects"""
        todos = self._load_todos()
        
        print("\n📊 Project Statistics")
        print("-" * 50)
        
        for project in self.projects:
            project_todos = [t for t in todos if t.get("project") == project]
            
            if project_todos:
                pending = len([t for t in project_todos if t["status"] == "pending"])
                in_progress = len([t for t in project_todos if t["status"] == "in_progress"])
                completed = len([t for t in project_todos if t["status"] == "completed"])
                
                print(f"\n🎯 {project}:")
                print(f"   Pending: {pending}")
                print(f"   In Progress: {in_progress}")
                print(f"   Completed: {completed}")
                print(f"   Total: {len(project_todos)}")
                
    def _load_todos(self) -> List[Dict]:
        """Load todos from JSON file"""
        if not self.todos_file.exists():
            return []
            
        try:
            with open(self.todos_file, 'r') as f:
                return json.load(f)
        except:
            return []
            
    def _save_todos(self, todos: List[Dict]):
        """Save todos to JSON file"""
        self.todos_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.todos_file, 'w') as f:
            json.dump(todos, f, indent=2)

def main():
    parser = argparse.ArgumentParser(description="UltraThink CLI - Manage todos and knowledge")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Todo commands
    todo_parser = subparsers.add_parser("todo", help="Manage todos")
    todo_subparsers = todo_parser.add_subparsers(dest="todo_command")
    
    # List todos
    list_parser = todo_subparsers.add_parser("list", help="List todos")
    list_parser.add_argument("-p", "--project", help="Filter by project")
    list_parser.add_argument("-s", "--status", help="Filter by status")
    
    # Add todo
    add_parser = todo_subparsers.add_parser("add", help="Add a todo")
    add_parser.add_argument("content", help="Todo content")
    add_parser.add_argument("-p", "--project", default="general", help="Project name")
    add_parser.add_argument("--priority", default="medium", 
                          choices=["low", "medium", "high"], help="Priority")
    
    # Update todo
    update_parser = todo_subparsers.add_parser("update", help="Update a todo")
    update_parser.add_argument("id", help="Todo ID")
    update_parser.add_argument("-s", "--status", 
                             choices=["pending", "in_progress", "completed"])
    update_parser.add_argument("--priority", choices=["low", "medium", "high"])
    
    # Memory commands
    memory_parser = subparsers.add_parser("memory", help="Manage memories")
    memory_parser.add_argument("-p", "--project", help="Filter by project")
    
    # Sync command
    sync_parser = subparsers.add_parser("sync", help="Sync with Graphiti")
    
    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Show project statistics")
    
    args = parser.parse_args()
    
    cli = UltraThinkCLI()
    
    if args.command == "todo":
        if args.todo_command == "list":
            cli.list_todos(args.project, args.status)
        elif args.todo_command == "add":
            cli.add_todo(args.content, args.project, args.priority)
        elif args.todo_command == "update":
            cli.update_todo(args.id, args.status, args.priority)
        else:
            todo_parser.print_help()
            
    elif args.command == "memory":
        cli.list_memories(args.project)
        
    elif args.command == "sync":
        cli.sync_graphiti()
        
    elif args.command == "stats":
        cli.project_stats()
        
    else:
        parser.print_help()

if __name__ == "__main__":
    main()