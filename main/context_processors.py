from main.models import UserProfile


def auth_profile(request):
    role = None
    full_name = None

    user = getattr(request, 'user', None)
    if user and user.is_authenticated:
        try:
            profile = user.profile
        except Exception:
            profile = None
        if profile:
            role = profile.role
            full_name = profile.full_name
        else:
            full_name = user.username

    return {
        'auth_role': role,
        'auth_full_name': full_name,
        'ROLE_TEACHER': UserProfile.ROLE_TEACHER,
        'ROLE_PRINCIPAL': UserProfile.ROLE_PRINCIPAL,
    }
