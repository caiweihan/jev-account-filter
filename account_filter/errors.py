"""Collection errors shared by platform adapters and orchestration."""


class CollectionError(RuntimeError):
    pass


class RiskControlError(CollectionError):
    pass


class UserNotFoundError(CollectionError):
    pass
