"""Quick script to check database tables and structure."""

from sqlalchemy import inspect
from app.db.base import engine

inspector = inspect(engine)
tables = inspector.get_table_names()

print("📊 Database Tables:")
for table in tables:
    print(f"  - {table}")

if 'api_costs' in tables:
    print("\n✅ api_costs table exists!")
    print("\n📋 api_costs columns:")
    for col in inspector.get_columns('api_costs'):
        print(f"  - {col['name']}: {col['type']}")
else:
    print("\n❌ api_costs table NOT found")

