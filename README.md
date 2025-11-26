# MCP Server and Client with AMQP Transport

## Overview
This project creates a unique example of an MCP Server on AMQP transport. The client-server and server-tools connections are all made through a RabbitMQ message broker via AMQP. Every client creates a new queue to be consumed constantly by the MCP Server. The client is accessed through the chat UI along with the MCP Inspector features, which also communicate with the server through AMQP. A specific RabbitMQ package has been developed for this MCP project which can also be found here. 
### Testing
Testing environment requires RabbitMQ docker image along with queues, exchanges, services to be defined on RabbitMQ, a valid json configuration file (a test file is provided) and a pip environment.

### Contents
- MCP Server
- MCP Client
- Custom Made RabbitMQ Python Library for the AMQP MCP Project
- Custom MCP Inspector
- Chat UI
- Docker Image of the service


## MCP Server

**Main File:** `app.py`

The MCP server is started with `service_core/bootstrap.py` using the `bootstrap_mcp()` function. This MCP server is built on top of **FastMCP** and integrates with a custom RabbitMQ package designed specifically for this project.

### Architecture

**Initial Tool Registry:**
- register_tools_from_idep(), The tool registry function picks available tools from a pre-configured `.idep` (JSON) file
- These tools are loaded at startup to initialize the MCP server with available capabilities
- The registry creates distinct tools that wrap one of two generic functions

**Generic Tool Functions:**
1. **`external_function_call`**: Used for standard tool calls
   - Takes `tool_name` and `kwargs` as parameters
   - Routes calls to internal company servers via RabbitMQ

2. **`external_data_extract_call`**: Used for resource gathering from database tables
   - Takes `table_name` as a parameter plus additional `kwargs`
   - While strictly speaking a "tool" in MCP terms, it's specifically designed for extracting data from various tables within the servers. Therefore is used as a resource.

### Communication Flow

Since this is a RabbitMQ-based system:
- All tool calls are routed internally to the company's servers
- Both generic functions internally use the `rpc_call` function from the custom RabbitMQ library
- The `rpc_call` function makes RPC calls to internal servers and listens for responses
- This is the primary method for the MCP Server to interact with its tools (internal servers)



## MCP Client and MCP Inspector

**Main File:** `lg_agent.py`

The MCP Client is built with **LangGraph** and uses a generic tool function called `mcp_tool_call`.

### Transport Layer

- While this example uses HTTP for communication with the MCP Server, the server itself listens to RabbitMQ queues
- The server can work with and respond to both **HTTP** and **AMQP** transported messages
- The `rpc_call_mcp()` function is specifically used for sending RPC calls from the client to the MCP Server

### API Endpoints

The MCP Client exposes two endpoints via FastAPI:

1. **`/agent`**: Used for chatting by users
2. **`/mcp_proxy`**: Used by the MCP Inspector

The proxy endpoint is necessary because:
- MCP servers don't support CORS headers
- The proxy allows the MCP Inspector (running in a browser) to call tools directly



## Chat UI and MCP Inspector

**Location:** `agent_frontend/`

A simple Chat UI that allows users to:
- Chat with the MCP Client
- Use the MCP Inspector for direct tool and resource interactions

### Inspector Features

Similar to the official Anthropic MCP Inspector, this implementation includes:
- **Two tabs**: One for calling tools, one for calling resources
- **Structured and unstructured output viewing**: Results are displayed in an organized format
- **Auto-loading**: Upon launch, all tools and resources are automatically loaded into the inspector
- **Detailed metadata**: Each tool/resource shows descriptions, titles, and parameters

### User Experience

By having the Chat UI next to the MCP Inspector:
- Users can execute multiple tool calls directly without relying on the LLM
- No need to "persuade" the LLM to call specific tools
- No waiting for tool executions to finish before proceeding
- Immediate feedback and results from tool calls



## RabbitMQ Package for MCP Server

**Location:** `service_core/`

### Initialization

**`config.py`** sets up the initial system with user credentials.

**`bootstrap_mcp()`** is the main function that starts the MCP server:
- Starts all necessary threads
- Begins listening to RPC queues defined in the `.idep` file
- This design is intentional since the MCP server is expected to receive and respond to requests (server-side)

### Transport Configuration

Inside `bootstrap_mcp()`, the FastMCP `run` method is used with HTTP transport. However, this results in the MCP server listening to **both HTTP AND AMQP requests simultaneously**, providing flexibility in how clients connect.

### Service Role

Even though this package contains all functions for a full RabbitMQ setup (consumer, producer, RPC server, RPC consumer), **the MCP server always acts as an RPC consumer**. This is because:
- The MCP Server never initiates interactions
- It waits for requests and responds accordingly
- `start_rpc_consumer_mcp` is the specific function used for the MCP server to listen to requests from clients

### Message Handling

The `callback()` function defined inside `start_rpc_consumer_mcp` shows how the protocol behaves for different requests:

- **Note on message classification**: The implementation's classification of incoming messages doesn't perfectly match the standard MCP format due to company-specific requirements. However, **the results are exactly according to the MCP format**.
- **Customization**: The definition is quite customizable so a few word changes and the MCP server can easily become 100% compliant with the MCP format.

**Message Types:**
- `"command.call_tool"`: Triggers a tool call in the MCP Server
- `"command.read_resource_template"`: Triggers resource template reading

These commands call the previously mentioned tool wrappers that contain the generic functions. The generic functions then use the `rpc_call` function to send RPC requests to internal servers and wait for replies.

### Special Function: `rpc_call_mcp`

**`rpc_call_mcp`** is a non-generic, specific function that makes an RPC call to the MCP Server itself. This function is used by the client to call the server.

**Why it's separate:**
- It's separated from the generic `rpc_call` function for convenience
- Functionality is identical to `rpc_call`
- The difference is that `rpc_call_mcp` has the address definitions of the MCP server micro-service hardcoded, making client-side calls simpler
