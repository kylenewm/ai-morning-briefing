#!/usr/bin/env python3
"""
Test Supabase database connection.
Run this after setting DATABASE_URL in .env
"""
import sys
from pathlib import Path

# Add podcast-summarizer to path (go up one level from tests/ to root)
sys.path.insert(0, str(Path(__file__).parent.parent / "podcast-summarizer"))

from backend.database.db import SessionLocal, init_db, engine
from backend.database.models import ContentItem, Insight, Briefing
from sqlalchemy import text

def test_connection():
    """Test database connection and table creation."""
    print("=" * 60)
    print("🧪 Testing Supabase Connection")
    print("=" * 60)
    
    try:
        # Test 1: Basic connection
        print("\n1️⃣ Testing database connection...")
        db = SessionLocal()
        result = db.execute(text("SELECT version()"))
        version = result.fetchone()[0]
        print(f"   ✅ Connected to: {version[:50]}...")
        db.close()
        
        # Test 2: Initialize tables
        print("\n2️⃣ Initializing database tables...")
        init_db()
        print("   ✅ Tables created/verified successfully")
        
        # Test 3: Verify tables exist
        print("\n3️⃣ Verifying tables exist...")
        db = SessionLocal()
        
        # Check each table
        tables = ['content_items', 'insights', 'briefings']
        for table_name in tables:
            result = db.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
            count = result.fetchone()[0]
            print(f"   ✅ Table '{table_name}' exists with {count} rows")
        
        db.close()
        
        # Test 4: Test write operation
        print("\n4️⃣ Testing write operation...")
        db = SessionLocal()
        
        # Try to insert a test content item
        test_item = ContentItem(
            source_type="test",
            source_name="Test Source",
            item_url=f"https://test.example.com/test-{Path(__file__).name}",
            title="Test Item",
            transcript_fetched=False
        )
        
        db.add(test_item)
        db.commit()
        print(f"   ✅ Test item inserted with ID: {test_item.id}")
        
        # Clean up test item
        db.delete(test_item)
        db.commit()
        print("   ✅ Test item deleted (cleanup)")
        
        db.close()
        
        # Success!
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        print("\n📝 Next steps:")
        print("   1. Run: python test_podcast.py")
        print("   2. Verify podcasts are cached in Supabase dashboard")
        print("   3. Push changes to GitHub")
        print("   4. Add GitHub Secrets")
        print("   5. Test workflow manually\n")
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("\n💡 Troubleshooting:")
        print("   1. Check that DATABASE_URL is set in .env")
        print("   2. Verify the connection string format:")
        print("      postgresql://postgres:[PASSWORD]@db.[PROJECT].supabase.co:5432/postgres")
        print("   3. Check that psycopg2-binary is installed:")
        print("      pip install psycopg2-binary")
        print("   4. Run the SQL schema in Supabase SQL Editor:\n")
        print("      See: supabase_schema.sql\n")
        return False


if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)

