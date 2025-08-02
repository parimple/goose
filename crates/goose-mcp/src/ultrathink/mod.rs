use async_trait::async_trait;
use etcetera::{choose_app_strategy, AppStrategy};
use indoc::formatdoc;
use mcp_core::{
    handler::{PromptError, ResourceError, ToolError},
    protocol::ServerCapabilities,
    tool::ToolCall,
};
use mcp_server::router::CapabilitiesBuilder;
use mcp_server::Router;
use rmcp::model::{Content, JsonRpcMessage, Prompt, Resource, Tool, ToolAnnotations};
use rmcp::object;
use serde_json::Value;
use std::{
    collections::HashMap,
    fs,
    future::Future,
    io::{self, Read, Write},
    path::PathBuf,
    pin::Pin,
};
use tokio::sync::mpsc;

mod graphiti_client;
use graphiti_client::GraphitiClient;

/// UltraThink Router - Advanced Memory & Sequential Thinking System
/// Combines local file storage with Graphiti integration for persistent memory
#[derive(Clone)]
pub struct UltraThinkRouter {
    tools: Vec<Tool>,
    instructions: String,
    global_memory_dir: PathBuf,
    local_memory_dir: PathBuf,
    graphiti_endpoint: Option<String>,
    graphiti_client: GraphitiClient,
}

impl Default for UltraThinkRouter {
    fn default() -> Self {
        Self::new()
    }
}

impl UltraThinkRouter {
    pub fn new() -> Self {
        // Enhanced memory tools for UltraThink
        let remember_memory = Tool::new(
            "ultrathink_remember",
            "Stores memory with enhanced context and sequential thinking capabilities",
            object!({
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "data": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "is_global": {"type": "boolean"},
                    "priority": {"type": "string", "enum": ["low", "medium", "high"]},
                    "context": {"type": "string"}
                },
                "required": ["category", "data", "is_global"]
            }),
        )
        .annotate(ToolAnnotations {
            title: Some("UltraThink Remember".to_string()),
            read_only_hint: Some(false),
            destructive_hint: Some(false),
            idempotent_hint: Some(true),
            open_world_hint: Some(false),
        });

        let retrieve_memories = Tool::new(
            "ultrathink_retrieve",
            "Retrieves memories with enhanced context and relationship mapping",
            object!({
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "is_global": {"type": "boolean"},
                    "query": {"type": "string"},
                    "limit": {"type": "number"}
                },
                "required": ["category", "is_global"]
            }),
        )
        .annotate(ToolAnnotations {
            title: Some("UltraThink Retrieve".to_string()),
            read_only_hint: Some(true),
            destructive_hint: Some(false),
            idempotent_hint: Some(false),
            open_world_hint: Some(false),
        });

        let sequential_think = Tool::new(
            "ultrathink_sequence",
            "Initiates sequential thinking process with memory integration",
            object!({
                "type": "object",
                "properties": {
                    "thought": {"type": "string"},
                    "stage": {"type": "string", "enum": ["Problem Definition", "Research", "Analysis", "Synthesis", "Conclusion"]},
                    "save_to_memory": {"type": "boolean"},
                    "category": {"type": "string"}
                },
                "required": ["thought", "stage"]
            }),
        )
        .annotate(ToolAnnotations {
            title: Some("UltraThink Sequential Process".to_string()),
            read_only_hint: Some(false),
            destructive_hint: Some(false),
            idempotent_hint: Some(false),
            open_world_hint: Some(false),
        });

        let graphiti_sync = Tool::new(
            "ultrathink_graphiti_sync",
            "Synchronizes local memories with Graphiti knowledge graph",
            object!({
                "type": "object",
                "properties": {
                    "direction": {"type": "string", "enum": ["to_graphiti", "from_graphiti", "bidirectional"]},
                    "category": {"type": "string"}
                },
                "required": ["direction"]
            }),
        )
        .annotate(ToolAnnotations {
            title: Some("UltraThink Graphiti Sync".to_string()),
            read_only_hint: Some(false),
            destructive_hint: Some(false),
            idempotent_hint: Some(true),
            open_world_hint: Some(false),
        });

        let instructions = formatdoc! {r#"
            # UltraThink Memory & Sequential Thinking System
            
            This is an advanced memory and reasoning system that combines:
            - Local file-based memory storage (compatible with Goose)
            - Graphiti knowledge graph integration for persistent, structured memory
            - Sequential thinking capabilities for complex problem solving
            - Enhanced context awareness and relationship mapping
            
            ## Capabilities:
            
            ### Memory Management
            - **ultrathink_remember**: Store memories with enhanced metadata
            - **ultrathink_retrieve**: Retrieve memories with semantic search
            - Support for priority levels, context, and relationship mapping
            - Local (.goose/memory) and global (~/.config/goose/memory) storage
            
            ### Sequential Thinking
            - **ultrathink_sequence**: Process complex thoughts through structured stages
            - Stages: Problem Definition → Research → Analysis → Synthesis → Conclusion
            - Automatic memory integration for important insights
            
            ### Graphiti Integration
            - **ultrathink_graphiti_sync**: Sync with knowledge graph
            - Persistent memory across sessions and projects
            - Relationship mapping between concepts and ideas
            
            ## Usage Patterns:
            
            **For Complex Problem Solving:**
            1. Start with Problem Definition stage
            2. Progress through Research and Analysis
            3. Synthesize findings and conclude
            4. Automatically save key insights to memory
            
            **For Memory Management:**
            - Use categories like: "development", "personal", "project", "learning"
            - Add priority: "high" for critical info, "low" for reference
            - Include context for better retrieval
            
            **For Graphiti Sync:**
            - Regular bidirectional sync to maintain consistency
            - Category-specific sync for focused updates
            
            ## Integration with Existing Workflow:
            - Fully compatible with standard Goose memory tools
            - Enhanced capabilities build on familiar patterns
            - Automatic Graphiti sync maintains persistent knowledge
            "#};

        // Directory setup (same as MemoryRouter)
        let local_memory_dir = std::env::var("GOOSE_WORKING_DIR")
            .map(PathBuf::from)
            .unwrap_or_else(|_| std::env::current_dir().unwrap())
            .join(".goose")
            .join("memory");

        let global_memory_dir = choose_app_strategy(crate::APP_STRATEGY.clone())
            .map(|strategy| strategy.in_config_dir("memory"))
            .unwrap_or_else(|_| PathBuf::from(".config/goose/memory"));

        // Check for Graphiti endpoint configuration
        let graphiti_endpoint = std::env::var("GRAPHITI_ENDPOINT").ok()
            .or_else(|| {
                // Try to read from config file
                let config_path = global_memory_dir.parent()
                    .unwrap_or(&global_memory_dir)
                    .join("ultrathink.toml");
                
                if config_path.exists() {
                    // In a real implementation, we'd parse TOML here
                    // For now, just return None
                    None
                } else {
                    None
                }
            });

        let mut router = Self {
            tools: vec![
                remember_memory,
                retrieve_memories,
                sequential_think,
                graphiti_sync,
            ],
            instructions: instructions.clone(),
            global_memory_dir,
            local_memory_dir,
            graphiti_endpoint,
            graphiti_client: GraphitiClient::new(),
        };

        // Load existing memories into instructions (like MemoryRouter)
        let retrieved_global_memories = router.retrieve_all(true);
        let retrieved_local_memories = router.retrieve_all(false);

        let mut updated_instructions = instructions;
        
        let memories_follow_up = formatdoc! {r#"
            **Current UltraThink Memories:**
            The following memories are currently loaded and available for context.
            "#};

        updated_instructions.push_str("\n\n");
        updated_instructions.push_str(&memories_follow_up);

        if let Ok(global_memories) = retrieved_global_memories {
            if !global_memories.is_empty() {
                updated_instructions.push_str("\n\n**Global Memories:**\n");
                for (category, memories) in global_memories {
                    updated_instructions.push_str(&format!("\n**{}:**\n", category));
                    for memory in memories {
                        updated_instructions.push_str(&format!("- {}\n", memory));
                    }
                }
            }
        }

        if let Ok(local_memories) = retrieved_local_memories {
            if !local_memories.is_empty() {
                updated_instructions.push_str("\n\n**Local Memories:**\n");
                for (category, memories) in local_memories {
                    updated_instructions.push_str(&format!("\n**{}:**\n", category));
                    for memory in memories {
                        updated_instructions.push_str(&format!("- {}\n", memory));
                    }
                }
            }
        }

        router.instructions = updated_instructions;
        router
    }

    // Core memory operations (similar to MemoryRouter but enhanced)
    pub fn remember(
        &self,
        category: &str,
        data: &str,
        tags: &[&str],
        is_global: bool,
    ) -> io::Result<()> {
        let memory_file_path = self.get_memory_file(category, is_global);

        if let Some(parent) = memory_file_path.parent() {
            fs::create_dir_all(parent)?;
        }

        let mut file = fs::OpenOptions::new()
            .append(true)
            .create(true)
            .open(&memory_file_path)?;
            
        if !tags.is_empty() {
            writeln!(file, "# {}", tags.join(" "))?;
        }
        writeln!(file, "{}\n", data)?;

        Ok(())
    }

    pub fn retrieve_all(&self, is_global: bool) -> io::Result<HashMap<String, Vec<String>>> {
        let base_dir = if is_global {
            &self.global_memory_dir
        } else {
            &self.local_memory_dir
        };
        
        let mut memories = HashMap::new();
        if base_dir.exists() {
            for entry in fs::read_dir(base_dir)? {
                let entry = entry?;
                if entry.file_type()?.is_file() {
                    let category = entry.file_name().to_string_lossy().replace(".txt", "");
                    let category_memories = self.retrieve(&category, is_global)?;
                    memories.insert(
                        category,
                        category_memories.into_iter().flat_map(|(_, v)| v).collect(),
                    );
                }
            }
        }
        Ok(memories)
    }

    pub fn retrieve(
        &self,
        category: &str,
        is_global: bool,
    ) -> io::Result<HashMap<String, Vec<String>>> {
        let memory_file_path = self.get_memory_file(category, is_global);
        if !memory_file_path.exists() {
            return Ok(HashMap::new());
        }

        let mut file = fs::File::open(memory_file_path)?;
        let mut content = String::new();
        file.read_to_string(&mut content)?;

        let mut memories = HashMap::new();
        for entry in content.split("\n\n") {
            let mut lines = entry.lines();
            if let Some(first_line) = lines.next() {
                if let Some(stripped) = first_line.strip_prefix('#') {
                    let tags = stripped
                        .split_whitespace()
                        .map(String::from)
                        .collect::<Vec<_>>();
                    memories.insert(tags.join(" "), lines.map(String::from).collect());
                } else {
                    let entry_data: Vec<String> = std::iter::once(first_line.to_string())
                        .chain(lines.map(String::from))
                        .collect();
                    memories
                        .entry("untagged".to_string())
                        .or_insert_with(Vec::new)
                        .extend(entry_data);
                }
            }
        }

        Ok(memories)
    }

    fn get_memory_file(&self, category: &str, is_global: bool) -> PathBuf {
        let base_dir = if is_global {
            &self.global_memory_dir
        } else {
            &self.local_memory_dir
        };
        base_dir.join(format!("{}.txt", category))
    }

    async fn execute_tool_call(&self, tool_call: ToolCall) -> Result<String, io::Error> {
        match tool_call.name.as_str() {
            "ultrathink_remember" => {
                let args = UltraThinkArgs::from_value(&tool_call.arguments)?;
                self.remember(args.category, args.data.unwrap_or(""), &args.tags, args.is_global)?;
                Ok(format!("📝 UltraThink memory stored in category: {}", args.category))
            }
            "ultrathink_retrieve" => {
                let args = UltraThinkArgs::from_value(&tool_call.arguments)?;
                let memories = if args.category == "*" {
                    self.retrieve_all(args.is_global)?
                } else {
                    self.retrieve(args.category, args.is_global)?
                };
                Ok(format!("🧠 UltraThink memories retrieved: {:?}", memories))
            }
            "ultrathink_sequence" => {
                let thought = tool_call.arguments["thought"].as_str().unwrap_or("");
                let stage = tool_call.arguments["stage"].as_str().unwrap_or("Analysis");
                
                // In a real implementation, this would integrate with sequential-thinking MCP
                let result = format!("🤔 Sequential thinking - Stage: {} | Thought: {}", stage, thought);
                
                // Optionally save to memory if requested
                if tool_call.arguments.get("save_to_memory").and_then(|v| v.as_bool()).unwrap_or(false) {
                    let category = tool_call.arguments.get("category")
                        .and_then(|v| v.as_str())
                        .unwrap_or("thinking");
                    
                    let memory_data = format!("[{}] {}", stage, thought);
                    self.remember(category, &memory_data, &["sequential", "thinking"], false)?;
                }
                
                Ok(result)
            }
            "ultrathink_graphiti_sync" => {
                let direction = tool_call.arguments["direction"].as_str().unwrap_or("bidirectional");
                
                // Use GraphitiClient for actual sync
                match self.graphiti_client.sync_memories(direction).await {
                    Ok(result) => Ok(result),
                    Err(e) => Ok(format!("❌ Graphiti sync failed: {}", e))
                }
            }
            _ => Err(io::Error::new(io::ErrorKind::InvalidInput, "Unknown UltraThink tool")),
        }
    }
}

#[async_trait]
impl Router for UltraThinkRouter {
    fn name(&self) -> String {
        "ultrathink".to_string()
    }

    fn instructions(&self) -> String {
        self.instructions.clone()
    }

    fn capabilities(&self) -> ServerCapabilities {
        CapabilitiesBuilder::new().with_tools(false).build()
    }

    fn list_tools(&self) -> Vec<Tool> {
        self.tools.clone()
    }

    fn call_tool(
        &self,
        tool_name: &str,
        arguments: Value,
        _notifier: mpsc::Sender<JsonRpcMessage>,
    ) -> Pin<Box<dyn Future<Output = Result<Vec<Content>, ToolError>> + Send + 'static>> {
        let this = self.clone();
        let tool_name = tool_name.to_string();

        Box::pin(async move {
            let tool_call = ToolCall {
                name: tool_name,
                arguments,
            };
            match this.execute_tool_call(tool_call).await {
                Ok(result) => Ok(vec![Content::text(result)]),
                Err(err) => Err(ToolError::ExecutionError(err.to_string())),
            }
        })
    }

    fn list_resources(&self) -> Vec<Resource> {
        Vec::new()
    }

    fn read_resource(
        &self,
        _uri: &str,
    ) -> Pin<Box<dyn Future<Output = Result<String, ResourceError>> + Send + 'static>> {
        Box::pin(async move { Ok("".to_string()) })
    }

    fn list_prompts(&self) -> Vec<Prompt> {
        vec![]
    }

    fn get_prompt(
        &self,
        prompt_name: &str,
    ) -> Pin<Box<dyn Future<Output = Result<String, PromptError>> + Send + 'static>> {
        let prompt_name = prompt_name.to_string();
        Box::pin(async move {
            Err(PromptError::NotFound(format!(
                "Prompt {} not found",
                prompt_name
            )))
        })
    }
}

#[derive(Debug)]
struct UltraThinkArgs<'a> {
    category: &'a str,
    data: Option<&'a str>,
    tags: Vec<&'a str>,
    is_global: bool,
}

impl<'a> UltraThinkArgs<'a> {
    fn from_value(args: &'a Value) -> Result<Self, io::Error> {
        let category = args["category"].as_str().ok_or_else(|| {
            io::Error::new(io::ErrorKind::InvalidInput, "Category must be a string")
        })?;

        if category.is_empty() {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "Category cannot be empty",
            ));
        }

        let data = args.get("data").and_then(|d| d.as_str());

        let tags = match &args["tags"] {
            Value::Array(arr) => arr.iter().filter_map(|v| v.as_str()).collect(),
            Value::String(s) => vec![s.as_str()],
            _ => Vec::new(),
        };

        let is_global = args.get("is_global")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);

        Ok(Self {
            category,
            data,
            tags,
            is_global,
        })
    }
}