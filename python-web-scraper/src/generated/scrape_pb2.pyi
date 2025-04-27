from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Status(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    UNKNOWN: _ClassVar[Status]
    ACCEPTED: _ClassVar[Status]
    REJECTED: _ClassVar[Status]

class ScrapeJobState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    STATE_UNKNOWN: _ClassVar[ScrapeJobState]
    PENDING: _ClassVar[ScrapeJobState]
    RUNNING: _ClassVar[ScrapeJobState]
    COMPLETED: _ClassVar[ScrapeJobState]
    FAILED: _ClassVar[ScrapeJobState]
UNKNOWN: Status
ACCEPTED: Status
REJECTED: Status
STATE_UNKNOWN: ScrapeJobState
PENDING: ScrapeJobState
RUNNING: ScrapeJobState
COMPLETED: ScrapeJobState
FAILED: ScrapeJobState

class StartScrapeRequest(_message.Message):
    __slots__ = ("start_url", "allowed_domains", "depth_limit", "crawl_strategy", "use_playwright")
    START_URL_FIELD_NUMBER: _ClassVar[int]
    ALLOWED_DOMAINS_FIELD_NUMBER: _ClassVar[int]
    DEPTH_LIMIT_FIELD_NUMBER: _ClassVar[int]
    CRAWL_STRATEGY_FIELD_NUMBER: _ClassVar[int]
    USE_PLAYWRIGHT_FIELD_NUMBER: _ClassVar[int]
    start_url: str
    allowed_domains: str
    depth_limit: int
    crawl_strategy: str
    use_playwright: bool
    def __init__(self, start_url: _Optional[str] = ..., allowed_domains: _Optional[str] = ..., depth_limit: _Optional[int] = ..., crawl_strategy: _Optional[str] = ..., use_playwright: bool = ...) -> None: ...

class StartScrapeResponse(_message.Message):
    __slots__ = ("job_id", "status", "message")
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    job_id: str
    status: Status
    message: str
    def __init__(self, job_id: _Optional[str] = ..., status: _Optional[_Union[Status, str]] = ..., message: _Optional[str] = ...) -> None: ...

class ScrapeStatusRequest(_message.Message):
    __slots__ = ("job_id",)
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    job_id: str
    def __init__(self, job_id: _Optional[str] = ...) -> None: ...

class ScrapeStatusResponse(_message.Message):
    __slots__ = ("job_id", "state", "message", "items_scraped")
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    ITEMS_SCRAPED_FIELD_NUMBER: _ClassVar[int]
    job_id: str
    state: ScrapeJobState
    message: str
    items_scraped: int
    def __init__(self, job_id: _Optional[str] = ..., state: _Optional[_Union[ScrapeJobState, str]] = ..., message: _Optional[str] = ..., items_scraped: _Optional[int] = ...) -> None: ...
