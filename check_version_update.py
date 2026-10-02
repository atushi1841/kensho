from apify_client import ApifyClient
import inspect

# Check actor version update signature
from apify_client.clients.resource_clients.actor_version import ActorVersionClient
print(inspect.getsource(ActorVersionClient.update))