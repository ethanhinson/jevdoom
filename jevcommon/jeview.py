"""Route Jev calls through a local Jeview (github.com/andududu/jeview) so they show on its live map."""

from __future__ import annotations

JEVIEW_URL = "http://127.0.0.1:4777"


def base_url(jeview: str | None, label: str) -> str | None:
    """The SDK base URL that sends calls through Jeview, grouped under `label` in the viewer."""
    if jeview is None:
        return None
    return f"{jeview.rstrip('/')}/{label}"


def display_headers(fields: dict[str, str]) -> dict[str, str]:
    """A Jeview-Display header: label each answer on the map with a field of the chosen option's
    description instead of its key. Jeview strips the header before forwarding; TypeSafe ignores it."""
    return {"Jeview-Display": ", ".join(f"{question}={field}" for question, field in fields.items())}


def add_argument(parser) -> None:
    parser.add_argument(
        "--jeview",
        nargs="?",
        const=JEVIEW_URL,
        default=None,
        metavar="URL",
        help=f"send Jev calls through a running Jeview so they show on its live map (default {JEVIEW_URL})",
    )
