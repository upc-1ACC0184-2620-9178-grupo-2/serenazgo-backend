"""Errores de dominio compartidos. La capa de interfaces los traduce a HTTP."""


class ErrorDeDominio(Exception):
    """Base de los errores de negocio."""


class NoEncontrado(ErrorDeDominio):
    """El recurso pedido no existe (HTTP 404)."""


class Conflicto(ErrorDeDominio):
    """La operación contradice el estado actual (HTTP 409)."""


class Invalido(ErrorDeDominio):
    """Datos que violan una regla de negocio (HTTP 422)."""
