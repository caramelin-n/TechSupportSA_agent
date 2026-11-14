"""Tests de las herramientas del agente (deterministas, sin LLM)."""
from src.agent import tools as t

USUARIO = "U001"      # lucia.benitez (usuario)
OTRO_USUARIO = "U002"  # martin.ojeda (usuario)
SOPORTE = "S001"       # diego.salinas
ADMIN = "A001"         # raul.gimenez


def _crear(db_session, user_id=USUARIO, **kwargs):
    params = dict(
        title="Impresora no responde",
        description="La impresora del segundo piso no responde al imprimir PDF",
        category="Hardware",
        priority="Media",
    )
    params.update(kwargs)
    return t._crear_ticket_impl(user_id, session=db_session, **params)


def test_crear_ticket_ok(db_session):
    out = _crear(db_session)
    assert out.startswith("Ticket creado: TCK-")
    assert "Abierto" in out


def test_crear_ticket_categoria_invalida(db_session):
    out = _crear(db_session, category="NoExiste")
    assert out.startswith("Error:")
    assert "NoExiste" in out


def test_crear_ticket_prioridad_invalida_lista_las_validas(db_session):
    out = _crear(db_session, priority="Urgente")
    assert out.startswith("Error:")
    assert "Crítica" in out and "Baja" in out


def test_crear_ticket_titulo_corto_es_error_de_validacion(db_session):
    out = _crear(db_session, title="ab")
    assert out.startswith("Error de validación") or out.startswith("Error:")


def test_transicion_invalida_devuelve_mensaje(db_session):
    out = _crear(db_session)
    ticket_id = out.split()[2].rstrip(".")

    # Abierto -> Cerrado no es una transición válida (ni siquiera para admin)
    res = t._actualizar_estado_impl(ADMIN, ticket_id, "Cerrado", session=db_session)
    assert res.startswith("Error:")
    assert "Transición inválida" in res


def test_usuario_no_puede_cambiar_estado(db_session):
    out = _crear(db_session)
    ticket_id = out.split()[2].rstrip(".")
    res = t._actualizar_estado_impl(USUARIO, ticket_id, "En revisión", session=db_session)
    assert res.startswith("Error:")
    assert "Solo soporte/admin" in res


def test_soporte_puede_cambiar_estado(db_session):
    out = _crear(db_session)
    ticket_id = out.split()[2].rstrip(".")
    res = t._actualizar_estado_impl(SOPORTE, ticket_id, "En revisión", session=db_session)
    assert "En revisión" in res


def test_prioridad_solo_soporte_y_admin(db_session):
    out = _crear(db_session)
    ticket_id = out.split()[2].rstrip(".")

    res = t._actualizar_prioridad_impl(USUARIO, ticket_id, "Alta", session=db_session)
    assert res.startswith("Error:")
    assert "soporte/admin" in res

    res = t._actualizar_prioridad_impl(SOPORTE, ticket_id, "Alta", session=db_session)
    assert "Alta" in res

    res = t._actualizar_prioridad_impl(ADMIN, ticket_id, "Crítica", session=db_session)
    assert "Crítica" in res


def test_usuario_no_ve_ticket_ajeno(db_session):
    out = _crear(db_session)
    ticket_id = out.split()[2].rstrip(".")
    res = t._consultar_ticket_impl(OTRO_USUARIO, ticket_id, session=db_session)
    assert res.startswith("Error:")
    assert "permiso" in res.lower()


def test_comentario_e_historial(db_session):
    out = _crear(db_session)
    ticket_id = out.split()[2].rstrip(".")

    res = t._agregar_comentario_impl(USUARIO, ticket_id, "Probé reiniciar", session=db_session)
    assert "Comentario agregado" in res

    hist = t._consultar_historial_impl(USUARIO, ticket_id, session=db_session)
    assert "CREATED" in hist
    assert "COMMENT_ADDED" in hist


def test_buscar_tickets_filtra_por_estado(db_session):
    _crear(db_session)
    res = t._buscar_tickets_impl(SOPORTE, status="Abierto", limite=200, session=db_session)
    assert "TCK-" in res


def test_buscar_tickets_estado_invalido(db_session):
    res = t._buscar_tickets_impl(SOPORTE, status="INVALIDO", session=db_session)
    assert res.startswith("Error:")
    assert "Estado inválido" in res


def test_resumen_requiere_soporte(db_session):
    res = t._resumen_incidencias_impl(USUARIO, session=db_session)
    assert res.startswith("Error:")
    assert "Solo soporte/admin" in res

    res = t._resumen_incidencias_impl(ADMIN, session=db_session)
    assert "Total de tickets" in res


def test_listar_usuarios_requiere_soporte(db_session):
    res = t._listar_usuarios_impl(USUARIO, session=db_session)
    assert res.startswith("Error:")
    assert "Solo soporte/admin" in res

    res = t._listar_usuarios_impl(SOPORTE, session=db_session)
    assert "S001" in res and "A001" in res


def test_asignar_ticket(db_session):
    out = _crear(db_session)
    ticket_id = out.split()[2].rstrip(".")
    res = t._asignar_ticket_impl(SOPORTE, ticket_id, "S001", session=db_session)
    assert "asignado" in res.lower()
    assert "S001" in res


def test_usuario_inexistente(db_session):
    out = t._crear_ticket_impl(
        "U999",
        title="Ticket fantasma",
        description="descripcion suficientemente larga",
        category="Hardware",
        priority="Baja",
        session=db_session,
    )
    assert out.startswith("Error:")
    assert "no encontrado" in out
