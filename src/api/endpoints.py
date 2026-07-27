"""High-level wrappers for the CSQAQ API endpoints used by the strategy."""

from src.api.client import CSQAQClient


def bind_local_ip(client: CSQAQClient) -> str:
    """Bind the current request IP to the ApiToken whitelist.

    The underlying endpoint has a 30-second cooldown on the client side.
    """
    return client.post("/sys/bind_local_ip")


def get_current_data_init(client: CSQAQClient, **kwargs) -> dict:
    """Fetch the home-page index data with ``type=init``.

    Returns the raw ``data`` payload, which contains ``sub_index_data`` among
    other fields.

    Extra keyword arguments are forwarded to the underlying client request.
    """
    return client.get("/current_data", params={"type": "init"}, **kwargs)


def get_sub_kline(
    client: CSQAQClient, sub_index_id: str, period: str = "4hour", **kwargs
) -> dict:
    """Fetch K-line data for a specific sub-index.

    Args:
        client: The API client instance.
        sub_index_id: The sub-index id from ``sub_index_data``.
        period: One of ``1hour``, ``4hour``, ``1day``, ``7day``.

    Returns:
        The raw ``data`` payload, typically containing ``t``, ``o``, ``c``,
        ``h``, ``l``, ``v`` arrays.

    Extra keyword arguments are forwarded to the underlying client request.
    """
    return client.get(
        "/sub/kline", params={"id": sub_index_id, "type": period}, **kwargs
    )
