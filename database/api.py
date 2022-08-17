# coding: utf-8
from common.api.utils import create_api

from database.models import MODELS, M2M_MODELS, User

# disable_relation_fields(*MODELS)
router, all_serializers, all_viewsets = create_api(User, *MODELS, *M2M_MODELS, many_to_many=True)

namespace = "database-api"
app_name = "database"
urlpatterns = [] + router.urls
urls = (urlpatterns, namespace, app_name)
