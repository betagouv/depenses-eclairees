from django.contrib.auth.models import Group

import factory

from docia.models import User


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@test.local")

    full_name = "Pierre"
    short_name = "Dupont"


class GroupFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Group

    name = factory.Sequence(lambda n: f"group_{n}")
