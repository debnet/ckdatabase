from common.api.permissions import CommonModelPermissions


class AccessApiPermissions(CommonModelPermissions):
    def has_permission(self, request, view):
        user = request.user
        if user and user.is_authenticated and (user.can_use_api or user.is_superuser):
            return super().has_permission(request, view)
        return False
