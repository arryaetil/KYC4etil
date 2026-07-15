"""Provider-factory: kiest mock of live o.b.v. PROVIDER_MODE."""
from ..config import get_settings
from .base import IdentityScopeClassifier, JaarverslagAgent, LookupProvider, WebsiteAgent


def get_providers() -> tuple[LookupProvider, WebsiteAgent, JaarverslagAgent, IdentityScopeClassifier]:
    settings = get_settings()
    if settings.provider_mode == "live":
        from .live import (
            LiveIdentityScopeClassifier, LiveJaarverslagAgent, LivePlacesProvider,
            LiveWebsiteAgent,
        )
        return (
            LivePlacesProvider(), LiveWebsiteAgent(), LiveJaarverslagAgent(),
            LiveIdentityScopeClassifier(),
        )
    from .mock import (
        MockIdentityScopeClassifier, MockJaarverslagAgent, MockLookupProvider,
        MockWebsiteAgent,
    )
    return (
        MockLookupProvider(), MockWebsiteAgent(), MockJaarverslagAgent(),
        MockIdentityScopeClassifier(),
    )
