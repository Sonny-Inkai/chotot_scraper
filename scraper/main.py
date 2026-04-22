#!/usr/bin/env python3
"""
Chotot Crawler - Entry Point

Starts the FastAPI server that exposes /api/crawl, /api/crawl/stop,
and /ws/crawl-status endpoints.

Usage:
    python main.py                   # start on default port 8000
    python main.py --port 9000       # custom port
"""

import argparse
import uvicorn


def main():
    parser = argparse.ArgumentParser(description="Chotot Crawler API Server")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    args = parser.parse_args()

    uvicorn.run(
        "api:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
