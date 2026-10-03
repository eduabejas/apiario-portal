import pytest

from interfaz4.config import ErrorConfig, cargar_config, cargar_secretos, leer_dotenv


def test_config_del_repo(config):
    assert set(config.apiarios) == {"produccion_miel"}
    a = config.apiario("produccion_miel")
    assert a.lat == pytest.approx(-34.889180362505506)
    assert config.ajustes.hitos_horas == [24, 12]
    assert config.ajustes.fuente_habilitada("smn_wrf")
    assert config.ajustes.fuente_habilitada("metno")
    assert config.ajustes.fuente_habilitada("smn_cap")
    assert not config.ajustes.fuente_habilitada("open_meteo")
    assert config.ajustes.canal_habilitado("correo")
    assert not config.ajustes.canal_habilitado("google_chat")


def test_apiario_desconocido(config):
    with pytest.raises(ErrorConfig, match="Apiario desconocido"):
        config.apiario("cria_reinas")


def test_secretos_basicos():
    s = cargar_secretos({"SMTP_USUARIO": "a@b.com", "SMTP_CLAVE_APP": "abcd efgh ijkl mnop"})
    assert s.smtp_host == "smtp.gmail.com" and s.smtp_port == 587
    assert s.smtp_seguridad == "starttls"
    assert s.smtp_clave_app == "abcdefghijklmnop"
    assert s.smtp_configurado
    assert "interfaz4-apiarios" in s.metno_user_agent


def test_secretos_vacios_como_en_github():
    s = cargar_secretos({"SMTP_USUARIO": "", "SMTP_CLAVE_APP": "", "GCHAT_WEBHOOK_URL": "", "METNO_USER_AGENT": ""})
    assert not s.smtp_configurado
    assert s.gchat_webhook_url is None
    assert s.correo_destino_por_defecto == []


def test_puerto_465_usa_ssl():
    assert cargar_secretos({"SMTP_PORT": "465"}).smtp_seguridad == "ssl"


def test_correos_por_responsable(config, entorno):
    entorno = {**entorno, "CORREOS_RESPONSABLES": "Rocío Barni=rocio@example.com; Eduardo Mendoza=edu@example.com, otro@example.com"}
    cfg = cargar_config(config.base, entorno)
    assert cfg.destinatarios(None, "rocio barni") == ["rocio@example.com"]
    assert cfg.destinatarios(None, "EDUARDO  Mendoza") == ["edu@example.com", "otro@example.com"]
    assert cfg.destinatarios(None, "Otra Persona") == ["apicultor@example.com"]
    assert cfg.destinatarios("x@y.com", "Rocío Barni") == ["x@y.com"]


def test_correos_por_responsable_json():
    s = cargar_secretos({"CORREOS_RESPONSABLES": '{"Rocío Barni": ["r@x.com"], "Eduardo": "e@x.com"}'})
    assert s.correos_responsables == {"rocio barni": ["r@x.com"], "eduardo": ["e@x.com"]}


def test_correo_invalido_en_secretos():
    with pytest.raises(ErrorConfig):
        cargar_secretos({"CORREO_DESTINO_POR_DEFECTO": "no-es-correo"})


def test_dotenv(tmp_path):
    archivo = tmp_path / ".env"
    archivo.write_text(
        '# comentario\nSMTP_HOST=smtp.example.com\nMETNO_USER_AGENT="app/1.0 contacto@x.com"\nVACIA=\nCON_COMENTARIO=valor # nota\n',
        encoding="utf-8",
    )
    valores = leer_dotenv(archivo)
    assert valores["SMTP_HOST"] == "smtp.example.com"
    assert valores["METNO_USER_AGENT"] == "app/1.0 contacto@x.com"
    assert valores["VACIA"] == ""
    assert valores["CON_COMENTARIO"] == "valor"


def test_ajustes_invalidos(proyecto, entorno):
    (proyecto / "config" / "ajustes.yaml").write_text("hitos_horas: [0]\n", encoding="utf-8")
    with pytest.raises(ErrorConfig):
        cargar_config(proyecto, entorno)
    (proyecto / "config" / "ajustes.yaml").write_text("fuentes:\n  inventada: {habilitada: true}\n", encoding="utf-8")
    with pytest.raises(ErrorConfig):
        cargar_config(proyecto, entorno)


def test_falta_config(tmp_path, entorno):
    with pytest.raises(ErrorConfig):
        cargar_config(tmp_path, entorno)
