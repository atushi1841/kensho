from apify_client.clients.resource_clients import actor
import inspect
print([m for m in dir(actor.ActorClient) if not m.startswith('_')])