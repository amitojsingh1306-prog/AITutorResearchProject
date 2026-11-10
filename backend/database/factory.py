"""Select local conversation storage without changing tutor API contracts."""
import json
from backend.database.chroma_repository import ChromaChatRepository


def create_repository(settings):
    if not settings.mysql_enabled:return ChromaChatRepository(settings.chroma_path)
    from backend.database.mysql_store import MySQLStore
    from backend.database.mysql_repository import MySQLChatRepository
    credentials=json.loads(settings.mysql_credentials_file.read_text())
    store=MySQLStore(settings.chroma_path,credentials)
    try:return MySQLChatRepository(settings.chroma_path,store)
    except BaseException:
        store.close();raise
