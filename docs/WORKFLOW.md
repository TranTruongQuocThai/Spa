# Workflows

## Spa

Customer → appointment → execution → invoice → payment → stock movement → commission → aftercare. The local API currently covers the customer and appointment steps; the remaining financial/stock write operations are tracked as unfinished.

## Training attendance

Student logs in → selects an open class session → grants camera/GPS → submits photo/location → server confirms enrollment and uniqueness → record is `present` when photo and coordinates exist, otherwise `pending_verification`. A production implementation must also calculate allowed time and radius on the server from branch coordinates.
