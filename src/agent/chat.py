"""Shared chat-loop helpers for the agent scripts."""

import json

from langchain_core.messages import AIMessage, ToolMessage


async def stream_answer(agent, prompt: str) -> None:
    """Run one prompt through the agent, printing text and tool activity.

    Dispatches on message type rather than graph node names (create_agent's
    nodes are "model"/"tools"), so this works across agent implementations.
    Agent text is printed as it arrives; tool calls and their (truncated)
    results are printed inline so the reasoning loop stays visible.
    """
    print("\nAgent: ", end="", flush=True)
    async for event in agent.astream({"messages": [("user", prompt)]}):
        for payload in event.values():
            message = payload["messages"][-1]
            if isinstance(message, AIMessage):
                if message.content:
                    print(message.content, end="", flush=True)
                for call in message.tool_calls:
                    print(f"\n  [tool: {call['name']}({json.dumps(call['args'])})]", flush=True)
            elif isinstance(message, ToolMessage):
                content = message.content
                if isinstance(content, list):
                    content = " ".join(str(part) for part in content)
                print(f"\n  [tool result: {str(content)[:200]}]", flush=True)
    print()
