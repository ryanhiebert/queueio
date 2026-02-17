from django.urls import path

from .job import index

urlpatterns = [
    path("", index),
]
