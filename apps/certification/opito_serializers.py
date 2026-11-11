from rest_framework import serializers

from apps.certification.models import OpitoFile


class OpitoCohortSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    course = serializers.IntegerField()
    course_code = serializers.CharField()
    product_code = serializers.CharField()
    start = serializers.CharField()
    start_date = serializers.DateField()
    learners = serializers.IntegerField()
    record_count = serializers.IntegerField()
    object_key = serializers.CharField()
    file_name = serializers.CharField()
    fileName = serializers.CharField()
    file_id = serializers.IntegerField(allow_null=True)
    generated_at = serializers.DateTimeField(allow_null=True)


class OpitoFileSerializer(serializers.ModelSerializer):
    fileName = serializers.SerializerMethodField()
    file_name = serializers.SerializerMethodField()
    course_code = serializers.CharField(source="course.course_code", read_only=True)
    product_code = serializers.CharField(source="course.opito_reg_code", read_only=True)
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = OpitoFile
        fields = [
            "id",
            "course",
            "course_code",
            "product_code",
            "start_date",
            "record_count",
            "object_key",
            "file_name",
            "fileName",
            "generated_at",
            "download_url",
            "created_at",
            "updated_at",
        ]

    def get_file_name(self, obj: OpitoFile) -> str:
        return obj.object_key.rsplit("/", 1)[-1] if obj.object_key else ""

    def get_fileName(self, obj: OpitoFile) -> str:
        return self.get_file_name(obj)

    def get_download_url(self, obj: OpitoFile) -> str:
        request = self.context.get("request")
        path = f"/api/v1/opito-files/{obj.pk}/download/"
        return request.build_absolute_uri(path) if request else path


class OpitoValidateSerializer(serializers.Serializer):
    valid = serializers.BooleanField()
    missingVantageIds = serializers.ListField(child=serializers.DictField())


class OpitoContentRowSerializer(serializers.Serializer):
    training_record = serializers.IntegerField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    centre_code = serializers.CharField(allow_blank=True)
    product_code = serializers.CharField(allow_blank=True)
    booking_ref = serializers.CharField()
    learner_count = serializers.IntegerField()
    opito_learner_no = serializers.CharField(allow_blank=True)
    vantage_id = serializers.CharField(allow_blank=True)
    first_name = serializers.CharField(allow_blank=True)
    last_name = serializers.CharField(allow_blank=True)
    dob = serializers.DateField(allow_null=True)
    forward_date = serializers.DateField(allow_null=True)


class OpitoContentSerializer(serializers.Serializer):
    rows = OpitoContentRowSerializer(many=True)
    count = serializers.IntegerField()


class OpitoGenerateSerializer(serializers.Serializer):
    course = serializers.IntegerField()
    start_date = serializers.DateField(required=False)
    date = serializers.DateField(required=False)

    def validate(self, attrs):
        if not attrs.get("start_date") and not attrs.get("date"):
            raise serializers.ValidationError(
                {"start_date": "Provide the cohort start date."}
            )
        attrs["start_date"] = attrs.get("start_date") or attrs["date"]
        return attrs
