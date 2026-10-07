import logging
import time

from django.db import connection

logger = logging.getLogger("harpia.profiling")


class RequestProfilingMiddleware:
    """Mede tempo total, nº de queries e tempo no banco de cada requisição.

    Ligado só com PROFILE_REQUESTS=1. Escreve uma linha no log (aparece em
    Vercel → Logs) e devolve o cabeçalho Server-Timing, visível na aba Rede do
    navegador. Serve para separar "código/consultas" de "rede/infra".
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        stats = {"queries": 0, "db": 0.0, "slowest": 0.0, "slowest_sql": ""}

        def wrapper(execute, sql, params, many, context):
            inicio = time.perf_counter()
            try:
                return execute(sql, params, many, context)
            finally:
                dt = time.perf_counter() - inicio
                stats["queries"] += 1
                stats["db"] += dt
                if dt > stats["slowest"]:
                    stats["slowest"], stats["slowest_sql"] = dt, sql[:120]

        inicio = time.perf_counter()
        with connection.execute_wrapper(wrapper):
            response = self.get_response(request)
        total = time.perf_counter() - inicio

        response["Server-Timing"] = (
            f'total;dur={total * 1000:.0f}, db;dur={stats["db"] * 1000:.0f}, '
            f'queries;desc="{stats["queries"]}"'
        )
        logger.warning(
            "PERF %s %s -> %s | total=%.0fms db=%.0fms queries=%d mais_lenta=%.0fms [%s]",
            request.method, request.path, response.status_code,
            total * 1000, stats["db"] * 1000, stats["queries"],
            stats["slowest"] * 1000, stats["slowest_sql"],
        )
        return response
