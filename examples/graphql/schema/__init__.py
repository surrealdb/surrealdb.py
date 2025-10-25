"""GraphQL schema."""
import strawberry
from .queries import Query
from .mutations import Mutation
from .subscriptions import Subscription

# Create the complete GraphQL schema
schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    subscription=Subscription,
)

