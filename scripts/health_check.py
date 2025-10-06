#!/usr/bin/env python3
"""
Robust health check script for messaging-web container
"""
import sys
import urllib.request
import urllib.error
import json
import socket

def check_health():
    """Check if the web service is healthy"""
    try:
        # Set a shorter timeout and handle errors gracefully
        request = urllib.request.Request('http://localhost:8000/health')
        
        with urllib.request.urlopen(request, timeout=3) as response:
            if response.status == 200:
                try:
                    content = response.read().decode()
                    data = json.loads(content)
                    if data.get('status') == 'healthy':
                        return True
                except (json.JSONDecodeError, KeyError) as e:
                    # Even if JSON parsing fails, 200 status means service is up
                    print(f"JSON parse error but got 200: {e}", file=sys.stderr)
                    return True
            else:
                print(f"Got HTTP {response.status}", file=sys.stderr)
                return False
            
    except (urllib.error.URLError, socket.timeout, ConnectionRefusedError) as e:
        # Service not responding
        print(f"Connection error: {e}", file=sys.stderr)
        return False
    except Exception as e:
        # Any other error
        print(f"Unexpected error: {e}", file=sys.stderr)
        return False

if __name__ == "__main__":
    result = check_health()
    print(f"Health check result: {result}", file=sys.stderr)
    sys.exit(0 if result else 1)