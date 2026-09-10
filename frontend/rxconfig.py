"""Reflex configuration for MetalArm.

Port topology differs between dev and prod, and this is enforced by Reflex
itself (reflex/reflex.py:358): in PROD/PREVIEW, frontend_port and backend_port
MUST be equal - one server (granian) serves both the SSR frontend and the
state/event endpoints.

  dev  (local):  3000 = UI, 8001 = Reflex state server (two ports)
  prod (Docker): 3000 = both (single port)

Reflex's state-server default is 8000, which would collide with the FastAPI
service, so dev moves it to 8001. Both values are env-driven so the Docker
image can set them equal without editing this file.

Plugins are declared EXPLICITLY. Reflex 0.9 warns about implicitly-enabled
plugins and has deprecated passing `theme=` to rx.App(); the theme now belongs
to RadixThemesPlugin. Declaring them here keeps the build warning-free and
pins behaviour rather than inheriting shifting defaults.
"""

import os

import reflex as rx

# Placeholder dark theme. Frontend Agent (Sonnet) owns the real palette -
# original work only, inspired by the hunter-rank aesthetic, never copying
# Solo Leveling assets, logos, or text.
config = rx.Config(
    app_name="metalarm",
    backend_port=int(os.getenv("REFLEX_BACKEND_PORT", "8001")),
    frontend_port=int(os.getenv("REFLEX_FRONTEND_PORT", "3000")),
    # Must be resolvable from the BROWSER. Inside Docker the container
    # hostname is not, so this stays a host-reachable URL.
    # NOTE: this value is baked into the compiled JS bundle at build time.
    api_url=os.getenv("REFLEX_API_URL", "http://localhost:8001"),
    telemetry_enabled=False,
    plugins=[
        rx.plugins.RadixThemesPlugin(
            theme=rx.theme(appearance="dark", accent_color="blue", radius="large"),
        ),
        rx.plugins.SitemapPlugin(),
    ],
)
