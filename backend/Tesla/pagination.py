from collections import OrderedDict

from rest_framework import pagination
from rest_framework.response import Response


class PageNumberPagination(pagination.PageNumberPagination):
    page_query_param = "page"
    page_size_query_param = "pageSize"

    def get_paginated_response(self, data):
        return Response(
            OrderedDict(
                [
                    ("itemCount", self.page.paginator.count),
                    ("next", self.get_next_link()),
                    ("previous", self.get_previous_link()),
                    ("list", data),
                ]
            )
        )
