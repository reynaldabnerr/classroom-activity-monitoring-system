from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def role_required(allowed_roles):
    def decorator(view_func):
        @login_required
        def _wrapped(request, *args, **kwargs):
            try:
                profile = request.user.profile
            except Exception:
                profile = None
            if profile is None or profile.role not in allowed_roles:
                raise PermissionDenied('Anda tidak memiliki akses ke halaman ini.')
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator
