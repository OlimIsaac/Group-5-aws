from django.core.exceptions import PermissionDenied
from functools import wraps


def role_required(*roles):
    """Decorator to restrict view access to users with specific roles."""

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated or request.user.role not in roles:
                raise PermissionDenied
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


def admin_required(view_func):
    return role_required('admin')(view_func)


def clinician_required(view_func):
    return role_required('clinician')(view_func)


def patient_required(view_func):
    return role_required('patient')(view_func)
