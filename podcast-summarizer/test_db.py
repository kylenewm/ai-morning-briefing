from backend.database.db import init_db

try:
    init_db()
    print('✅ Connected to Supabase and initialized database!')
except Exception as e:
    print(f'❌ Connection failed: {e}')
    import traceback
    traceback.print_exc()
