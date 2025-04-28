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

class Status(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    STATUS_UNKNOWN: _ClassVar[Status]
    SUCCESS: _ClassVar[Status]
    FAILED_DOWNLOAD: _ClassVar[Status]
    FAILED_PROCESSING: _ClassVar[Status]
    FAILED_UNSUPPORTED_TYPE: _ClassVar[Status]
    FAILED_DESERIALIZATION: _ClassVar[Status]
UNKNOWN: MediaType
IMAGE: MediaType
AUDIO: MediaType
STATUS_UNKNOWN: Status
SUCCESS: Status
FAILED_DOWNLOAD: Status
FAILED_PROCESSING: Status
FAILED_UNSUPPORTED_TYPE: Status
FAILED_DESERIALIZATION: Status

class UrlItem(_message.Message):
    __slots__ = ("media_url", "type", "page_url")
    MEDIA_URL_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    PAGE_URL_FIELD_NUMBER: _ClassVar[int]
    media_url: str
    type: MediaType
    page_url: str
    def __init__(self, media_url: _Optional[str] = ..., type: _Optional[_Union[MediaType, str]] = ..., page_url: _Optional[str] = ...) -> None: ...

class ProcessUrlsRequest(_message.Message):
    __slots__ = ("items", "apply_denoising")
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    APPLY_DENOISING_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[UrlItem]
    apply_denoising: bool
    def __init__(self, items: _Optional[_Iterable[_Union[UrlItem, _Mapping]]] = ..., apply_denoising: bool = ...) -> None: ...

class FeatureResult(_message.Message):
    __slots__ = ("url", "status", "error_message", "feature_vector")
    URL_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    FEATURE_VECTOR_FIELD_NUMBER: _ClassVar[int]
    url: str
    status: Status
    error_message: str
    feature_vector: bytes
    def __init__(self, url: _Optional[str] = ..., status: _Optional[_Union[Status, str]] = ..., error_message: _Optional[str] = ..., feature_vector: _Optional[bytes] = ...) -> None: ...

class ProcessUrlsResponse(_message.Message):
    __slots__ = ("results",)
    RESULTS_FIELD_NUMBER: _ClassVar[int]
    results: _containers.RepeatedCompositeFieldContainer[FeatureResult]
    def __init__(self, results: _Optional[_Iterable[_Union[FeatureResult, _Mapping]]] = ...) -> None: ...

class MediaItemBytes(_message.Message):
    __slots__ = ("media_content", "media_type", "reference_id")
    MEDIA_CONTENT_FIELD_NUMBER: _ClassVar[int]
    MEDIA_TYPE_FIELD_NUMBER: _ClassVar[int]
    REFERENCE_ID_FIELD_NUMBER: _ClassVar[int]
    media_content: bytes
    media_type: MediaType
    reference_id: str
    def __init__(self, media_content: _Optional[bytes] = ..., media_type: _Optional[_Union[MediaType, str]] = ..., reference_id: _Optional[str] = ...) -> None: ...

class ProcessBytesRequest(_message.Message):
    __slots__ = ("items", "apply_denoising")
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    APPLY_DENOISING_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[MediaItemBytes]
    apply_denoising: bool
    def __init__(self, items: _Optional[_Iterable[_Union[MediaItemBytes, _Mapping]]] = ..., apply_denoising: bool = ...) -> None: ...

class ProcessBytesResponse(_message.Message):
    __slots__ = ("results",)
    RESULTS_FIELD_NUMBER: _ClassVar[int]
    results: _containers.RepeatedCompositeFieldContainer[FeatureResult]
    def __init__(self, results: _Optional[_Iterable[_Union[FeatureResult, _Mapping]]] = ...) -> None: ...
