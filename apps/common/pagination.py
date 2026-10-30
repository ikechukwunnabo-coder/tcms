"""Pagination matching the API contract (``04`` §1): ``{data, total, page}``."""
from __future__ import annotations

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class StandardPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200

    def get_paginated_response(self, data):
        return Response(
            {
                "data": data,
                "total": self.page.paginator.count,
                "page": self.page.number,
                "page_size": self.get_page_size(self.request),
            }
        )
