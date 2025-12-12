import asyncwhois
import sys

print(f"Python version: {sys.version}")
print(f"asyncwhois version: {asyncwhois.__version__ if hasattr(asyncwhois, '__version__') else 'unknown'}")

print("\nAvailable attributes in asyncwhois module:")
for attr in dir(asyncwhois):
    if not attr.startswith('_'):
        print(f"  - {attr}")

# Проверяем, есть ли submodule aio
if hasattr(asyncwhois, 'aio'):
    print("\nAvailable attributes in asyncwhois.aio:")
    for attr in dir(asyncwhois.aio):
        if not attr.startswith('_'):
            print(f"  - {attr}")
else:
    print("\nasyncwhois.aio not found")

# Проверим основной модуль на наличие функций
print("\nChecking for specific functions:")
functions_to_check = ['lookup', 'query', 'aio_lookup', 'async_lookup']
for func in functions_to_check:
    if hasattr(asyncwhois, func):
        print(f"  ✅ {func}: {getattr(asyncwhois, func)}")
    else:
        print(f"  ❌ {func}: not found")