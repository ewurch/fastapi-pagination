import databases
import sqlalchemy
from fastapi import FastAPI
from ormar import Integer, Model, ModelMeta, String
from pytest import fixture

from fastapi_pagination import Page, add_pagination
from fastapi_pagination.ext.ormar import paginate
from fastapi_pagination.limit_offset import Page as LimitOffsetPage

from ..base import BasePaginationTestCase, SafeTestClient, UserOut
from ..utils import faker


@fixture(scope="session")
def db(database_url):
    return databases.Database(database_url)


@fixture(scope="session")
def metadata(database_url):
    return sqlalchemy.MetaData()


@fixture(scope="session")
def User(db, metadata):
    # weird syntax cause otherwise class definition is evaluated
    # before fixtures are resolved, and ormar uses Metaclass that already
    # requires sqlalchemy.Metadata() to exist
    definition = {
        "Meta": type("Meta", (ModelMeta,), dict(database=db, metadata=metadata)),
        "id": Integer(primary_key=True),
        "name": String(max_length=100),
    }
    User = type("User", (Model,), definition)
    return User


@fixture(scope="session")
def app(db, metadata, User):
    app = FastAPI()

    @app.on_event("startup")
    async def on_startup() -> None:
        engine = sqlalchemy.create_engine(str(db.url))
        metadata.drop_all(engine)
        metadata.create_all(engine)

        await db.connect()
        User.Meta.metadata = metadata
        User.Meta.abstract = False
        for _ in range(100):
            await User.objects.create(name=faker.name())

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        await db.disconnect()

    @app.get("/default", response_model=Page[UserOut])
    @app.get("/limit-offset", response_model=LimitOffsetPage[UserOut])
    async def route():
        return await paginate(User.objects)

    add_pagination(app)
    return app


class TestOrmar(BasePaginationTestCase):
    @fixture(scope="session")
    async def client(self, app):
        with SafeTestClient(app) as c:
            yield c

    @fixture(scope="session")
    async def entities(self, User):
        return await User.objects.all()
