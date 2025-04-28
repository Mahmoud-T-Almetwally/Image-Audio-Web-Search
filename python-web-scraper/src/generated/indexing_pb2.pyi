from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class MediaType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    UNKNOWN: _ClassVar[MediaType]
    IMAGE: _ClassVar[MediaType]
    AUDIO: _ClassVar[MediaType]
UNKNOWN: MediaType
IMAGE: MediaType
AUDIO: MediaType

class ScrapedItem(_message.Message):
    __slots__ = ("page_url", "media_url", "media_type")
    PAGE_URL_FIELD_NUMBER: _ClassVar[int]
    MEDIA_URL_FIELD_NUMBER: _ClassVar[int]
    MEDIA_TYPE_FIELD_NUMBER: _ClassVar[int]
    page_url: str
    media_url: str
    media_type: MediaType
    def __init__(self, page_url: _Optional[str] = ..., media_url: _Optional[str] = ..., media_type: _Optional[_Union[MediaType, str]] = ...) -> None: ...

class ProcessScrapedItemsRequest(_message.Message):
    __slots__ = ("items", "job_id")
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[ScrapedItem]
    job_id: str
    def __init__(self, items: _Optional[_Iterable[_Union[ScrapedItem, _Mapping]]] = ..., job_id: _Optional[str] = ...) -> None: ...

class ProcessScrapedItemsResponse(_message.Message):
    __slots__ = ("items_received", "items_processed", "items_failed", "message")
    ITEMS_RECEIVED_FIELD_NUMBER: _ClassVar[int]
    ITEMS_PROCESSED_FIELD_NUMBER: _ClassVar[int]
    ITEMS_FAILED_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    items_received: int
    items_processed: int
    items_failed: int
    message: str
    def __init__(self, items_received: _Optional[int] = ..., items_processed: _Optional[int] = ..., items_failed: _Optional[int] = ..., message: _Optional[str] = ...) -> None: ...
