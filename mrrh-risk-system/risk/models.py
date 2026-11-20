from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models

from .features import CLASSES, RANGES

study_id_validator = RegexValidator(
    r"^[A-Za-z0-9-]{3,20}$",
    "Use a study code of 3 to 20 letters, digits or hyphens. Never enter a name, phone number or hospital number.",
)


def _r(name):
    lo, hi = RANGES[name]
    return [MinValueValidator(lo), MaxValueValidator(hi)]


class Assessment(models.Model):
    """One risk assessment. Only coded, non-identifying data are stored."""

    CATEGORY_CHOICES = [(c, c.capitalize()) for c in CLASSES]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="assessments")
    study_id = models.CharField("Study code", max_length=20, validators=[study_id_validator],
                                help_text="A coded identifier only. No names, phone numbers or hospital numbers.")
    created_at = models.DateTimeField(auto_now_add=True)

    age = models.PositiveSmallIntegerField("Age (years)", validators=_r("age"))
    gestational_weeks = models.PositiveSmallIntegerField("Gestational age (weeks)", validators=_r("gestational_weeks"))
    systolic_bp = models.PositiveSmallIntegerField("Systolic blood pressure (mmHg)", validators=_r("systolic_bp"))
    diastolic_bp = models.PositiveSmallIntegerField("Diastolic blood pressure (mmHg)", validators=_r("diastolic_bp"))
    glucose_mmol = models.FloatField("Blood glucose (mmol/L)", validators=_r("glucose_mmol"))
    temp_c = models.FloatField("Body temperature (°C)", validators=_r("temp_c"))
    heart_rate = models.PositiveSmallIntegerField("Heart rate (beats per minute)", validators=_r("heart_rate"))
    parity = models.PositiveSmallIntegerField("Number of previous births (parity)", validators=_r("parity"))

    headache = models.BooleanField("Headache", default=False)
    blurred_vision = models.BooleanField("Blurred vision", default=False)
    vaginal_bleeding = models.BooleanField("Vaginal bleeding", default=False)
    abdominal_pain = models.BooleanField("Abdominal pain", default=False)
    fever = models.BooleanField("Fever", default=False)
    swelling = models.BooleanField("Swelling (face, hands or feet)", default=False)
    breathing_difficulty = models.BooleanField("Difficulty breathing", default=False)

    previous_caesarean = models.BooleanField("Previous caesarean section", default=False)
    pre_existing_condition = models.BooleanField("Recorded pre-existing medical condition", default=False)

    predicted_category = models.CharField(max_length=10, choices=CATEGORY_CHOICES)
    class_probabilities = models.JSONField(default=dict, blank=True,
                                           help_text="Stored for audit only. Not shown to users until calibration is assessed.")
    model_version = models.CharField(max_length=40)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.study_id} - {self.predicted_category} ({self.created_at:%Y-%m-%d})"
