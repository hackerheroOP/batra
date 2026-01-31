import sys
import os
sys.path.append(os.getcwd())

print(f"CWD: {os.getcwd()}")
print(f"Sys Path: {sys.path}")

print("\n--- Testing Imports ---")

try:
    import plugins.start
    print("✅ plugins.start loaded successfully")
except Exception as e:
    print(f"❌ Error loading plugins.start: {e}")

try:
    import plugins.payment
    print("✅ plugins.payment loaded successfully")
except Exception as e:
    print(f"❌ Error loading plugins.payment: {e}")

try:
    import plugins.indexing
    print("✅ plugins.indexing loaded successfully")
except Exception as e:
    print(f"❌ Error loading plugins.indexing: {e}")

try:
    import plugins.admin_settings
    print("✅ plugins.admin_settings loaded successfully")
except Exception as e:
    print(f"❌ Error loading plugins.admin_settings: {e}")
