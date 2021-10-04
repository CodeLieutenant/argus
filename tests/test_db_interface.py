import json
from uuid import UUID, uuid4

import pytest
import logging
from mocks.mock_cluster import MockCluster, MockSession
from argus.db.config import Config
from argus.db.interface import ArgusDatabase, ArgusInterfaceSingletonError, ArgusInterfaceNameError, \
    ArgusInterfaceSchemaError

LOGGER = logging.getLogger(__name__)


def test_interface_connection(mock_cluster):
    db = ArgusDatabase.get()
    assert not db.session.is_shutdown
    ArgusDatabase.destroy()
    assert db.session.is_shutdown


def test_interface_from_config(mock_cluster):
    db = ArgusDatabase.from_config(
        config=Config(username="a", password="a", contact_points=["127.0.0.1", "127.0.0.2", "127.0.0.3"],
                      keyspace_name="example"))
    db.destroy()

    assert MockSession.MOCK_CURRENT_KEYSPACE == "example"


def test_interface_unable_to_init_from_config_twice(mock_cluster, argus_interface_default):
    with pytest.raises(ArgusInterfaceSingletonError):
        db = ArgusDatabase.from_config(
            config=Config(username="a", password="a", contact_points=["127.0.0.1", "127.0.0.2", "127.0.0.3"],
                          keyspace_name="example"))


def test_interface_is_singleton(mock_cluster, argus_interface_default):
    db = ArgusDatabase.get()

    assert id(argus_interface_default) == id(db)


def test_inteface_supported_types(mock_cluster, argus_interface_default):
    for typecls in [int, float, str, UUID]:
        assert argus_interface_default.is_native_type(typecls)


def test_interface_schema_init(mock_cluster, preset_test_details_schema, simple_primary_key, argus_interface_default):
    schema = {
        **simple_primary_key,
        **preset_test_details_schema,
    }

    argus_interface_default.init_table("test_table", schema)
    assert MockSession.MOCK_LAST_QUERY[0] == "CREATE TABLE IF NOT EXISTS test_table" \
                                             "(name varchar , scm_revision_id varchar , started_by varchar , " \
                                             "build_job_name varchar , build_job_url varchar , start_time varint ," \
                                             " yaml_test_duration varint , config_files list<varchar> , " \
                                             "packages list<frozen<PackageVersion>> , end_time varint , " \
                                             "PRIMARY KEY (id, ))"


def test_interface_init_table_twice(mock_cluster, preset_test_details_schema, simple_primary_key,
                                    argus_interface_default):
    schema = {
        **simple_primary_key,
        **preset_test_details_schema,
    }

    argus_interface_default.init_table("test_table", schema)
    second_result = argus_interface_default.init_table("test_table", schema)

    assert second_result[1] == "Table test_table already initialized"


def test_interface_prepare_cache(mock_cluster, argus_interface_default):
    statement = argus_interface_default.prepare_query_for_table("example", "test", "SELECT * FROM example")
    cached_statement = argus_interface_default.prepared_statements.get("example_test")

    assert id(statement) == id(cached_statement)


def test_interface_keyspace_naming(mock_cluster):
    with pytest.raises(ArgusInterfaceNameError):
        ArgusDatabase.from_config(
            Config(username="a", password="b", contact_points=["127.0.0.1"], keyspace_name="has.a.dot"))


def test_interface_fetch(monkeypatch, mock_cluster, argus_interface_default):
    class ResultSet:
        @staticmethod
        def one():
            return True

    monkeypatch.setattr(MockSession, "MOCK_RESULT_SET", ResultSet())
    result = argus_interface_default.fetch("example", uuid4())

    assert result


def test_interface_fetch_non_existing(monkeypatch, mock_cluster, argus_interface_default):
    class ResultSet:
        @staticmethod
        def one():
            return None

    monkeypatch.setattr(MockSession, "MOCK_RESULT_SET", ResultSet())

    result = argus_interface_default.fetch("example", uuid4())
    assert not result


def test_interface_insert(mock_cluster, argus_interface_default):
    data = {
        "id": str(uuid4()),
        "column": "value",
        "number": 30,
        "float": 1.5,
        "list": [1, 2, 3],
    }
    argus_interface_default.insert("example", data)
    parameters = MockSession.MOCK_LAST_QUERY[1][0]

    assert json.loads(parameters) == data


def test_interface_update(mock_cluster, simple_primary_key, preset_test_details_schema, preset_test_details_serialized,
                          argus_interface_default):
    schema = {
        **simple_primary_key,
        **preset_test_details_schema,
    }

    argus_interface_default.init_table("test_table", schema)
    test_id = str(uuid4())
    data = {
        "id": test_id,
        **preset_test_details_serialized
    }

    argus_interface_default.update("test_table", data)
    assert str(MockSession.MOCK_LAST_QUERY[1][-1:][0]) == test_id


def test_interface_update_uninitialized_table(mock_cluster, simple_primary_key, preset_test_details_schema,
                                              preset_test_details_serialized, argus_interface_default):
    with pytest.raises(ArgusInterfaceSchemaError):
        argus_interface_default.update("test_table", {})


def test_interface_update_missing_primary_keys(mock_cluster, simple_primary_key, preset_test_details_schema,
                                               preset_test_details_serialized, argus_interface_default):
    schema = {
        **simple_primary_key,
        **preset_test_details_schema,
    }

    argus_interface_default.init_table("test_table", schema)
    data = {
        **preset_test_details_serialized
    }
    with pytest.raises(ArgusInterfaceSchemaError):
        argus_interface_default.update("test_table", data)
