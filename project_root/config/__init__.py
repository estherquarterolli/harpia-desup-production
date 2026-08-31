from .celery import app as celery_app

try:
    import pymysql

    pymysql.install_as_MySQLdb()
except ImportError:
    # Se o driver não estiver instalado, o erro vai aparecer ao iniciar o banco.
    pass

__all__ = ("celery_app",)
