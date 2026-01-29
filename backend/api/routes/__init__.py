# backend/api/routes/__init__.py
# Import blueprints for easier access
from .scheduler import scheduler_bp
from .interviews import interviews_bp

__all__ = ['scheduler_bp', 'interviews_bp']
