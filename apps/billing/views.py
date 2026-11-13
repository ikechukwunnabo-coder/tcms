from django.db.models import Count
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.billing import services
from apps.billing.models import CorporateAccount, Invoice, Payment
from apps.billing.serializers import (
    CorporateAccountReadSerializer,
    CorporateAccountWriteSerializer,
    InvoiceCreateSerializer,
    InvoiceSerializer,
    InvoiceUpdateSerializer,
    PaymentCreateSerializer,
    PaymentSerializer,
)
from apps.common.enums import RoleCode
from apps.common.views import RoleScopedModelViewSet

READ = (
    RoleCode.SYSTEM_ADMIN,
    RoleCode.ADMIN,
    RoleCode.ACCOUNTS,
)
WRITE = (RoleCode.SYSTEM_ADMIN, RoleCode.ADMIN, RoleCode.ACCOUNTS)
STAFF_READ = tuple(
    role for role in RoleCode if role not in (RoleCode.HR_MANAGER, RoleCode.HR_OFFICER)
)


class CorporateAccountViewSet(RoleScopedModelViewSet):
    queryset = (
        CorporateAccount.objects.all()
        .annotate(nominee_count=Count("nominees"))
        .order_by("name")
    )
    serializer_class = CorporateAccountReadSerializer
    required_roles = STAFF_READ
    write_roles = WRITE
    search_fields = ["name", "company__name", "lead_email"]

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return CorporateAccountWriteSerializer
        return CorporateAccountReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = CorporateAccountWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account = serializer.save()
        account = self.get_queryset().get(pk=account.pk)
        data = CorporateAccountReadSerializer(account).data
        return Response(data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        account = self.get_object()
        serializer = CorporateAccountWriteSerializer(
            account, data=request.data, partial=kwargs.pop("partial", False)
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        account = self.get_queryset().get(pk=account.pk)
        return Response(CorporateAccountReadSerializer(account).data)


class InvoiceViewSet(RoleScopedModelViewSet):
    queryset = (
        Invoice.objects.all()
        .select_related("corporate_account", "enrolment", "learner")
        .prefetch_related("lines")
        .order_by("-issue_date", "-id")
    )
    serializer_class = InvoiceSerializer
    required_roles = READ
    write_roles = WRITE
    filterset_fields = ["corporate_account", "enrolment", "learner", "status"]
    search_fields = ["invoice_no", "learner__badge_no", "learner__surname"]

    def get_serializer_class(self):
        if self.action == "create":
            return InvoiceCreateSerializer
        if self.action in ("update", "partial_update"):
            return InvoiceUpdateSerializer
        return InvoiceSerializer

    def create(self, request, *args, **kwargs):
        serializer = InvoiceCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        invoice = serializer.save()
        return Response(InvoiceSerializer(invoice).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = InvoiceUpdateSerializer(
            instance, data=request.data, partial=kwargs.pop("partial", False)
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(InvoiceSerializer(instance).data)

    @action(detail=True, methods=["post"])
    def issue(self, request, pk=None):
        invoice = services.issue_invoice(self.get_object(), actor=request.user)
        return Response(InvoiceSerializer(invoice).data)

    @action(detail=True, methods=["post"])
    def void(self, request, pk=None):
        invoice = services.void_invoice(
            self.get_object(),
            actor=request.user,
            reason=request.data.get("reason", ""),
        )
        return Response(InvoiceSerializer(invoice).data)


class PaymentViewSet(RoleScopedModelViewSet):
    queryset = (
        Payment.objects.all()
        .select_related("invoice", "received_by")
        .order_by("-paid_at", "-id")
    )
    serializer_class = PaymentSerializer
    required_roles = READ
    write_roles = WRITE
    filterset_fields = ["invoice", "status"]
    search_fields = ["payment_ref", "invoice__invoice_no"]

    def get_serializer_class(self):
        if self.action == "create":
            return PaymentCreateSerializer
        return PaymentSerializer

    def create(self, request, *args, **kwargs):
        serializer = PaymentCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        payment = serializer.save()
        return Response(PaymentSerializer(payment).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        payment = services.confirm_payment(self.get_object(), actor=request.user)
        return Response(PaymentSerializer(payment).data)

    @action(detail=True, methods=["post"])
    def fail(self, request, pk=None):
        payment = services.fail_payment(
            self.get_object(),
            actor=request.user,
            reason=request.data.get("reason", ""),
        )
        return Response(PaymentSerializer(payment).data)

