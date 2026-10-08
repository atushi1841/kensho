import sys
sys.path.insert(0, '.')
from server import server
print('Server tools:', [t.name for t in server._tool_manager._tools.values()])
