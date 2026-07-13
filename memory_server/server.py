"""MCP server exposing session-memory tools to Claude Code (stdio transport)."""

from datetime import datetime
from mcp.server.fastmcp import FastMCP
from storage import (
    get_client, get_collection, store_chunk, search_sessions, get_session_chunks,
)
from obsidian import create_session_note, append_to_session, append_summary

mcp = FastMCP("claude-memory")
client = get_client()
collection = get_collection(client)


@mcp.tool()
def memory_search(query: str, n_results: int = 5, project: str = "") -> str:
    """Search past Claude session history for relevant context.
    Use this at the start of a session or when the user references past work.

    Args:
        query: What to search for (semantic search)
        n_results: Number of results to return (default 5)
        project: Optional project filter (e.g. "MyApp", "backend")
    """
    hits = search_sessions(collection, query, n_results, project if project else None)
    if not hits:
        return "No relevant past sessions found."
    return "\n\n---\n\n".join(
        f"[{h['metadata'].get('chunk_type', 'unknown')}] "
        f"(score {h['score']:.2f}, project {h['metadata'].get('project', 'N/A')}, "
        f"date {h['metadata'].get('timestamp', 'N/A')[:10]})\n{h['text']}"
        for h in hits
    )


@mcp.tool()
def memory_save(text: str, session_id: str, chunk_type: str = "decision",
                project: str = "", tags: str = "") -> str:
    """Save a meaningful piece of information from this session to memory.
    Only save decisions, learnings, architectural choices, preferences, and outcomes.
    Do NOT save trivial exchanges like "yes", "ok", "looks good".

    Args:
        text: The information to remember
        session_id: Current session identifier (YYYY-MM-DD-topic format)
        chunk_type: "decision" | "learning" | "architecture" | "preference" | "outcome"
        project: Which project this relates to
        tags: Comma-separated tags
    """
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    return "Saved to memory: " + store_chunk(
        collection, text, session_id, chunk_type, project, tag_list)


@mcp.tool()
def session_start(project: str = "", topic: str = "") -> str:
    """Start a new session log in Obsidian. Call at the beginning of each session.

    Args:
        project: The project being worked on
        topic: Brief description of the session topic
    """
    session_id = datetime.now().strftime("%Y-%m-%d") + (
        f"-{topic.lower().replace(' ', '-')[:30]}" if topic else "")
    path = create_session_note(session_id, project, topic)
    return f"Session started: {session_id}\nLog: {path}"


@mcp.tool()
def session_log(session_id: str, role: str, content: str, actions: str = "") -> str:
    """Append a message exchange to the running session log in Obsidian.

    Args:
        session_id: The current session ID
        role: "user" or "assistant"
        content: The message content (summarized if long)
        actions: Actions taken (files changed, commits, etc.)
    """
    append_to_session(session_id, role, content, actions)
    return f"Logged {role} message to {session_id}"


@mcp.tool()
def session_end(session_id: str, summary: str, decisions: str = "") -> str:
    """End a session. Saves summary to Obsidian and key decisions to the vector store.

    Args:
        session_id: The current session ID
        summary: Brief summary of what was accomplished
        decisions: Pipe-separated key decisions (e.g. "chose Postgres|dropped the cron job")
    """
    decision_list = [d.strip() for d in decisions.split("|") if d.strip()]
    append_summary(session_id, summary, decision_list)
    if summary:
        store_chunk(collection, summary, session_id, "outcome", tags=["session-summary"])
    for d in decision_list:
        store_chunk(collection, d, session_id, "decision")
    return f"Session {session_id} ended and saved."


@mcp.tool()
def memory_get_session(session_id: str) -> str:
    """Get all stored chunks from a specific past session.

    Args:
        session_id: The session ID to retrieve
    """
    chunks = get_session_chunks(collection, session_id)
    if not chunks:
        return f"No stored chunks for session {session_id}"
    return "\n\n".join(
        f"[{c['metadata'].get('chunk_type', '')}] {c['text']}" for c in chunks)


if __name__ == "__main__":
    mcp.run(transport="stdio")
