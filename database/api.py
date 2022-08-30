# coding: utf-8
from common.api.serializers import BaseCustomSerializer
from common.api.utils import api_view_with_serializer, create_api
from django.urls import path
from rest_framework import serializers

from database.ckparser import parse_text
from database.ckparser import revert as revert_data
from database.models import M2M_MODELS, MODELS, User

# disable_relation_fields(*MODELS)
router, all_serializers, all_viewsets = create_api(User, *MODELS, *M2M_MODELS, many_to_many=True)


class InputParserSerializer(BaseCustomSerializer):
    text = serializers.CharField(label="Text")


@api_view_with_serializer(["POST"], input_serializer=InputParserSerializer)
def parse(request):
    text = request.validated_data["text"]
    return parse_text(text)


class InputReverterSerializer(BaseCustomSerializer):
    data = serializers.JSONField(label="Data")


@api_view_with_serializer(["POST"], input_serializer=InputReverterSerializer)
def revert(request):
    data = request.validated_data["data"]
    return {"result": revert_data(data)}


namespace = "database-api"
app_name = "database"
urlpatterns = [
    path("parse/", parse, name="parse"),
] + router.urls
urls = (urlpatterns, namespace, app_name)
