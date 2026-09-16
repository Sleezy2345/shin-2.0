from urllib.parse import quote

import pytest

from goji.shadow_db_config import ShadowDatabaseConfig, ShadowDatabaseConfigError


def _uri(*, user='goji_shadow_writer', password='synthetic-only-password', host='db.example.invalid',
         port='5432', path='/postgres', query='sslmode=verify-full&sslrootcert=%2Ftmp%2Ftest-ca.crt'):
    return f'postgresql://{user}:{password}@{host}:{port}{path}?{query}'


def _env(uri=None, enabled='true', **extra):
    return {'GOJI_SHADOW_ENABLED': enabled,
            'GOJI_SHADOW_DATABASE_URL': _uri() if uri is None else uri, **extra}


def test_shadow_is_disabled_by_default_and_cannot_use_a_service_role_fallback():
    for environ in ({}, {'SUPABASE_SERVICE_ROLE_KEY': 'dummy'},
                    _env(enabled='false'), _env(enabled='')):
        with pytest.raises(ShadowDatabaseConfigError):
            ShadowDatabaseConfig.from_env(environ)


def test_shadow_requires_separate_database_url_even_with_service_key():
    with pytest.raises(ShadowDatabaseConfigError):
        ShadowDatabaseConfig.from_env({'GOJI_SHADOW_ENABLED': 'true',
                                       'SUPABASE_SERVICE_ROLE_KEY': 'synthetic-only-key'})


@pytest.mark.parametrize('uri', [
    _uri(user='postgres'),
    _uri(user='service_role'),
    _uri(user='authenticated'),
    _uri(password=''),
    _uri(host=''),
    _uri(port='9999'),
    _uri(port='not-a-port'),
    _uri(path='/template1'),
    _uri(query='sslmode=require&sslrootcert=%2Ftmp%2Ftest-ca.crt'),
    _uri(query='sslmode=prefer&sslrootcert=%2Ftmp%2Ftest-ca.crt'),
    _uri(query='sslmode=verify-full'),
    _uri(query='sslmode=verify-full&sslrootcert=relative.crt'),
    _uri(query='sslmode=verify-full&sslrootcert=%2Ftmp%2Ftest-ca.crt&options=-c%20role%3Dpostgres'),
    _uri(query='sslmode=verify-full&sslrootcert=%2Ftmp%2Ftest-ca.crt&sslmode=verify-full'),
    _uri(query='sslmode=verify-full&sslrootcert=%2Ftmp%2Ftest-ca.crt&role=postgres'),
    _uri() + '#fragment',
    'not a connection URI',
])
def test_shadow_rejects_unsafe_or_malformed_connection_parameters(uri):
    with pytest.raises(ShadowDatabaseConfigError):
        ShadowDatabaseConfig.from_env(_env(uri=uri))


def test_valid_configuration_is_inert_and_does_not_reveal_password():
    url = _uri(password=quote('synthetic-only-secret!@', safe=''))
    config = ShadowDatabaseConfig.from_env(_env(uri=url, SUPABASE_SERVICE_ROLE_KEY='not-used'))
    assert config.dsn == url
    assert 'synthetic-only-secret' not in repr(config)
    assert 'SUPABASE_SERVICE_ROLE_KEY' not in repr(config)


def test_invalid_uri_error_does_not_reveal_credentials():
    with pytest.raises(ShadowDatabaseConfigError) as exc:
        ShadowDatabaseConfig.from_env(_env(uri=_uri(user='postgres', password='private-synthetic-example')))
    assert 'private-synthetic-example' not in str(exc.value)
    assert 'postgresql://' not in str(exc.value)
