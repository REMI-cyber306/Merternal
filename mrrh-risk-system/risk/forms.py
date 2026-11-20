from django import forms

from .features import FEATURE_ORDER
from .models import Assessment


class AssessmentForm(forms.ModelForm):
    class Meta:
        model = Assessment
        fields = ["study_id"] + FEATURE_ORDER
        widgets = {
            "study_id": forms.TextInput(attrs={"autocomplete": "off", "placeholder": "e.g. S-0001", "maxlength": 20}),
            "glucose_mmol": forms.NumberInput(attrs={"step": "0.1"}),
            "temp_c": forms.NumberInput(attrs={"step": "0.1"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            w = field.widget
            if isinstance(w, forms.CheckboxInput):
                w.attrs["class"] = "form-check-input"
            else:
                w.attrs["class"] = "form-control" + (" is-invalid" if self.errors.get(name) else "") if self.is_bound else "form-control"

    def clean(self):
        data = super().clean()
        sbp, dbp = data.get("systolic_bp"), data.get("diastolic_bp")
        if sbp is not None and dbp is not None and sbp <= dbp:
            self.add_error("diastolic_bp", "Diastolic pressure must be lower than systolic pressure. Please re-check both values.")
        age, parity = data.get("age"), data.get("parity")
        if age is not None and parity is not None and parity > max(0, age - 10):
            self.add_error("parity", "This number of previous births is not plausible for the age entered.")
        return data

    def clean_study_id(self):
        return self.cleaned_data["study_id"].strip().upper()
