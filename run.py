#!/usr/bin/env python3
"""
Startup script for DeathScent UI
"""

import subprocess
import sys
import os

def check_dependencies():
    """Check if required packages are installed"""
    try:
        import flask
        import bleak
        print("✓ All required dependencies are installed")
        return True
    except ImportError as e:
        print(f"✗ Missing dependency: {e}")
        print("Please run: pip install flask bleak")
        return False

def main():
    print("🌹 DeathScent UI Startup")
    print("=" * 30)
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Check if device is configured
    print("Device Configuration:")
    print(f"  BLE Address: FC28F7A3-F547-7342-1F57-BB2939694BDC")
    print(f"  Characteristic: 6e400002-b5a3-f393-e0a9-e50e24dcca9e")
    print()
    
    print("Starting Flask server...")
    print("Frontend will be available at: http://localhost:5001")
    print("Press Ctrl+C to stop the server")
    print("=" * 50)
    
    # Start the Flask app
    try:
        from backend import app
        app.run(debug=True, host='0.0.0.0', port=5001)
    except KeyboardInterrupt:
        print("\nServer stopped by user")
    except Exception as e:
        print(f"Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

