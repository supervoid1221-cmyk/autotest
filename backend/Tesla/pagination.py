from collections import OrderedDict

from rest_framework import pagination
from rest_framework.response import Response


class PageNumberPagination(pagination.PageNumberPagination):
    page_query_param = "page"
    page_size_query_param = "pageSize"
    # 防止调用方通过任意大的 pageSize 绕过分页，拖垮数据库和序列化。
    max_page_size = 1000

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
