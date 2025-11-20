#!/usr/bin/env python3
"""
Test script to check if all required libraries are installed.
This will attempt to import all main modules and report any missing dependencies.
"""

import sys
from pathlib import Path

# Add podcast-summarizer to path (go up one level from tests/ to root)
project_root = Path(__file__).parent.parent / "podcast-summarizer"
sys.path.insert(0, str(project_root))

def test_import(module_name, package_name=None):
    """Test if a module can be imported."""
    try:
        __import__(module_name)
        print(f"✅ {package_name or module_name}")
        return True
    except ImportError as e:
        print(f"❌ {package_name or module_name}: {e}")
        return False
    except Exception as e:
        print(f"⚠️  {package_name or module_name}: {e}")
        return False

def main():
    print("=" * 80)
    print("Testing Library Imports")
    print("=" * 80)
    print()
    
    results = []
    
    # Core Python libraries (should always be available)
    print("Core Python Libraries:")
    print("-" * 80)
    results.append(("os", test_import("os")))
    results.append(("sys", test_import("sys")))
    results.append(("logging", test_import("logging")))
    results.append(("asyncio", test_import("asyncio")))
    results.append(("json", test_import("json")))
    results.append(("datetime", test_import("datetime")))
    print()
    
    # FastAPI and web framework
    print("Web Framework:")
    print("-" * 80)
    results.append(("fastapi", test_import("fastapi", "fastapi")))
    results.append(("uvicorn", test_import("uvicorn", "uvicorn")))
    print()
    
    # Database
    print("Database:")
    print("-" * 80)
    results.append(("sqlalchemy", test_import("sqlalchemy", "sqlalchemy")))
    results.append(("alembic", test_import("alembic", "alembic")))
    print()
    
    # AI/ML Libraries
    print("AI/ML Libraries:")
    print("-" * 80)
    results.append(("openai", test_import("openai", "openai")))
    results.append(("langchain", test_import("langchain", "langchain")))
    results.append(("langchain_openai", test_import("langchain_openai", "langchain-openai")))
    results.append(("langgraph", test_import("langgraph", "langgraph")))
    results.append(("langsmith", test_import("langsmith", "langsmith")))
    print()
    
    # Search Providers
    print("Search Providers:")
    print("-" * 80)
    results.append(("exa_py", test_import("exa_py", "exa_py")))
    print()
    
    # Content Processing
    print("Content Processing:")
    print("-" * 80)
    results.append(("feedparser", test_import("feedparser", "feedparser")))
    results.append(("bs4", test_import("bs4", "beautifulsoup4")))
    results.append(("lxml", test_import("lxml", "lxml")))
    results.append(("youtube_transcript_api", test_import("youtube_transcript_api", "youtube-transcript-api")))
    results.append(("assemblyai", test_import("assemblyai", "assemblyai")))
    print()
    
    # HTTP/API
    print("HTTP/API Libraries:")
    print("-" * 80)
    results.append(("httpx", test_import("httpx", "httpx")))
    print()
    
    # Google APIs
    print("Google APIs:")
    print("-" * 80)
    results.append(("google.auth", test_import("google.auth", "google-auth")))
    results.append(("google_auth_oauthlib", test_import("google_auth_oauthlib", "google-auth-oauthlib")))
    results.append(("google_auth_httplib2", test_import("google_auth_httplib2", "google-auth-httplib2")))
    results.append(("googleapiclient", test_import("googleapiclient", "google-api-python-client")))
    print()
    
    # Utilities
    print("Utilities:")
    print("-" * 80)
    results.append(("dotenv", test_import("dotenv", "python-dotenv")))
    results.append(("pydantic", test_import("pydantic", "pydantic")))
    results.append(("pydantic_settings", test_import("pydantic_settings", "pydantic-settings")))
    results.append(("dateutil", test_import("dateutil", "python-dateutil")))
    print()
    
    # Test application imports
    print("Application Modules:")
    print("-" * 80)
    try:
        from backend.config import settings
        print("✅ config")
    except Exception as e:
        print(f"❌ config: {e}")
        results.append(("config", False))
    
    try:
        from backend.database import init_db
        print("✅ database")
    except Exception as e:
        print(f"❌ database: {e}")
        results.append(("database", False))
    
    try:
        from backend.api.routes import router
        print("✅ api.routes")
    except Exception as e:
        print(f"❌ api.routes: {e}")
        results.append(("api.routes", False))
    
    try:
        from backend.main import app
        print("✅ main")
    except Exception as e:
        print(f"❌ main: {e}")
        results.append(("main", False))
    
    print()
    print("=" * 80)
    
    # Summary
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    print(f"Summary: {passed}/{total} imports successful")
    print("=" * 80)
    
    if passed < total:
        print()
        print("Missing libraries detected. Install them with:")
        print("pip install -r podcast-summarizer/backend/requirements.txt")
        return 1
    else:
        print()
        print("✅ All libraries are installed!")
        return 0

if __name__ == "__main__":
    sys.exit(main())

