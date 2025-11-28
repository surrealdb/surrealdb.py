"""GraphQL schema."""

import strawberry

from .mutations import Mutation
from .queries import Query
from .subscriptions import Subscription

# Create the complete GraphQL schema
schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    subscription=Subscription,
)
