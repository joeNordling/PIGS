"""
Launch script for the Flip 7 multiplayer server.

Usage:
    python -m flip_7.network.launch_server          # play mode  (LAN IP, no reload)
    python -m flip_7.network.launch_server --dev    # dev mode   (localhost, auto-reload)
    python -m flip_7.network.launch_server --host 192.168.1.50  # override host

Players on the same network connect to:
    http://<displayed-ip>:<port>
"""

import argparse
import socket
import sys

import uvicorn


DEFAULT_PORT = 8765

# ANSI colour codes
_BLUE   = '\033[0;34m'
_GREEN  = '\033[0;32m'
_YELLOW = '\033[1;33m'
_RED    = '\033[0;31m'
_NC     = '\033[0m'


def get_lan_ip() -> str:
    """
    Return this machine's LAN IP address.

    Opens a temporary UDP socket toward an external host (no data is sent)
    to let the OS select the correct outbound interface, then reads the
    local address it chose.  Falls back to 127.0.0.1 if no network is available.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Flip 7 multiplayer server")
    parser.add_argument("--dev",  action="store_true", help="Development mode: bind to localhost, enable auto-reload")
    parser.add_argument("--host", default=None,        help="Override the bind address (default: auto-detected LAN IP)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Port (default: {DEFAULT_PORT})")
    args = parser.parse_args()

    if args.dev:
        host   = "127.0.0.1"
        reload = True
    else:
        host   = args.host or get_lan_ip()
        reload = False

    _print_banner(host, args.port, dev=args.dev)

    uvicorn.run(
        "flip_7.network.server:app",
        host=host,
        port=args.port,
        reload=reload,
        log_level="info",
    )


def _print_banner(host: str, port: int, dev: bool) -> None:
    print(f"\n{_BLUE}{'=' * 48}{_NC}")
    print(f"{_BLUE}🎴  Flip 7 Multiplayer Server{_NC}")
    print(f"{_BLUE}{'=' * 48}{_NC}\n")

    if dev:
        print(f"{_YELLOW}Mode: development (localhost only, auto-reload on){_NC}")
        print(f"{_GREEN}Open your browser at: http://{host}:{port}{_NC}")
    else:
        print(f"{_GREEN}Mode: play{_NC}")
        print(f"\n  Share this address with other players on your network:\n")
        print(f"  {_GREEN}http://{host}:{port}{_NC}\n")

        if host.startswith("127."):
            print(f"  {_YELLOW}Warning: could not detect a LAN IP — only this machine can connect.{_NC}")
            print(f"  {_YELLOW}Are you connected to a network? Use --host to override.{_NC}")

    print(f"\n{_YELLOW}Press Ctrl+C to stop the server{_NC}\n")


if __name__ == "__main__":
    main()