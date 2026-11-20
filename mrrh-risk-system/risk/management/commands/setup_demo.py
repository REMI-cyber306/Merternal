"""Create the user groups and (optionally) demo accounts.

Usage:
    python manage.py setup_demo                      # only creates the groups
    DEMO_PASSWORD='a-long-password' python manage.py setup_demo --users
Passwords are never hard-coded: set DEMO_PASSWORD yourself.
"""
import os

from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create the 'Healthcare worker' group and optional demo users (clinician, supervisor)."

    def add_arguments(self, parser):
        parser.add_argument("--users", action="store_true", help="also create demo users using DEMO_PASSWORD")

    def handle(self, *args, **opts):
        Group.objects.get_or_create(name="Healthcare worker")
        self.stdout.write("Group 'Healthcare worker' ready.")
        if not opts["users"]:
            return
        pw = os.environ.get("DEMO_PASSWORD", "")
        if len(pw) < 10:
            raise CommandError("Set DEMO_PASSWORD (at least 10 characters) before using --users.")
        for username, staff in (("clinician", False), ("supervisor", True)):
            user, created = User.objects.get_or_create(username=username, defaults={"is_staff": staff})
            user.is_staff = staff
            user.set_password(pw)
            user.save()
            if not staff:
                user.groups.add(Group.objects.get(name="Healthcare worker"))
            self.stdout.write(f"{'Created' if created else 'Updated'} user '{username}' ({'supervisor' if staff else 'healthcare worker'}).")
