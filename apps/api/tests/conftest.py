import pytest
from app.config import get_settings
from app.main import app

# Prevent migrations from running on TestClient startup
app.router.on_startup = [h for h in app.router.on_startup if h.__name__ != "run_migrations"]

@pytest.fixture(autouse=True)
def disable_local_mode_in_tests():
    settings = get_settings()
    original_local_mode = settings.local_mode
    settings.local_mode = False
    yield
    settings.local_mode = original_local_mode
