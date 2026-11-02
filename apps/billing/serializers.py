from rest_framework import serializers

from apps.billing import services
from apps.billing.models import CorporateAccount, Invoice, InvoiceLine, Payment
from apps.learners.models import Learner
from apps.scheduling.models import Enrolment


class CorporateAccountReadSerializer(serializers.ModelSerializer):
    nominee_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = CorporateAccount
        fields = [
            "id",
            "name",
            "company",
            "lead_user",
            "lead_email",
            "credit_limit",
            "terms_days",
            "balance",
            "active",
            "nominee_count",
        ]
        read_only_fields = fields


class CorporateAccountWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = CorporateAccount
        fields = ["name", "company", "lead_email", "credit_limit", "terms_days"]


class InvoiceLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceLine
        fields = ["id", "description", "quantity", "unit_price", "amount"]


class InvoiceSerializer(serializers.ModelSerializer):
    lines = InvoiceLineSerializer(many=True, read_only=True)
    learner_name = serializers.CharField(source="learner.full_name", read_only=True)
    corporate_account_name = serializers.CharField(
        source="corporate_account.name", read_only=True
    )
    balance = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = [
            "id",
            "invoice_no",
            "corporate_account",
            "corporate_account_name",
            "enrolment",
            "learner",
            "learner_name",
            "issue_date",
            "due_date",
            "currency",
            "subtotal",
            "tax",
            "total",
            "amount_paid",
            "balance",
            "status",
            "notes",
            "lines",
        ]

    def get_balance(self, obj) -> str:
        return f"{(obj.total or 0) - (obj.amount_paid or 0):.2f}"


class InvoiceLineInputSerializer(serializers.Serializer):
    description = serializers.CharField(max_length=255)
    quantity = serializers.DecimalField(max_digits=12, decimal_places=2, default=1)
    unit_price = serializers.DecimalField(max_digits=14, decimal_places=2)


class InvoiceCreateSerializer(serializers.Serializer):
    corporate_account = serializers.PrimaryKeyRelatedField(
        queryset=CorporateAccount.objects.all(), required=False, allow_null=True
    )
    enrolment = serializers.PrimaryKeyRelatedField(
        queryset=Enrolment.objects.all(), required=False, allow_null=True
    )
    learner = serializers.PrimaryKeyRelatedField(
        queryset=Learner.objects.all(), required=False, allow_null=True
    )
    issue_date = serializers.DateField(required=False)
    due_date = serializers.DateField(required=False, allow_null=True)
    currency = serializers.CharField(max_length=3, required=False, default="NGN")
    tax_pct = serializers.DecimalField(
        max_digits=5, decimal_places=2, required=False, allow_null=True
    )
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    lines = InvoiceLineInputSerializer(many=True)

    def create(self, validated_data):
        actor = self.context["request"].user
        return services.create_invoice(actor=actor, **validated_data)


class InvoiceUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invoice
        fields = ["due_date", "currency", "notes"]


class PaymentSerializer(serializers.ModelSerializer):
    invoice_no = serializers.CharField(source="invoice.invoice_no", read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id",
            "invoice",
            "invoice_no",
            "payment_ref",
            "amount",
            "paid_at",
            "method",
            "status",
            "received_by",
            "notes",
        ]
        read_only_fields = [
            "id",
            "invoice",
            "payment_ref",
            "amount",
            "paid_at",
            "status",
            "received_by",
        ]


class PaymentCreateSerializer(serializers.Serializer):
    invoice = serializers.PrimaryKeyRelatedField(queryset=Invoice.objects.all())
    amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    paid_at = serializers.DateTimeField(required=False)
    method = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    payment_ref = serializers.CharField(
        max_length=64, required=False, allow_blank=True, default=""
    )
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    confirm = serializers.BooleanField(required=False, default=True)

    def create(self, validated_data):
        actor = self.context["request"].user
        invoice = validated_data.pop("invoice")
        return services.record_payment(invoice=invoice, received_by=actor, **validated_data)

