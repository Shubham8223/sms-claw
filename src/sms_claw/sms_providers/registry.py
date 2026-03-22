"""SMS provider registry — register once, resolve by name."""

from __future__ import annotations

from functools import lru_cache

from sms_claw.core.config import get_settings
from sms_claw.sms_providers.base import SMSProviderBase

_REGISTRY: dict[str, type[SMSProviderBase]] = {}


def register(name: str):  # type: ignore[no-untyped-def]
    """Class decorator — registers a provider under the given name."""

    def decorator(cls: type[SMSProviderBase]) -> type[SMSProviderBase]:
        _REGISTRY[name] = cls
        return cls

    return decorator


def _load_all() -> None:
    """Import all built-in providers so their @register decorators fire."""
    from sms_claw.sms_providers.africas_talking_provider import AfricasTalkingProvider
    from sms_claw.sms_providers.twilio_provider import TwilioProvider
    from sms_claw.sms_providers.vonage_provider import VonageProvider

    register("twilio")(TwilioProvider)
    register("africas_talking")(AfricasTalkingProvider)
    register("vonage")(VonageProvider)


@lru_cache(maxsize=1)
def get_sms_provider() -> SMSProviderBase:
    _load_all()
    name = get_settings().default_sms_provider
    if name not in _REGISTRY:
        raise ValueError(
            f"SMS provider '{name}' not registered. Available: {list(_REGISTRY.keys())}"
        )
    return _REGISTRY[name]()
