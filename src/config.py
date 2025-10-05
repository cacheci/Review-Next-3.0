import logging
import os
from pathlib import Path

import toml

ROOT_PATH: Path = Path(__file__).resolve().parent.parent


class BaseConfig:
    """
    配置管理的基类。
    """
    toml_file_path = os.path.join(ROOT_PATH, 'config.toml')
    section = None

    @classmethod
    def update_from_toml(cls, section: str = None):
        try:
            cls.section = section
            config = toml.load(cls.toml_file_path)
            items = config.get(section, {}) if section else config
            for key, value in items.items():
                if hasattr(cls, key.upper()):
                    setattr(cls, key.upper(), value)
                # 配置必须使用大写
        except Exception as err:
            logging.error(f'Error occurred while loading config file: {err}')

    @classmethod
    def save_to_toml(cls):
        try:
            config = toml.load(cls.toml_file_path)
            if cls.section:
                if cls.section not in config:
                    config[cls.section] = {}
                for key in dir(cls):
                    if key.isupper():
                        config[cls.section][key] = getattr(cls, key)
            else:
                for key in dir(cls):
                    if key.isupper():
                        config[key] = getattr(cls, key)
            with open(cls.toml_file_path, 'w') as f:
                toml.dump(config, f)
        except Exception as err:
            logging.error(f'Error occurred while saving config file: {err}')


class ProgramConfig(BaseConfig):
    """
    程序配置 不从本地更新
    """
    VERSION: str = "0.0.1"


class Config(BaseConfig):
    """
    全局配置
    """
    LOGGING: bool = True  # 是否开启日志输出本地
    LOG_LEVE: int = 20  # 日志等级
    HTTPX_LOG_LEVE : int = 30  # httpx日志等级
    SQLALCHEMY_LOG = False  # 是否开启SQLAlchemy日志
    PROXY: str = None  # 代理
    DATABASES_DIR: Path = ROOT_PATH / 'database'  # 数据库路径


class BotConfig(BaseConfig):
    """
    机器人配置
    """
    ADMIN: list = [0]  # 管理员账号
    BOT_TOKEN: str = ""  # 机器人 Token
    BASE_URL: str = "https://api.telegram.org/bot"  # 自定义URL
    TIMEOUT: int = 60  # bot请求/读取超时时间

class Config_submit(BaseConfig):
    SUBMIT_DELETE_WHEN_CANCEL: bool = False

class ReviewConfig(BaseConfig):
    """
    审核配置
    """
    REJECTED_CHANNEL: int = 0  # 拒稿频道
    PUBLISH_CHANNEL: int = 0  # 发布频道
    REVIEWER_GROUP: int = 0  # 审核群组
    REJECTION_REASON: list = ["内容不够有趣",
                              "已在频道发布或已有人投稿",
                              "内容NSFW或引起感官不适",
                              "内容NSFW或引起感官不适",
                              "没有GET到梗",
                              "内容不在可接受范围内",
                              "禁止纯链接投稿"]  # 拒稿理由
    REJECT_NUMBER_REQUIRED: int = 2  # 拒稿所需的最小审核人数
    APPROVE_NUMBER_REQUIRED: int = 2  # 通过所需的最小审核人数
    # REJECT_REASON_USER_LIMIT: bool = False  # 是否限制只能由原拒稿人选择拒稿理由（没写这个）
    RETRACT_NOTIFY: bool = True  # 是否通知投稿者稿件被驳回
    # BANNED_NOTIFY: bool = True  # 是否通知投稿者已被屏蔽（没写这个）

class Config_verify(Config,BotConfig,ReviewConfig,Config_submit):
    """
    验证配置
    """
    @classmethod
    def verify(cls):
        import re
        if not os.path.exists(cls.toml_file_path):
            raise FileNotFoundError(f"{cls.toml_file_path} not found")
        if (not isinstance(cls.LOGGING, bool)):
            return("fail","Config verify failed: LOGGING should be bool.")
        if (not isinstance(cls.LOG_LEVE, int)):
            return("fail","Config verify failed: LOG_LEVE should be int.")
        if (not isinstance(cls.HTTPX_LOG_LEVE, int)):
            return("fail","Config verify failed: HTTPX_LOG_LEVE should be int.")
        if (not isinstance(cls.SQLALCHEMY_LOG, bool)):
            return("fail","Config verify failed: SQLALCHEMY_LOG should be bool.")
        if (not isinstance(cls.ADMIN, list)):
            return("fail","Config verify failed: ADMIN should be list.")
        if (not isinstance(cls.BOT_TOKEN, str)):
            return("fail","Config verify failed: BOT_TOKEN should be str.")
        if (not re.fullmatch(r'^\d{6,}:[a-zA-Z0-9_]{35}$', cls.BOT_TOKEN)):
            return("fail","Config verify failed: BOT_TOKEN is not correct token.")
        if (not isinstance(cls.BASE_URL, str)):
            return("fail","Config verify failed: BASE_URL should be str.")
        if (not re.fullmatch(r'^https?:\/\/([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}\/bot$', cls.BASE_URL)):
            return("fail","Config verify failed: BASE_URL is not correct api URL.")
        if (not isinstance(cls.TIMEOUT, int)):
            return("fail","Config verify failed: TIMEOUT should be int.")
        if (not isinstance(cls.SUBMIT_DELETE_WHEN_CANCEL, bool)):
            return("fail","Config verify failed: SUBMIT_DELETE_WHEN_CANCEL should be bool.")
        if (not isinstance(cls.REJECTED_CHANNEL, int)):
            return("fail","Config verify failed: REJECTED_CHANNEL should be int.")
        if not (str(cls.REJECTED_CHANNEL).startswith("-100")):
            return("warning","REJECTED_CHANNEL set not to be a group or channel. ID of a group or channel should have prefix -100.")
        if (not isinstance(cls.PUBLISH_CHANNEL, int)):
            return("fail","Config verify failed: PUBLISH_CHANNEL should be int.")
        if not (str(cls.PUBLISH_CHANNEL).startswith("-100")):
            return("warning","PUBLISH_CHANNEL set not to be a group or channel. ID of a group or channel should have prefix -100.")
        if (not isinstance(cls.REVIEWER_GROUP, int)):
            return("fail","Config verify failed: REVIEWER_GROUP should be int.")
        if not (str(cls.REVIEWER_GROUP).startswith("-100")):
            return("warning","REVIEWER_GROUP set not to be a group or channel. ID of a group or channel should have prefix -100.")
        if (not isinstance(cls.REJECTION_REASON, list)):
            return("fail","Config verify failed: TIMEOUT should be list.")
        if (not isinstance(cls.REJECT_NUMBER_REQUIRED, int)):
            return("fail","Config verify failed: TIMEOUT should be int.")
        if (not isinstance(cls.APPROVE_NUMBER_REQUIRED, int)):
            return("fail","Config verify failed: TIMEOUT should be int.")
        if (not isinstance(cls.RETRACT_NOTIFY, bool)):
            return("fail","Config verify failed: TIMEOUT should be bool.")
        return("ok","")

Config.update_from_toml()
BotConfig.update_from_toml('Bot')
ReviewConfig.update_from_toml('Review')
