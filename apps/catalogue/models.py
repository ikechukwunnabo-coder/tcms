from django.db import models

from apps.common.enums import CertificateTypeCode, ExpiryTypeCode
from apps.common.models import TimeStampedModel


class CertificateType(models.Model):
    id = models.SmallAutoField(primary_key=True)
    name = models.CharField(max_length=64)

    class Meta:
        db_table = "certificate_type"

    def __str__(self) -> str:
        return self.name


class Course(TimeStampedModel):
    """Course — mirrors legacy ``tblHSECourses`` (``coursecode`` preserved)."""

    course_code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=200)
    cert_type = models.ForeignKey(
        CertificateType,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="courses",
        default=CertificateTypeCode.STANDARD,
    )
    expiry_type = models.SmallIntegerField(
        choices=ExpiryTypeCode.choices, default=ExpiryTypeCode.CALCULATED
    )
    duration_days = models.IntegerField(null=True, blank=True)
    validity_years = models.IntegerField(null=True, blank=True)
    id_card = models.BooleanField(default=False)
    foet_required = models.BooleanField(default=False)
    opito_reg_code = models.CharField(max_length=64, blank=True, default="")
    front_id_text = models.TextField(blank=True, default="")
    back_id_text = models.TextField(blank=True, default="")
    refresher_course = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="refreshers"
    )
    active = models.BooleanField(default=True)

    class Meta:
        db_table = "course"

    def __str__(self) -> str:
        return f"{self.course_code} {self.name}"


class CourseModule(models.Model):
    name = models.CharField(max_length=200, unique=True)
    active = models.BooleanField(default=True)

    class Meta:
        db_table = "course_module"

    def __str__(self) -> str:
        return self.name


class CourseItem(models.Model):
    name = models.CharField(max_length=200, unique=True)
    active = models.BooleanField(default=True)

    class Meta:
        db_table = "course_item"

    def __str__(self) -> str:
        return self.name


class CourseModuleRelation(TimeStampedModel):
    """Axis ``/course-module-rel``: a module assigned to a course."""

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="module_relations")
    module = models.ForeignKey(
        CourseModule, on_delete=models.CASCADE, related_name="course_relations"
    )

    class Meta:
        db_table = "course_module_relation"
        constraints = [
            models.UniqueConstraint(
                fields=["course", "module"], name="uq_course_module_relation"
            )
        ]

    def __str__(self) -> str:
        return f"{self.course_id}/{self.module_id}"


class CourseItemRelation(TimeStampedModel):
    """Axis ``/course-item-rel``: an item assigned to a course."""

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="item_relations")
    item = models.ForeignKey(
        CourseItem, on_delete=models.CASCADE, related_name="course_relations"
    )

    class Meta:
        db_table = "course_item_relation"
        constraints = [
            models.UniqueConstraint(
                fields=["course", "item"], name="uq_course_item_relation"
            )
        ]

    def __str__(self) -> str:
        return f"{self.course_id}/{self.item_id}"


class CourseModuleItem(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="module_items")
    module = models.ForeignKey(CourseModule, on_delete=models.CASCADE, related_name="+")
    item = models.ForeignKey(CourseItem, on_delete=models.CASCADE, related_name="+")

    class Meta:
        db_table = "course_module_item"
        constraints = [
            models.UniqueConstraint(
                fields=["course", "module", "item"], name="uq_course_module_item"
            )
        ]

    def __str__(self) -> str:
        return f"{self.course_id}/{self.module_id}/{self.item_id}"
