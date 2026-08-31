"""全局配置：从环境变量 / .env 加载，所有模块统一从这里读配置。"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # 学校大模型 API
    api_base_url: str = ""
    api_key: str = ""
    chat_model: str = ""
    vision_model: str = ""
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    embedding_use_local: bool = True
    llm_timeout: int = 60

    # 知识库
    kb_data_dir: str = "./data/uploads"
    chunk_size: int = 700
    chunk_overlap: int = 70
    retrieval_top_k: int = 5

    # 沙箱
    sandbox_enabled: bool = True
    sandbox_timeout_sec: int = 10
    sandbox_memory_limit: str = "256m"
    sandbox_cpu_limit: str = "0.5"
    sandbox_max_concurrency: int = 3

    # 数据库
    database_url: str = "postgresql://postgres:postgres@localhost:5432/zhixue"

    # 服务
    cors_origins: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
