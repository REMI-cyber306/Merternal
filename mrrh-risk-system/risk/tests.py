from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse

from . import predictor
from .features import CLASSES, FEATURE_ORDER
from .models import Assessment

LOW = dict(study_id="s-0001", age=26, gestational_weeks=28, systolic_bp=110, diastolic_bp=70, glucose_mmol=5.0,
           temp_c=36.7, heart_rate=80, parity=1)
HIGH = dict(study_id="S-0002", age=41, gestational_weeks=34, systolic_bp=178, diastolic_bp=114, glucose_mmol=12.5,
            temp_c=38.4, heart_rate=124, parity=6, headache="on", blurred_vision="on", vaginal_bleeding="on",
            swelling="on", pre_existing_condition="on", previous_caesarean="on")


def vals(d):
    out = {f: 0 for f in FEATURE_ORDER}
    for k, v in d.items():
        if k in out:
            out[k] = 1 if v == "on" else v
    return out


class PredictorTests(TestCase):
    def test_returns_valid_category_and_probabilities_sum_to_one(self):
        cat, probs, version = predictor.predict(vals(LOW))
        self.assertIn(cat, CLASSES)
        self.assertAlmostEqual(sum(probs.values()), 1.0, places=5)
        self.assertTrue(version)

    def test_clear_low_and_high_examples(self):
        self.assertEqual(predictor.predict(vals(LOW))[0], "low")
        self.assertEqual(predictor.predict(vals(HIGH))[0], "high")

    def test_a_medium_example_exists(self):
        mild = dict(LOW, systolic_bp=146, diastolic_bp=92, headache="on")
        self.assertEqual(predictor.predict(vals(mild))[0], "medium")


class FormTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("nurse", password="a-long-password-1")
        self.client.force_login(self.user)

    def post(self, **over):
        data = dict(LOW)
        data.update(over)
        return self.client.post(reverse("assess_new"), data)

    def test_valid_submission_creates_assessment_and_redirects(self):
        r = self.post()
        self.assertEqual(r.status_code, 302)
        a = Assessment.objects.get()
        self.assertEqual(a.study_id, "S-0001")  # normalised to upper case
        self.assertEqual(a.user, self.user)
        self.assertIn(a.predicted_category, CLASSES)
        self.assertTrue(a.model_version)

    def test_out_of_range_values_rejected(self):
        for field, bad in [("age", 5), ("gestational_weeks", 60), ("systolic_bp", 300), ("glucose_mmol", 0.2),
                           ("temp_c", 50), ("heart_rate", 10), ("parity", 40)]:
            with self.subTest(field=field):
                self.assertEqual(self.post(**{field: bad}).status_code, 200)
        self.assertEqual(Assessment.objects.count(), 0)

    def test_missing_input_rejected(self):
        data = dict(LOW)
        del data["heart_rate"]
        self.assertEqual(self.client.post(reverse("assess_new"), data).status_code, 200)
        self.assertEqual(Assessment.objects.count(), 0)

    def test_systolic_must_exceed_diastolic(self):
        r = self.post(systolic_bp=80, diastolic_bp=90)
        self.assertContains(r, "Diastolic pressure must be lower")
        self.assertEqual(Assessment.objects.count(), 0)

    def test_study_code_cannot_look_like_a_name_or_phone_number(self):
        for bad in ["Jane Doe", "0777 395 407", "ab", "name@mail.com"]:
            with self.subTest(code=bad):
                self.assertEqual(self.post(study_id=bad).status_code, 200)
        self.assertEqual(Assessment.objects.count(), 0)

    def test_boundary_values_accepted(self):
        r = self.post(age=10, gestational_weeks=1, systolic_bp=60, diastolic_bp=30, glucose_mmol=1.0, temp_c=33.0, heart_rate=30, parity=0)
        self.assertEqual(r.status_code, 302)


class AccessTests(TestCase):
    def setUp(self):
        self.a = User.objects.create_user("nurse_a", password="a-long-password-1")
        self.b = User.objects.create_user("nurse_b", password="a-long-password-1")
        self.boss = User.objects.create_user("boss", password="a-long-password-1", is_staff=True)
        cat, probs, ver = predictor.predict(vals(LOW))
        kw = {f: v for f, v in vals(LOW).items()}
        self.rec = Assessment.objects.create(user=self.a, study_id="S-0001", predicted_category=cat,
                                             class_probabilities=probs, model_version=ver, **kw)

    def test_anonymous_users_are_sent_to_login(self):
        for name in ["home", "assess_new", "history"]:
            r = self.client.get(reverse(name))
            self.assertEqual(r.status_code, 302, name)
            self.assertIn("/accounts/login/", r["Location"])
        r = self.client.get(reverse("assessment_detail", args=[self.rec.pk]))
        self.assertEqual(r.status_code, 302)

    def test_owner_can_view_other_worker_cannot_supervisor_can(self):
        url = reverse("assessment_detail", args=[self.rec.pk])
        self.client.force_login(self.a)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.force_login(self.b)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.boss)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_result_page_shows_notice_and_hides_probabilities(self):
        self.client.force_login(self.a)
        r = self.client.get(reverse("assessment_detail", args=[self.rec.pk]))
        self.assertContains(r, "Decision support only")
        self.assertContains(r, "not a diagnosis")
        self.assertNotContains(r, "class_probabilities")
        self.assertNotContains(r, "%")

    def test_history_is_scoped_per_user(self):
        self.client.force_login(self.b)
        self.assertEqual(len(self.client.get(reverse("history")).context["page"].object_list), 0)
        self.client.force_login(self.a)
        self.assertEqual(len(self.client.get(reverse("history")).context["page"].object_list), 1)

    def test_csv_export_is_for_supervisors_only(self):
        self.client.force_login(self.a)
        self.assertNotEqual(self.client.get(reverse("export_csv")).status_code, 200)
        self.client.force_login(self.boss)
        r = self.client.get(reverse("export_csv"))
        self.assertEqual(r.status_code, 200)
        self.assertIn("study_code", r.content.decode())

    def test_admin_cannot_add_assessments_directly(self):
        from risk.admin import AssessmentAdmin
        from django.contrib.admin.sites import site
        ma = AssessmentAdmin(Assessment, site)
        self.assertFalse(ma.has_add_permission(None))


class PublicPageTests(TestCase):
    def test_about_page_is_public_and_labels_data_as_synthetic(self):
        r = self.client.get(reverse("about"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "SYNTHETIC")

    def test_healthz_reports_model(self):
        r = self.client.get(reverse("healthz"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "ok")

    @override_settings(DEMO_MODE=True)
    def test_demo_banner_visible(self):
        self.assertContains(self.client.get(reverse("login")), "Prototype for demonstration")


class SetupCommandTests(TestCase):
    def test_users_flag_requires_password(self):
        import os
        os.environ.pop("DEMO_PASSWORD", None)
        with self.assertRaises(CommandError):
            call_command("setup_demo", "--users")

    def test_creates_groups_and_users(self):
        import os
        os.environ["DEMO_PASSWORD"] = "a-long-password-1"
        try:
            call_command("setup_demo", "--users")
        finally:
            os.environ.pop("DEMO_PASSWORD")
        self.assertTrue(User.objects.get(username="supervisor").is_staff)
        self.assertFalse(User.objects.get(username="clinician").is_staff)
