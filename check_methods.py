from apify_client.clients.resource_clients import actor_version
import inspect
print([m for m in dir(actor_version.ActorVersionClient) if not m.startswith('_')])