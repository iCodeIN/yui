from collections.abc import Mapping
from typing import Any
from typing import Union

import attr


@attr.dataclass(slots=True)
class APIResponse:

    body: Union[dict[str, Any], str]
    status: int
    headers: Mapping[str, Any]
