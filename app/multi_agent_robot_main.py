from __future__ import annotations

from app.product_profiles import apply_product_profile_env

apply_product_profile_env("multi_agent_robot")

from app.main import app  # noqa: E402
