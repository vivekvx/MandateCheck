"""MCP server exposing MandateCheck's deterministic payment gate as tools."""

from mandatecheck_mcp.server import main, server

__all__ = ["main", "server"]

__version__ = "0.1.0"
