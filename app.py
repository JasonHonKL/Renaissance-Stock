# app.py
import asyncio
import logging
import argparse
from web.app import run_app

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Stock Analysis System')
    parser.add_argument('--no-web', action='store_true', help='Run without web interface')
    args = parser.parse_args()
    
    if args.no_web:
        # CLI mode could be implemented here
        print("CLI mode not implemented yet")
    else:
        # Run web interface
        run_app()