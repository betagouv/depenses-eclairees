import factory

from docia.models import User


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@test.local")

    full_name = "Pierre"
    short_name = "Dupont"
