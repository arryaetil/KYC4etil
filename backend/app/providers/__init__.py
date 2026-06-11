"""Provider-factory: kiest mock of live o.b.v. PROVIDER_MODE."""
from ..config import get_settings
from .base import JaarverslagAgent, LookupProvider, WebsiteAgent


def get_providers() -> tuple[LookupProvider, WebsiteAgent, JaarverslagAgent]:
    settings = get_settings()
    if settings.provider_mode == "live":
        from .live import LiveJaarverslagAgent, LivePlacesProvider, LiveWebsiteAgent
        return LivePlacesProvider(), LiveWebsiteAgent(), LiveJaarverslagAgent()
    from .mock import MockJaarverslagAgent, MockLookupProvider, MockWebsiteAgent
    return MockLookupProvider(), MockWebsiteAgent(), MockJaarverslagAgent()
